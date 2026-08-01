"""Small, real compiler/runtime adapters used by first-party catalog builds."""
from __future__ import annotations

import subprocess
import tempfile
import re
import json
from pathlib import Path


def _run(command: list[str], cwd: Path, stdin: str) -> str:
    result = subprocess.run(command, cwd=cwd, input=stdin, text=True, capture_output=True, timeout=8)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "process failed")[-500:])
    return result.stdout


def compile_starter(candidate: dict) -> bool:
    with tempfile.TemporaryDirectory(prefix="catalog-starter-") as raw:
        root = Path(raw)
        return _compile(candidate, root, "starter")


def _files(candidate: dict, kind: str) -> list[dict]:
    """Return the requested source-file set, with legacy single-file fallback."""
    value = candidate.get(f"{kind}_files")
    if isinstance(value, list) and value:
        return value
    content = candidate.get(f"{kind}_code", "")
    filename = candidate.get(
        "filename",
        "main.py" if candidate.get("language") == "Python" else
        "Main.java" if candidate.get("language") == "Java" else
        "main.cpp" if candidate.get("language") == "C++" else "main.c",
    )
    return [{"path": filename, "content": content}]


def _write_files(candidate: dict, root: Path, kind: str) -> list[Path]:
    paths: list[Path] = []
    for item in _files(candidate, kind):
        relative = Path(str(item.get("path", "")))
        if not relative.name or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid catalog source path: {relative}")
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(item.get("content", "")), encoding="utf-8")
        paths.append(path)
    return paths


def _compile(candidate: dict, root: Path, kind: str) -> bool:
    language = candidate["language"]
    paths = _write_files(candidate, root, kind)
    if language == "Python":
        subprocess.run(["python", "-m", "py_compile", *[str(path) for path in paths]], cwd=root, check=True, capture_output=True, timeout=15)
        return True
    if language == "Java":
        subprocess.run(["javac", "-d", str(root), *[str(path) for path in paths]], cwd=root, check=True, capture_output=True, timeout=30)
        return True
    extension = ".cpp" if language == "C++" else ".c"
    compiler = "g++" if language == "C++" else "gcc"
    flags = ["-std=c++17"] if language == "C++" else ["-std=c11"]
    source_paths = [path for path in paths if path.suffix in {".c", ".cc", ".cpp", ".cxx"}]
    result = subprocess.run([compiler, *flags, *[str(path) for path in source_paths], "-o", "program.exe"], cwd=root, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "compiler failed")[-1000:])
    return True


def execute_reference(candidate: dict, test: dict) -> str:
    with tempfile.TemporaryDirectory(prefix="catalog-reference-") as raw:
        root = Path(raw)
        _compile(candidate, root, "reference")
        language = candidate["language"]
        stdin_text = str(test.get("stdin_text", test.get("stdin", "")))
        if language == "Python":
            return _run(["python", "main.py"], root, stdin_text)
        if language == "Java":
            return _run(["java", "-cp", str(root), candidate.get("main_class", "Main")], root, stdin_text)
        return _run([str(root / "program.exe")], root, stdin_text)


def execute_wrong_solution(candidate: dict, test: dict) -> str:
    wrong = dict(candidate)
    if candidate.get("wrong_files"):
        wrong["reference_files"] = candidate["wrong_files"]
    else:
        wrong["reference_code"] = candidate["wrong_code"]
    return execute_reference(wrong, test)


def validate_candidate(candidate: dict) -> dict:
    required = (
        "source_key", "language", "title_zh", "summary_zh", "statement_zh",
        "input_format_zh", "output_format_zh", "constraints_zh", "difficulty",
        "problem_family_id", "language_fit_reason", "learning_objective_id",
        "learning_objective", "prerequisites", "core_skill", "novelty_reason",
        "knowledge_tags",
    )
    missing = [key for key in required if not candidate.get(key)]
    if missing:
        raise ValueError("missing quality metadata: " + ",".join(missing))
    title = str(candidate["title_zh"]).strip().lower()
    if re.search(r"(?:练习|题目|习题)\s*\d+$", title) or re.search(r"(?:add|sub|mul|max|min|basic|variant|generated)", title):
        raise ValueError("template or numbered title")
    public_inputs = {str(test.get("stdin_text", test.get("stdin", ""))) for test in candidate["public_cases"]}
    hidden_inputs = {str(test.get("stdin_text", test.get("stdin", ""))) for test in candidate["hidden_cases"]}
    if public_inputs & hidden_inputs:
        raise ValueError("public and hidden inputs overlap")
    if len(candidate["public_cases"]) < 3 or len(candidate["hidden_cases"]) < 5:
        raise ValueError("insufficient public or hidden tests")
    if not compile_starter(candidate):
        raise RuntimeError("starter did not compile")
    public = candidate["public_cases"]
    hidden = candidate["hidden_cases"]
    def run_all(item: dict, tests: list[dict]) -> list[str]:
        with tempfile.TemporaryDirectory(prefix="catalog-validated-") as raw:
            root = Path(raw)
            _compile(item, root, "reference")
            language = item["language"]
            command = ["python", "main.py"] if language == "Python" else ["java", "-cp", str(root), "Main"] if language == "Java" else [str(root / "program.exe")]
            return [_run(command, root, str(test.get("stdin_text", test.get("stdin", "")))) for test in tests]

    all_tests = [*public, *hidden]
    outputs = run_all(candidate, all_tests)
    for actual, test in zip(outputs, all_tests):
        if actual.replace("\r\n", "\n").rstrip("\n") != test["expected_stdout"].rstrip("\n"):
            raise RuntimeError("reference output mismatch")
    wrong = dict(candidate)
    wrong["reference_code"] = candidate["wrong_code"]
    wrong_outputs = run_all(wrong, hidden)
    if not any(actual.rstrip("\n") != test["expected_stdout"].rstrip("\n") for actual, test in zip(wrong_outputs, hidden)):
        raise RuntimeError("wrong solution was not rejected")
    candidate["validated"] = True
    candidate["quality_status"] = "approved"
    candidate.setdefault("quality_score", 100)
    return candidate
