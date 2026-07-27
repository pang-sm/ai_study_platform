"""Import a small, audited batch of Exercism exercises.

The source checkouts are intentionally external to the application repository.
Only MIT-licensed exercise metadata, starter files, public test files, and the
server-side reference/hidden data are copied into the database.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, SessionLocal, engine
import models


LANGUAGE_REPOS = {"C": "c", "C++": "cpp", "Python": "python", "Java": "java"}
LANGUAGE_CONFIG = {"C": "C", "C++": "C++", "Python": "Python", "Java": "Java"}


def run(command: list[str], cwd: Path, timeout: int = 90) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (result.stdout + "\n" + result.stderr).strip()
    return result.returncode == 0, output[-4000:]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def files_from_config(exercise_dir: Path, config: dict, key: str) -> list[dict]:
    result = []
    for relative in config.get("files", {}).get(key, []):
        path = exercise_dir / relative
        if not path.is_file():
            continue
        result.append({"path": relative.replace("\\", "/"), "content": path.read_text(encoding="utf-8")})
    return result


def official_test_bundle(language: str, exercise_dir: Path, test_files: list[dict]) -> list[dict]:
    """Include the track's test runner support without exposing it as starter code."""
    result = list(test_files)
    support_dir = exercise_dir / ("test-framework" if language == "C" else "test" if language == "C++" else "__missing__")
    if support_dir.is_dir():
        for path in sorted(support_dir.rglob("*")):
            if path.is_file():
                result.append({"path": path.relative_to(exercise_dir).as_posix(), "content": path.read_text(encoding="utf-8")})
    return result


def reference_files_from_config(exercise_dir: Path, config: dict) -> list[dict]:
    """Read the official exemplar and place it at the track's solution paths."""
    solution_paths = config.get("files", {}).get("solution", [])
    example_paths = config.get("files", {}).get("exemplar", []) or config.get("files", {}).get("example", [])
    examples = []
    for relative in example_paths:
        path = exercise_dir / relative
        if path.is_file():
            examples.append(path.read_text(encoding="utf-8"))
    if not examples or not solution_paths:
        return []
    return [
        {"path": str(solution_paths[index]).replace("\\", "/"), "content": content}
        for index, content in enumerate(examples[: len(solution_paths)])
    ]


def metadata_map(repo_dir: Path) -> dict[str, dict]:
    config = read_json(repo_dir / "config.json")
    result = {}
    for track in ("concept", "practice"):
        for item in config.get("exercises", {}).get(track, []):
            result[item["slug"]] = {**item, "track": track}
    return result


def difficulty_for(item: dict, index: int) -> str:
    value = item.get("difficulty")
    if value is None:
        prerequisites = len(item.get("prerequisites") or [])
        value = 1 if prerequisites <= 2 else 2 if prerequisites <= 5 else 4 if prerequisites <= 8 else 6
    value = int(value)
    return "入门" if value <= 1 else "简单" if value <= 3 else "中等" if value <= 5 else "困难"


def find_exercise(repo_dir: Path, slug: str) -> tuple[Path | None, str | None]:
    for track in ("concept", "practice"):
        path = repo_dir / "exercises" / track / slug
        if path.is_dir():
            return path, track
    return None, None


def audit_reference(language: str, exercise_dir: Path, reference_files: list[dict], test_files: list[dict]) -> tuple[bool, dict]:
    if not reference_files or not test_files:
        return False, {"reference": "missing reference or official tests"}
    with tempfile.TemporaryDirectory(prefix="exercism-audit-") as raw:
        temp = Path(raw) / exercise_dir.name
        shutil.copytree(exercise_dir, temp)
        for item in reference_files:
            target = temp / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
        commands = {
            "Python": ["python", "-m", "unittest", "discover", "-v", "-p", "*_test.py"],
            "C": ["gcc", "-std=c99", "-DUNITY_SUPPORT_64", "-DUNITY_OUTPUT_COLOR", "test-framework/unity.c", "-o", "tests.exe"],
            "C++": ["cmake", "-S", ".", "-B", "build", "-DEXERCISM_RUN_ALL_TESTS=ON"],
            "Java": ["cmd", "/c", str(temp / "gradlew.bat"), "test", "--no-daemon"],
        }
        if language == "C++":
            ok, output = run(commands[language], temp)
            if ok:
                ok, output = run(["cmake", "--build", "build", "--config", "Debug"], temp)
                if ok:
                    ok, output = run(["ctest", "--test-dir", "build", "--output-on-failure"], temp)
                    if ok and "No tests were found" in output:
                        cpp_sources = [
                            str(path.relative_to(temp)) for path in temp.rglob("*.cpp")
                            if ".meta" not in path.parts and "build" not in path.parts
                        ]
                        ok, output = run(["g++", "-std=c++17", "-I.", *cpp_sources, "-o", "exercise-tests.exe"], temp)
                        if ok:
                            ok, output = run([str(temp / "exercise-tests.exe")], temp)
        elif language == "C":
            ok, output = run(commands[language] + [str(path.name) for path in temp.glob("*.c")], temp)
            if ok:
                ok, output = run([str(temp / "tests.exe")], temp)
        else:
            ok, output = run(commands[language], temp)
        return ok, {"reference": "pass" if ok else "fail", "output": output}


def starter_compile(language: str, starter_files: list[dict], exercise_dir: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="exercism-starter-") as raw:
        temp = Path(raw)
        for item in starter_files:
            target = temp / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
        source_paths = [str(temp / item["path"]) for item in starter_files]
        if language == "Python":
            return run(["python", "-m", "py_compile", *source_paths], temp)
        if language == "C":
            return run(["gcc", "-fsyntax-only", *source_paths], temp)
        if language == "C++":
            return run(["g++", "-std=c++17", "-fsyntax-only", *source_paths], temp)
        return run(["javac", *source_paths], temp)


def import_language(db, source_root: Path, language: str, max_count: int, requested_slugs: list[str] | None = None) -> dict:
    repo = LANGUAGE_REPOS[language]
    repo_dir = source_root / repo
    license_path = repo_dir / "LICENSE"
    license_text = license_path.read_text(encoding="utf-8") if license_path.is_file() else ""
    if "MIT License" not in license_text and "The MIT License" not in license_text:
        raise RuntimeError(f"{repo} LICENSE is not verified as MIT")
    commit = subprocess.check_output(["git", "-C", str(repo_dir), "rev-parse", "HEAD"], text=True).strip()
    metadata = metadata_map(repo_dir)
    candidates = sorted(metadata.values(), key=lambda item: (int(item.get("difficulty") or 1), item["slug"]))
    if requested_slugs:
        requested = set(requested_slugs)
        candidates = [item for item in candidates if item["slug"] in requested]
    imported = 0
    audited = []
    for item in candidates:
        if imported >= max_count:
            break
        exercise_dir, track = find_exercise(repo_dir, item["slug"])
        if not exercise_dir:
            continue
        config_path = exercise_dir / ".meta" / "config.json"
        if not config_path.is_file():
            continue
        config = read_json(config_path)
        starter = files_from_config(exercise_dir, config, "solution")
        reference = reference_files_from_config(exercise_dir, config)
        tests = files_from_config(exercise_dir, config, "test")
        if not starter or not reference or not tests:
            continue
        official_tests = official_test_bundle(language, exercise_dir, tests)
        compile_ok, compile_output = starter_compile(language, starter, exercise_dir)
        reference_ok, reference_report = audit_reference(language, exercise_dir, reference, tests)
        audit = {"starter_compile": "pass" if compile_ok else "fail", "reference_tests": reference_report, "ai_hidden_tests": 0}
        audited.append({"slug": item["slug"], "audit": audit})
        if not compile_ok or not reference_ok:
            continue
        instructions = exercise_dir / ".docs" / "instructions.md"
        description = instructions.read_text(encoding="utf-8") if instructions.is_file() else config.get("blurb", "")
        tags = sorted(set((item.get("concepts") or []) + (item.get("practices") or []) + (item.get("prerequisites") or [])))
        public_tests = [{"path": test["path"], "content": test["content"]} for test in tests]
        payload = {
            "slug": f"{language.lower().replace('+', 'p')}-{item['slug']}",
            "language": language,
            "title": item.get("name") or item["slug"].replace("-", " ").title(),
            "difficulty": difficulty_for(item, imported),
            "tags_json": json.dumps(tags, ensure_ascii=False),
            "description": description,
            "starter_files_json": json.dumps(starter, ensure_ascii=False),
            "reference_files_json": json.dumps(reference, ensure_ascii=False),
            "public_tests_json": json.dumps(public_tests, ensure_ascii=False),
            "hidden_tests_json": json.dumps(tests, ensure_ascii=False),
            "official_test_files_json": json.dumps(official_tests, ensure_ascii=False),
            "source_repo": f"https://github.com/exercism/{repo}",
            "source_path": f"exercises/{track}/{item['slug']}",
            "source_commit": commit,
            "license": "MIT",
            "license_text": license_text,
            "attribution": f"Exercism {language} track and Exercism problem specifications; MIT License. Source: https://github.com/exercism/{repo}/tree/{commit}/exercises/{track}/{item['slug']}",
            "reference_verified": True,
            "starter_verified": True,
            "audit_report_json": json.dumps(audit, ensure_ascii=False),
        }
        existing = db.query(models.ProgrammingExercise).filter_by(slug=payload["slug"]).first()
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            db.add(models.ProgrammingExercise(**payload))
        imported += 1
    db.commit()
    return {"language": language, "imported": imported, "audited": audited, "license": "MIT", "commit": commit}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--max-per-language", type=int, default=20)
    parser.add_argument("--languages", default=",".join(LANGUAGE_REPOS))
    parser.add_argument("--slugs", default="", help="Optional comma-separated exercise slugs to audit first")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        selected = [item.strip() for item in args.languages.split(",") if item.strip() in LANGUAGE_REPOS]
        requested = [item.strip() for item in args.slugs.split(",") if item.strip()]
        report = [import_language(db, Path(args.source_root), language, args.max_per_language, requested) for language in selected]
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
