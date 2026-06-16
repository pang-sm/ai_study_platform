"""Build data-structure chapter practice questions from the annotated TXT source.

Usage:
    python backend/exam_resources/11408/data_structure/chapter_questions/build_data_structure_chapter_questions.py --dry-run
    python backend/exam_resources/11408/data_structure/chapter_questions/build_data_structure_chapter_questions.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parents[3]
PROJECT_DIR = BACKEND_DIR.parent
RAW_DIR = BASE_DIR / "raw"
CHECKED_DIR = BASE_DIR / "checked"
REPORT_DIR = BASE_DIR / "import_reports"
SOURCE_TXT = RAW_DIR / "2027数据结构_原创配套习题_全章总汇_带知识点标注_修正版.txt"
DB_PATH = BACKEND_DIR / "app.db"

SUBJECT_KEY = "data_structure"
SUBJECT_NAME = "数据结构"
SOURCE_TYPE = "chapter"
CHOICE_SECTION_TITLE = "\u4e00\u3001\u5355\u9879\u9009\u62e9\u9898"
BIG_SECTION_TITLE = "\u4e8c\u3001\u7efc\u5408\u5e94\u7528\u9898"
GRAPH_KEYWORDS = (
    "\u90bb\u63a5\u77e9\u9635",
    "\u90bb\u63a5\u8868",
    "\u5341\u5b57\u94fe\u8868",
    "\u90bb\u63a5\u591a\u91cd\u8868",
    "\u6709\u5411\u56fe",
    "\u65e0\u5411\u56fe",
    "\u8fde\u901a\u56fe",
    "\u5f3a\u8fde\u901a",
    "\u8fde\u901a\u5206\u91cf",
    "\u9876\u70b9",
    "\u8fb9\u96c6",
    "\u5f27",
    "\u5165\u5ea6",
    "\u51fa\u5ea6",
    "\u8def\u5f84",
    "\u56de\u8def",
    "\u7b80\u5355\u8def\u5f84",
    "BFS",
    "DFS",
    "\u5e7f\u5ea6\u4f18\u5148",
    "\u6df1\u5ea6\u4f18\u5148",
    "\u751f\u6210\u6811",
    "\u6700\u5c0f\u751f\u6210\u6811",
    "Prim",
    "Kruskal",
    "\u6700\u77ed\u8def\u5f84",
    "Dijkstra",
    "Floyd",
    "\u62d3\u6251\u6392\u5e8f",
    "\u5173\u952e\u8def\u5f84",
    "AOV",
    "AOE",
)

CHAPTER_NAMES = {
    "1": "第1章 绪论",
    "2": "第2章 线性表",
    "3": "第3章 栈、队列和数组",
    "4": "第4章 串",
    "5": "第5章 树与二叉树",
    "6": "第6章 图",
    "7": "第7章 查找",
    "8": "第8章 排序",
    "unclassified": "未分类",
}


@dataclass
class ParsedQuestion:
    raw_index: int
    source_question_number: str
    question_number: int | None
    question_type: str
    stem: str
    options: dict[str, str]
    standard_answer: str
    analysis: str
    knowledge_points: list[str]
    knowledge_point_id: str
    knowledge_point_name: str
    knowledge_point_path: str
    chapter_id: str
    chapter_name: str
    source_section_title: str
    source_batch_title: str
    source_chapter_title: str
    chapter_conflict: dict[str, str]


def read_source() -> str:
    return SOURCE_TXT.read_text(encoding="utf-8-sig")


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def split_knowledge_points(raw: str) -> list[str]:
    cleaned = normalize_space(raw.strip("[]【】 "))
    cleaned = re.sub(r"^知识点[:：]\s*", "", cleaned)
    parts = re.split(r"\s*(?:；|;|、|\|)\s*", cleaned)
    return [p for p in (normalize_space(part) for part in parts) if p]


def knowledge_point_code(kp: str) -> str:
    match = re.match(r"^(\d+(?:\.\d+){0,3})\b", kp.strip())
    return match.group(1) if match else ""


def source_chapter_id(title: str) -> str:
    match = re.search("\u7b2c\\s*(\\d+)\\s*\u7ae0", title or "")
    return match.group(1) if match else ""


def has_graph_signal(*parts: str) -> bool:
    text = "\n".join(part or "" for part in parts)
    lower_text = text.lower()
    for keyword in GRAPH_KEYWORDS:
        if keyword.isascii():
            if keyword.lower() in lower_text:
                return True
        elif keyword in text:
            return True
    return False


def chapter_from_knowledge_points(
    kps: list[str],
    batch_title: str,
    source_chapter_title: str = "",
    section_title: str = "",
    stem: str = "",
) -> tuple[str, str, dict[str, str]]:
    source_id = source_chapter_id(source_chapter_title)
    explicit_id = ""
    for kp in kps:
        code = knowledge_point_code(kp)
        if code:
            explicit_id = code.split(".")[0]
            break

    graph_signal = has_graph_signal(*kps, source_chapter_title, section_title, stem)
    conflict: dict[str, str] = {}
    if explicit_id and explicit_id in CHAPTER_NAMES:
        if source_id and source_id in CHAPTER_NAMES and source_id != explicit_id:
            conflict = {
                "knowledge_point_chapter_id": explicit_id,
                "knowledge_point_chapter_name": CHAPTER_NAMES[explicit_id],
                "source_chapter_id": source_id,
                "source_chapter_title": source_chapter_title,
                "reason": "knowledge_point_source_chapter_conflict",
            }
        return explicit_id, CHAPTER_NAMES[explicit_id], conflict

    if source_id == "6" or graph_signal:
        if explicit_id and explicit_id in CHAPTER_NAMES:
            conflict = {
                "knowledge_point_chapter_id": explicit_id,
                "knowledge_point_chapter_name": CHAPTER_NAMES[explicit_id],
                "source_chapter_id": source_id or "",
                "source_chapter_title": source_chapter_title,
                "reason": "source_or_keyword_graph_override",
            }
        return "6", CHAPTER_NAMES["6"], conflict

    if source_id in CHAPTER_NAMES:
        return source_id, CHAPTER_NAMES[source_id], conflict

    match = re.search("\u7b2c\\s*(\\d+)\\s*\u7ae0", batch_title or "")
    if match and match.group(1) in CHAPTER_NAMES:
        chapter_id = match.group(1)
        return chapter_id, CHAPTER_NAMES[chapter_id], conflict
    return "unclassified", CHAPTER_NAMES["unclassified"], conflict


def is_section_title(line: str) -> bool:
    if not line or line.startswith("【") or line.startswith("答案"):
        return False
    return bool(re.match(r"^\d+(?:\.\d+){1,3}\s+.+", line))


def is_question_start(line: str) -> bool:
    return bool(re.match(r"^\d{1,3}[.．]\s+", line) or re.match(r"^综合\d{1,3}[.．]\s+", line))


def parse_answer_line(line: str) -> tuple[str, str]:
    match = re.search(r"答案[:：]\s*(.*)$", line)
    if not match:
        return line, ""
    before = line[: match.start()].rstrip()
    answer = normalize_space(match.group(1))
    return before, answer


def split_option_line(line: str) -> tuple[str, str] | None:
    match = re.match(r"^([A-D])[.．、]\s*(.*)$", line.strip())
    if not match:
        return None
    return match.group(1), normalize_space(match.group(2))


def parse_question_block(
    block: list[str],
    kps: list[str],
    section_title: str,
    batch_title: str,
    source_chapter_title: str,
    raw_index: int,
    current_question_type: str,
) -> ParsedQuestion | None:
    if not block:
        return None
    first = normalize_space(block[0])
    big_match = re.match(r"^综合(\d{1,3})[.．]\s*(.*)$", first)
    choice_match = re.match(r"^(\d{1,3})[.．]\s*(.*)$", first)
    if big_match:
        question_type = "big"
        source_number = f"综合{big_match.group(1)}"
        question_number = int(big_match.group(1))
        first_stem = big_match.group(2)
    elif choice_match:
        question_type = current_question_type or "choice"
        source_number = choice_match.group(1)
        question_number = int(choice_match.group(1))
        first_stem = choice_match.group(2)
    else:
        return None

    stem_lines: list[str] = []
    options: dict[str, str] = {}
    answer = ""
    current_option = ""

    initial_stem, inline_answer = parse_answer_line(first_stem)
    if initial_stem:
        stem_lines.append(initial_stem)
    if inline_answer:
        answer = inline_answer

    for raw_line in block[1:]:
        line = raw_line.rstrip()
        if not line.strip():
            continue
        before_answer, found_answer = parse_answer_line(line)
        if found_answer:
            answer = found_answer
            line = before_answer
            if not line:
                continue
        option = split_option_line(line)
        if option:
            current_option, text = option
            options[current_option] = text
            continue
        if current_option and not is_question_start(line):
            options[current_option] = normalize_space(f"{options[current_option]} {line}")
        else:
            stem_lines.append(line.strip())

    stem = normalize_space("\n".join(stem_lines))
    if all(options.get(label) for label in ("A", "B", "C", "D")) and answer.upper() in {"A", "B", "C", "D"}:
        question_type = "choice"
    elif not options:
        question_type = "big"
    kps = kps[:]
    chapter_id, chapter_name, chapter_conflict = chapter_from_knowledge_points(
        kps,
        batch_title,
        source_chapter_title=source_chapter_title,
        section_title=section_title,
        stem=stem,
    )
    kp_codes = [knowledge_point_code(kp) for kp in kps if knowledge_point_code(kp)]
    kp_id = "；".join(kp_codes)
    kp_path = "；".join(kps)
    kp_name = kp_path

    return ParsedQuestion(
        raw_index=raw_index,
        source_question_number=source_number,
        question_number=question_number,
        question_type=question_type,
        stem=stem,
        options=options,
        standard_answer=answer,
        analysis="",
        knowledge_points=kps,
        knowledge_point_id=kp_id,
        knowledge_point_name=kp_name,
        knowledge_point_path=kp_path,
        chapter_id=chapter_id,
        chapter_name=chapter_name,
        source_section_title=section_title,
        source_batch_title=batch_title,
        source_chapter_title=source_chapter_title,
        chapter_conflict=chapter_conflict,
    )


def parse_questions(text: str) -> list[ParsedQuestion]:
    lines = text.splitlines()
    questions: list[ParsedQuestion] = []
    pending_kps: list[str] = []
    current_section = ""
    current_batch = ""
    current_source_chapter = ""
    current_question_type = "choice"
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if re.match(r"^第\d+批：", line):
            current_batch = line
            i += 1
            continue
        if re.match(r"^第\s*\d+\s*章", line):
            current_source_chapter = line
            i += 1
            continue
        if is_section_title(line):
            current_section = line
            section_code = knowledge_point_code(line)
            if section_code:
                section_chapter_id = section_code.split(".")[0]
                if section_chapter_id in CHAPTER_NAMES:
                    current_source_chapter = f"{CHAPTER_NAMES[section_chapter_id]}｜{line}"
            i += 1
            continue
        if re.match(r"^【\d+】", line):
            current_section = line
            i += 1
            continue
        if line == CHOICE_SECTION_TITLE:
            current_question_type = "choice"
            i += 1
            continue
        if line == BIG_SECTION_TITLE:
            current_question_type = "big"
            i += 1
            continue
        marker = re.match(r"^【知识点[:：](.*?)】\s*(.*)$", line)
        if marker:
            pending_kps = split_knowledge_points(marker.group(1))
            remainder = marker.group(2).strip()
            if remainder:
                lines.insert(i + 1, remainder)
            i += 1
            continue
        if is_question_start(line):
            block = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if re.match(r"^【知识点[:：]", next_line):
                    break
                if next_line.startswith("====") or re.match(r"^第\d+批：", next_line):
                    break
                if re.match(r"^第\s*\d+\s*章", next_line):
                    break
                if next_line in {CHOICE_SECTION_TITLE, BIG_SECTION_TITLE}:
                    break
                if is_section_title(next_line):
                    break
                block.append(lines[j])
                j += 1
            parsed = parse_question_block(
                block,
                pending_kps,
                current_section,
                current_batch,
                current_source_chapter,
                len(questions) + 1,
                current_question_type,
            )
            if parsed:
                questions.append(parsed)
            i = j
            continue
        i += 1
    return questions


def validate_questions(questions: list[ParsedQuestion]) -> tuple[dict, list[dict]]:
    rejected: list[dict] = []
    for q in questions:
        reasons = []
        if not q.stem:
            reasons.append("missing_stem")
        if not q.standard_answer:
            reasons.append("missing_answer")
        if not q.knowledge_points:
            reasons.append("missing_knowledge_points")
        if q.question_type == "choice":
            missing = [label for label in ("A", "B", "C", "D") if not q.options.get(label)]
            if missing:
                reasons.append(f"missing_options:{','.join(missing)}")
            if q.standard_answer.upper() not in {"A", "B", "C", "D"}:
                reasons.append("invalid_choice_answer")
        if reasons:
            item = asdict(q)
            item["reject_reasons"] = reasons
            rejected.append(item)

    total = len(questions)
    valid = total - len(rejected)
    by_chapter = Counter(q.chapter_name for q in questions)
    stats = {
        "total": total,
        "valid": valid,
        "rejected": len(rejected),
        "choice": sum(1 for q in questions if q.question_type == "choice"),
        "big": sum(1 for q in questions if q.question_type == "big"),
        "with_knowledge_points": sum(1 for q in questions if q.knowledge_points),
        "without_knowledge_points": sum(1 for q in questions if not q.knowledge_points),
        "unclassified": sum(1 for q in questions if q.chapter_id == "unclassified"),
        "chapter_conflicts": sum(1 for q in questions if q.chapter_conflict),
        "by_chapter": dict(sorted(by_chapter.items())),
    }
    return stats, rejected


def backup_file(path: Path, timestamp: str) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def write_outputs(questions: list[ParsedQuestion], rejected: list[dict], stats: dict, timestamp: str) -> None:
    CHECKED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for path in [
        CHECKED_DIR / "parsed_ready.json",
        CHECKED_DIR / "parsed_rejected.json",
        REPORT_DIR / "data_structure_annotated_build_report.json",
        REPORT_DIR / "data_structure_annotated_build_report.md",
    ]:
        backup_file(path, timestamp)

    ready_payload = [asdict(q) for q in questions if q.raw_index not in {r["raw_index"] for r in rejected}]
    (CHECKED_DIR / "parsed_ready.json").write_text(
        json.dumps(ready_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (CHECKED_DIR / "parsed_rejected.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = {
        "source_file": str(SOURCE_TXT),
        "encoding": "utf-8-sig",
        "built_at": timestamp,
        "stats": stats,
        "chapter_conflicts": [
            {
                "raw_index": q.raw_index,
                "source_question_number": q.source_question_number,
                "knowledge_points": q.knowledge_points,
                "chapter_id": q.chapter_id,
                "chapter_name": q.chapter_name,
                "source_chapter_title": q.source_chapter_title,
                "source_section_title": q.source_section_title,
                "conflict": q.chapter_conflict,
            }
            for q in questions
            if q.chapter_conflict
        ],
        "sample_questions": ready_payload[:5],
    }
    (REPORT_DIR / "data_structure_annotated_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = [
        "# 数据结构章节练习构建报告",
        f"- 题源文件: {SOURCE_TXT.name}",
        f"- 总题数: {stats['total']}",
        f"- 可入库: {stats['valid']}",
        f"- 选择题: {stats['choice']}",
        f"- 综合题: {stats['big']}",
        f"- 带知识点: {stats['with_knowledge_points']}",
        f"- 无知识点: {stats['without_knowledge_points']}",
        f"- 未分类: {stats['unclassified']}",
        f"- 章节冲突记录: {stats['chapter_conflicts']}",
        "",
        "## 每章题数",
    ]
    md.extend(f"- {chapter}: {count}" for chapter, count in stats["by_chapter"].items())
    (REPORT_DIR / "data_structure_annotated_build_report.md").write_text("\n".join(md), encoding="utf-8")


def dump_existing_rows(conn: sqlite3.Connection, timestamp: str) -> Path:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT * FROM exam_question_bank
        WHERE subject_key = ? AND source_type = ? AND is_active = 1
        ORDER BY id
        """,
        (SUBJECT_KEY, SOURCE_TYPE),
    ).fetchall()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = REPORT_DIR / f"data_structure_chapter_questions_db_backup_{timestamp}.json"
    backup_path.write_text(
        json.dumps([dict(row) for row in rows], ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return backup_path


def apply_to_database(questions: list[ParsedQuestion], timestamp: str) -> dict:
    ready = [q for q in questions if q.stem and q.standard_answer and q.knowledge_points]
    conn = sqlite3.connect(DB_PATH)
    try:
        backup_path = dump_existing_rows(conn, timestamp)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            UPDATE exam_question_bank
            SET is_active = 0, updated_at = ?
            WHERE subject_key = ? AND source_type = ? AND is_active = 1
            """,
            (now, SUBJECT_KEY, SOURCE_TYPE),
        )
        rows = []
        for q in ready:
            rows.append(
                (
                    SUBJECT_KEY,
                    SUBJECT_NAME,
                    SOURCE_TYPE,
                    "public",
                    q.knowledge_point_id,
                    q.knowledge_point_name,
                    q.knowledge_point_path,
                    q.question_number,
                    q.question_type,
                    q.stem,
                    json.dumps(q.options, ensure_ascii=False),
                    q.standard_answer,
                    q.analysis,
                    "基础",
                    json.dumps(
                        {
                            "source": SOURCE_TXT.name,
                            "raw_index": q.raw_index,
                            "source_question_number": q.source_question_number,
                            "chapter_id": q.chapter_id,
                            "chapter_name": q.chapter_name,
                            "knowledge_points": q.knowledge_points,
                            "source_section_title": q.source_section_title,
                            "source_batch_title": q.source_batch_title,
                            "source_chapter_title": q.source_chapter_title,
                            "chapter_conflict": q.chapter_conflict,
                        },
                        ensure_ascii=False,
                    ),
                    "annotated_txt",
                    "usable",
                    1,
                    now,
                    now,
                )
            )
        conn.executemany(
            """
            INSERT INTO exam_question_bank (
                subject_key, subject_name, source_type, visibility,
                knowledge_point_id, knowledge_point_name, knowledge_point_path,
                question_number, question_type, stem, options_json,
                standard_answer, analysis, difficulty, source_ref,
                generation_mode, quality_status, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
        active_total = conn.execute(
            "SELECT COUNT(*) FROM exam_question_bank WHERE subject_key=? AND source_type=? AND is_active=1",
            (SUBJECT_KEY, SOURCE_TYPE),
        ).fetchone()[0]
        return {"inserted": len(rows), "active_total": active_total, "backup_path": str(backup_path)}
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Replace active DB chapter questions after parsing.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and write reports without changing the database.")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    text = read_source()
    questions = parse_questions(text)
    stats, rejected = validate_questions(questions)
    write_outputs(questions, rejected, stats, timestamp)

    print(json.dumps({"source_file": str(SOURCE_TXT), "stats": stats}, ensure_ascii=False, indent=2))
    if args.apply:
        db_result = apply_to_database(questions, timestamp)
        print(json.dumps({"database": db_result}, ensure_ascii=False, indent=2))
    elif args.dry_run:
        print("DRY RUN - database unchanged")


if __name__ == "__main__":
    main()
