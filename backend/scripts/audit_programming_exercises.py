"""Run a real, repeatable audit over the imported programming exercise rows.

The audit intentionally executes the stored reference files against the stored
official test bundle.  It also injects a guaranteed failing mutation so a test
bundle cannot be marked adequate merely because it compiles.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from database import SessionLocal
import models


COPY_PATH = ROOT / "frontend" / "src" / "components" / "programmingExerciseCopy.js"
TIMEOUT_SECONDS = 30


def load_items(value: str) -> list[dict]:
    try:
        result = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return result if isinstance(result, list) else []


def safe_relative_path(value: str) -> Path:
    path = PurePosixPath(str(value or ""))
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe path: {value}")
    return Path(*path.parts)


def write_files(root: Path, items: list[dict]) -> None:
    for item in items:
        path = safe_relative_path(item.get("path"))
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(item.get("content") or ""), encoding="utf-8")


def run_command(command: list[str], cwd: Path) -> dict:
    started = time.monotonic()
    command_env = os.environ.copy()
    compiler = shutil.which("g++") or shutil.which("gcc")
    if compiler:
        compiler_dir = str(Path(compiler).parent)
        command_env["PATH"] = compiler_dir + os.pathsep + command_env.get("PATH", "")
    command_env["PYTHONPATH"] = str(cwd) + os.pathsep + command_env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env=command_env,
        )
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "output": (proc.stdout or "") + (proc.stderr or ""),
            "timed_out": False,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": str(exc.stdout or ""),
            "stderr": str(exc.stderr or ""),
            "output": f"timeout after {TIMEOUT_SECONDS}s\n{exc}",
            "timed_out": True,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except OSError as exc:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
            "output": str(exc),
            "timed_out": False,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


def source_paths(items: list[dict], suffixes: tuple[str, ...]) -> list[str]:
    return [
        str(safe_relative_path(item["path"]))
        for item in items
        if str(item.get("path", "")).lower().endswith(suffixes)
    ]


def build_commands(language: str, reference: list[dict], tests: list[dict], root: Path) -> tuple[list[str], list[str]]:
    if language == "Python":
        return (
            [sys.executable, "-m", "unittest", "discover", "-v", "-p", "*_test.py"],
            [],
        )
    if language == "C":
        sources = source_paths(reference, (".c",))
        test_sources = [
            path for path in source_paths(tests, (".c",))
            if not path.replace("\\", "/").startswith("test-framework/")
        ]
        return (
            ["gcc", "-std=c11", "-DEXERCISM_RUN_ALL_TESTS", "-I.", *sources, *test_sources, "test-framework/unity.c", "-o", "exercise-tests.exe"],
            ["exercise-tests.exe"],
        )
    if language == "C++":
        sources = source_paths(reference, (".cpp", ".cc", ".cxx"))
        test_sources = source_paths(tests, (".cpp", ".cc", ".cxx"))
        included_sources = {
            match.group(1).replace("\\", "/")
            for item in tests
            for match in re.finditer(r'#include\s+"([^" ]+\.c(?:pp|cxx)?)"', str(item.get("content") or ""))
        }
        sources = [path for path in sources if path.replace("\\", "/") not in included_sources and Path(path).name not in {Path(item).name for item in included_sources}]
        return (
            ["g++", "-std=c++17", "-static-libgcc", "-static-libstdc++", "-DEXERCISM_RUN_ALL_TESTS", "-I.", *sources, *test_sources, "-o", "exercise-tests.exe"],
            ["exercise-tests.exe"],
        )
    return [], []


def starter_compile(language: str, starter: list[dict]) -> dict:
    with tempfile.TemporaryDirectory(prefix="programming-starter-audit-") as raw:
        root = Path(raw)
        write_files(root, starter)
        paths = source_paths(starter, (".py", ".c", ".cpp", ".cc", ".cxx", ".java"))
        if not paths:
            return {"passed": False, "reason": "starter has no compilable source file"}
        if language == "Python":
            result = run_command([sys.executable, "-m", "py_compile", *paths], root)
        elif language == "C":
            result = run_command(["gcc", "-std=c11", "-fsyntax-only", *paths], root)
        elif language == "C++":
            result = run_command(["g++", "-std=c++17", "-fsyntax-only", *paths], root)
        else:
            return {"passed": False, "reason": "unsupported language runner"}
        return {"passed": result["exit_code"] == 0, "result": result}


def execute_bundle(language: str, starter: list[dict], reference: list[dict], official: list[dict]) -> dict:
    with tempfile.TemporaryDirectory(prefix="programming-audit-") as raw:
        root = Path(raw)
        write_files(root, starter)
        write_files(root, reference)
        write_files(root, official)
        compile_command, run_command_value = build_commands(language, reference, official, root)
        if not compile_command:
            return {"passed": False, "reason": "unsupported language runner", "compile": None, "run": None}
        if language == "Python":
            test_runner = [sys.executable, "-m", "pytest", "-q"]
            if importlib.util.find_spec("pytest") is None and sys.platform == "win32":
                test_runner = ["py", "-3.13", "-m", "pytest", "-q"]
            if importlib.util.find_spec("pytest") is None and sys.platform != "win32":
                return {"passed": False, "reason": "pytest is not installed", "compile": None, "run": None}
            compile_command = test_runner
            run_result = run_command(compile_command, root)
            return {"passed": run_result["exit_code"] == 0, "compile": None, "run": run_result}
        compile_result = run_command(compile_command, root)
        if compile_result["exit_code"] != 0:
            return {"passed": False, "compile": compile_result, "run": None}
        produced = [path.name for path in root.glob("exercise-tests*")]
        if sys.platform == "win32" and run_command_value and not Path(str(run_command_value[0])).is_absolute():
            run_command_value = [str(root / run_command_value[0]), *run_command_value[1:]]
        run_result = run_command(run_command_value, root)
        return {"passed": run_result["exit_code"] == 0, "compile": compile_result, "produced": produced, "run": run_result}


def mutate_reference(language: str, reference: list[dict]) -> list[dict]:
    result = [dict(item) for item in reference]
    if not result:
        return result
    first = dict(result[0])
    content = str(first.get("content") or "")
    if language == "Python":
        mutated = re.sub(r"(?m)^(\s*)return\s+.+$", r"\1return None  # intentional audit mutation", content, count=1)
        first["content"] = mutated if mutated != content else 'raise AssertionError("intentional audit mutation")\n' + content
    elif language == "C++":
        mutated = re.sub(r"(?m)^(\s*)return\s+[^;]+;", r"\1return {}; // intentional audit mutation", content, count=1)
        first["content"] = mutated if mutated != content else "#error intentional audit mutation\n" + content
    else:
        mutated = re.sub(r"(?m)^(\s*)return\s+[^;]+;", r"\1return 0; /* intentional audit mutation */", content, count=1)
        first["content"] = mutated if mutated != content else "#error intentional audit mutation\n" + content
    result[0] = first
    return result


def mutate_reference_variants(language: str, reference: list[dict]) -> list[list[dict]]:
    variants = []
    for file_index, item in enumerate(reference):
        content = str(item.get("content") or "")
        for match in re.finditer(r"(?m)^(\s*)return\s+([^;]+);?", content):
            expression = match.group(2).strip()
            if language == "Python":
                replacement = f"{match.group(1)}return None  # intentional audit mutation"
            elif language == "C++":
                replacement = f"{match.group(1)}return {{}}; // intentional audit mutation"
            else:
                replacement = f"{match.group(1)}return 0; /* intentional audit mutation */"
            mutated_content = content[:match.start()] + replacement + content[match.end():]
            variant = [dict(entry) for entry in reference]
            variant[file_index] = {**variant[file_index], "content": mutated_content}
            if mutated_content != content and expression not in ("None", "0", "NULL", "{}"):
                variants.append(variant)
    if not variants:
        variants.append(mutate_reference(language, reference))
    return variants[:12]


def test_count(language: str, output: str) -> int:
    text = output or ""
    patterns = {
        "Python": r"Ran\s+(\d+)\s+tests?",
        "C": r"(\d+)\s+Tests\s+\d+\s+Failures",
    }
    if language == "C++":
        match = re.search(r"test cases:\s*(\d+)\s*\|", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"\((\d+)\s+assertions?\s+in\s+(\d+)\s+test cases?\)", text, re.IGNORECASE)
        return int(match.group(2)) if match else 0
    match = re.search(patterns.get(language, r"$^"), text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def copy_keys() -> set[str]:
    source = COPY_PATH.read_text(encoding="utf-8")
    result = set()
    for match in re.finditer(r"^\s*(?:\"([^\"]+)\"|([A-Za-z0-9-]+))\s*:\s*\[", source, re.MULTILINE):
        result.add(match.group(1) or match.group(2))
    return result


def base_slug(slug: str) -> str:
    return re.sub(r"^(python|c|cpp|java)-", "", slug)


def audit_row(row: models.ProgrammingExercise, copies: set[str]) -> dict:
    starter = load_items(row.starter_files_json)
    reference = load_items(row.reference_files_json)
    public = load_items(row.public_tests_json)
    hidden = load_items(row.hidden_tests_json)
    official = load_items(row.official_test_files_json)
    structural = {
        "starter_files": bool(starter),
        "reference_files": bool(reference),
        "public_tests": bool(public),
        "hidden_tests": bool(hidden),
        "official_tests": bool(official),
        "source_complete": bool(row.source_repo and row.source_path and row.source_commit and row.license == "MIT"),
    }
    starter_run = starter_compile(row.language, starter)
    reference_run = execute_bundle(row.language, starter, reference, official)
    mutation_runs = []
    for mutation in mutate_reference_variants(row.language, reference):
        mutation_run = execute_bundle(row.language, starter, mutation, official)
        mutation_runs.append(mutation_run)
        if not mutation_run["passed"]:
            break
    mutation_run = mutation_runs[-1]
    reference_output = ""
    for result in (reference_run.get("compile"), reference_run.get("run")):
        if result:
            reference_output += result.get("output", "")
    mutation_output = ""
    for result in (mutation_run.get("compile"), mutation_run.get("run")):
        if result:
            mutation_output += result.get("output", "")
    return {
        "id": row.id,
        "slug": row.slug,
        "language": row.language,
        "title": row.title,
        "reference_passed": reference_run["passed"],
        "starter_passed": starter_run["passed"],
        "starter_result": starter_run,
        "reference_test_count": test_count(row.language, reference_output),
        "reference_result": reference_run,
        "wrong_implementation_rejected": any(not item["passed"] for item in mutation_runs),
        "mutation_variant_count": len(mutation_runs),
        "structural_passed": all(structural.values()),
        "wrong_implementation_result": mutation_run,
        "structural": structural,
        "translation_copy_present": base_slug(row.slug) in copies,
        "failure_reason": "" if reference_run["passed"] else reference_output[-4000:],
        "mutation_failure_reason": "" if not mutation_run["passed"] else mutation_output[-4000:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default="")
    parser.add_argument("--report", default="")
    parser.add_argument("--languages", default="C,C++,Python,Java")
    parser.add_argument("--slugs", default="", help="Optional comma-separated database slugs")
    args = parser.parse_args()
    if args.database_url:
        raise SystemExit("Set DATABASE_URL before importing this script")
    db = SessionLocal()
    try:
        copies = copy_keys()
        rows = db.query(models.ProgrammingExercise).order_by(models.ProgrammingExercise.language, models.ProgrammingExercise.id).all()
        languages = {item.strip() for item in args.languages.split(",") if item.strip()}
        slugs = {item.strip() for item in args.slugs.split(",") if item.strip()}
        rows = [row for row in rows if row.language in languages and (not slugs or row.slug in slugs)]
        results = []
        for index, row in enumerate(rows, start=1):
            print(f"[{index}/{len(rows)}] auditing {row.language} {row.slug}", flush=True)
            results.append(audit_row(row, copies))
        summary = {}
        for language in ("C", "C++", "Python", "Java"):
            selected = [item for item in results if item["language"] == language]
            summary[language] = {
                "total": len(selected),
                "reference_passed": sum(item["reference_passed"] for item in selected),
                "reference_failed": sum(not item["reference_passed"] for item in selected),
                "starter_passed": sum(item["starter_passed"] for item in selected),
                "starter_failed": sum(not item["starter_passed"] for item in selected),
                "wrong_implementation_rejected": sum(item["wrong_implementation_rejected"] for item in selected),
                "translation_copy_missing": sum(not item["translation_copy_present"] for item in selected),
            }
        report = {"summary": summary, "results": results}
        output = json.dumps(report, ensure_ascii=False, indent=2)
        print(output)
        if args.report:
            Path(args.report).write_text(output, encoding="utf-8")
    finally:
        db.close()


if __name__ == "__main__":
    main()
