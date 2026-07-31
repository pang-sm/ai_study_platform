"""Small, real compiler/runtime adapters used by first-party catalog builds."""
from __future__ import annotations

import subprocess
import tempfile
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


def _compile(candidate: dict, root: Path, kind: str) -> bool:
    language = candidate["language"]
    source = candidate[f"{kind}_code"]
    if language == "Python":
        path = root / "main.py"
        path.write_text(source, encoding="utf-8")
        subprocess.run(["python", "-m", "py_compile", str(path)], cwd=root, check=True, capture_output=True, timeout=15)
        return True
    if language == "Java":
        (root / "Main.java").write_text(source, encoding="utf-8")
        subprocess.run(["javac", "Main.java"], cwd=root, check=True, capture_output=True, timeout=30)
        return True
    extension = ".cpp" if language == "C++" else ".c"
    path = root / f"main{extension}"
    path.write_text(source, encoding="utf-8")
    compiler = "g++" if language == "C++" else "gcc"
    flags = ["-std=c++17"] if language == "C++" else ["-std=c11"]
    result = subprocess.run([compiler, *flags, path.name, "-o", "program.exe"], cwd=root, capture_output=True, text=True, timeout=30)
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
            return _run(["java", "-cp", str(root), "Main"], root, stdin_text)
        return _run([str(root / "program.exe")], root, stdin_text)


def execute_wrong_solution(candidate: dict, test: dict) -> str:
    wrong = dict(candidate)
    wrong["reference_code"] = candidate["wrong_code"]
    return execute_reference(wrong, test)


def validate_candidate(candidate: dict) -> dict:
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
    return candidate
