"""Create the fixed online Workbench acceptance sample from the public catalog API."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "verification-results"
BASE_URL = "http://101.32.190.42/api"
SEED = 20260803
LANGUAGES = ("C", "C++", "Python", "Java")


def get_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "workbench-audit/1.0"})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def all_exercises(language: str) -> list[dict]:
    rows: list[dict] = []
    for page in (1, 2):
        payload = get_json(f"{BASE_URL}/programming/exercises?language={quote(language)}&page={page}&page_size=48")
        rows.extend(payload.get("exercises") or [])
    if len(rows) != 60:
        raise RuntimeError(f"online catalog count for {language} is {len(rows)}, expected 60")
    return rows


def is_multifile(row: dict) -> bool:
    manifest = row.get("manifest") or {}
    editable = manifest.get("editable_files") or []
    return row.get("language") == "Java" and len(editable) >= 3


def reasons(row: dict, seed: int, multifile: bool = False) -> list[str]:
    result = [f"固定种子 {seed} 分层随机抽样"]
    difficulty = str(row.get("difficulty") or "")
    if difficulty:
        result.append(f"难度：{difficulty}")
    samples = row.get("public_samples") or []
    if samples and "\n" in str(samples[0].get("stdin_text") or ""):
        result.append("多行输入")
    else:
        result.append("单行或短输入")
    statement = f"{row.get('title', '')} {row.get('statement', '')}".lower()
    if any(marker in statement for marker in ("字符串", "文本", "字符", "日志")):
        result.append("字符串或文本")
    if any(marker in statement for marker in ("数组", "集合", "列表", "记录", "图", "矩阵")):
        result.append("数组、集合或算法")
    if multifile:
        result.append("Java 真实多文件专项")
    return result


def main() -> None:
    rng = random.Random(SEED)
    selected: list[dict] = []
    for language in LANGUAGES:
        rows = all_exercises(language)
        if language == "Java":
            multi = [row for row in rows if is_multifile(row)]
            if len(multi) < 5:
                raise RuntimeError(f"Java multifile candidates: {len(multi)}, expected at least 5")
            chosen_multi = rng.sample(multi, 5)
            remaining = [row for row in rows if row not in chosen_multi]
            chosen = chosen_multi + rng.sample(remaining, 5)
        else:
            chosen = rng.sample(rows, 10)
        for row in chosen:
            selected.append(
                {
                    "language": language,
                    "exercise_id": row["id"],
                    "source_key": row.get("source_key", ""),
                    "title": row.get("title", ""),
                    "difficulty": row.get("difficulty", ""),
                    "exercise_type": "multi_file" if is_multifile(row) else "standard_io",
                    "random_seed": SEED,
                    "selection_reason": reasons(row, SEED, is_multifile(row)),
                }
            )
    selected.sort(key=lambda item: (LANGUAGES.index(item["language"]), item["exercise_id"]))
    payload = {
        "base_url": BASE_URL,
        "random_seed": SEED,
        "total": len(selected),
        "counts": {language: sum(item["language"] == language for item in selected) for language in LANGUAGES},
        "java_multifile_count": sum(item["exercise_type"] == "multi_file" for item in selected),
        "exercises": selected,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "programming-workbench-random-40-sample.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# Workbench 固定随机 40 题清单",
        "",
        f"- 正式站点：{BASE_URL}",
        f"- 随机种子：`{SEED}`",
        f"- 总数：{len(selected)}；Java 多文件：{payload['java_multifile_count']}",
        "",
        "| 语言 | exercise_id | 题名 | 难度 | 类型 | 抽样原因 |",
        "|---|---:|---|---|---|---|",
    ]
    for item in selected:
        lines.append(
            f"| {item['language']} | {item['exercise_id']} | {item['title']} | {item['difficulty']} | "
            f"{item['exercise_type']} | {'；'.join(item['selection_reason'])} |"
        )
    (OUT / "programming-workbench-random-40-sample.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUT), "total": len(selected), "counts": payload["counts"], "java_multifile_count": payload["java_multifile_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
