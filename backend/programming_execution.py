"""Language-specific execution helpers for programming exercises."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
import os
from pathlib import Path


JAVA_BUILD_GRADLE = '''
plugins {
    id "java"
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation platform("org.junit:junit-bom:5.10.0")
    testImplementation "org.junit.jupiter:junit-jupiter"
    testImplementation "org.assertj:assertj-core:3.25.1"
    testRuntimeOnly "org.junit.platform:junit-platform-launcher"
}

test {
    useJUnitPlatform()
    testLogging {
        exceptionFormat = "full"
        showStandardStreams = true
        events = ["passed", "failed", "skipped"]
    }
}
'''.strip() + "\n"


def java_enabled_test_content(content: str) -> str:
    """Enable the full official suite inside the isolated execution directory."""
    return re.sub(r"(?m)^\s*@Disabled(?:\([^\n]*\))?\s*\n", "", str(content or ""))


def _safe_relative_path(value: str) -> Path:
    path = Path(str(value or "").replace("\\", "/"))
    if not str(value).strip() or path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid exercise file path")
    return path


def _find_gradle() -> str | None:
    commands = ("gradle.bat", "gradle") if os.name == "nt" else ("gradle", "gradle.bat")
    for command in commands:
        found = shutil.which(command)
        if found:
            return found
    wrapper_root = Path.home() / ".gradle" / "wrapper" / "dists"
    if wrapper_root.is_dir():
        names = commands
        for name in names:
            matches = sorted(wrapper_root.rglob(name))
            if matches:
                return str(matches[-1])
    return None


def _parse_junit_cases(output: str, duration_ms: int) -> list[dict]:
    pattern = re.compile(r"^\s*([\w$.-]+)\s+>\s+(.+?)\s+(PASSED|FAILED|SKIPPED)\s*$", re.MULTILINE)
    cases = []
    for index, match in enumerate(pattern.finditer(output)):
        raw_status = match.group(3).lower()
        status = "passed" if raw_status == "passed" else "failed" if raw_status == "failed" else "skipped"
        cases.append({
            "id": f"java-case-{index + 1}",
            "name": match.group(2).strip(),
            "status": status,
            "reason": "" if status == "passed" else "官方测试断言未通过",
            "duration_ms": duration_ms,
            "source_test_name": match.group(1),
        })
    return cases


def _java_failure_values(output: str) -> tuple[str | None, str | None]:
    def find_value(label: str) -> str | None:
        match = re.search(
            rf"{label}:\s*(?:\"([^\"\n]*)\"|<([^>\n]*)>)",
            output,
            re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(1) if match.group(1) is not None else match.group(2)

    return (find_value("expected"), find_value("but was"))


def _java_location(output: str) -> str | None:
    match = re.search(r"([A-Za-z0-9_$./\\-]+\.java):(\d+):\s+error:", output)
    if match:
        return f"{Path(match.group(1)).name}:{match.group(2)}"
    match = re.search(r"([A-Za-z0-9_$./\\-]+\.java):(\d+)", output)
    return f"{Path(match.group(1)).name}:{match.group(2)}" if match else None


def run_java_tests(
    source_files: list[dict],
    test_files: list[dict],
    selector: str | None = None,
    timeout_seconds: int = 6,
) -> dict:
    """Run one JUnit 5 selector or the complete official suite.

    Only the supplied current-exercise source and test files are copied into
    the temporary directory. Gradle runs offline so a missing deployment cache
    is reported instead of triggering a runtime dependency download.
    """
    gradle = _find_gradle()
    if not gradle:
        return {
            "success": False,
            "status": "compile_failed",
            "passed": False,
            "passed_count": 0,
            "total_count": 1,
            "failed_categories": ["compile"],
            "duration_ms": 0,
            "stderr": "服务器未安装 Gradle，Java 练习无法构建。",
            "technical_details": "gradle command was not found",
            "exit_code": -1,
            "compile_error": "Gradle 未安装或部署缓存不可用",
            "cases": [],
        }

    started = time.time()
    with tempfile.TemporaryDirectory(prefix="exercise-java-") as raw:
        temp = Path(raw)
        try:
            for item in source_files:
                target = temp / _safe_relative_path(item.get("relative_path") or item.get("path") or "")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(item.get("content") or ""), encoding="utf-8")
            for item in test_files:
                target = temp / _safe_relative_path(item.get("path") or item.get("relative_path") or "")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(java_enabled_test_content(item.get("content") or ""), encoding="utf-8")
        except (OSError, ValueError) as exc:
            return {
                "success": False,
                "status": "compile_failed",
                "passed": False,
                "passed_count": 0,
                "total_count": 1,
                "failed_categories": ["compile"],
                "duration_ms": int((time.time() - started) * 1000),
                "stderr": str(exc),
                "technical_details": str(exc),
                "exit_code": -1,
                "compile_error": str(exc),
                "cases": [],
            }
        (temp / "build.gradle").write_text(JAVA_BUILD_GRADLE, encoding="utf-8")
        (temp / "settings.gradle").write_text('rootProject.name = "exercise"\n', encoding="utf-8")
        command = [gradle, "--offline", "--no-daemon", "test"]
        if selector:
            command.extend(["--tests", selector])
        try:
            process = subprocess.run(
                command,
                cwd=temp,
                capture_output=True,
                text=True,
                timeout=max(30, timeout_seconds + 24),
            )
            output = ((process.stdout or "") + "\n" + (process.stderr or "")).strip()
            exit_code = process.returncode
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            output = "\n".join(str(part or "") for part in (exc.stdout, exc.stderr)).strip()
            exit_code = -1
            timed_out = True

    duration_ms = int((time.time() - started) * 1000)
    cases = _parse_junit_cases(output, duration_ms)
    if timed_out:
        status = "timeout"
        reason = "程序运行超过 5 秒，可能存在死循环"
    elif "compileJava" in output and re.search(r"\berror:\s", output, re.IGNORECASE):
        status = "compile_failed"
        reason = "Java 代码编译失败"
    elif exit_code == 0 and cases and all(case["status"] == "passed" for case in cases):
        status = "passed"
        reason = ""
    elif exit_code == 0:
        status = "passed"
        reason = ""
    else:
        status = "failed"
        reason = "返回结果与期望值不一致"
    expected, actual = _java_failure_values(output)
    if status == "failed":
        for case in cases:
            if case["status"] == "failed":
                case["reason"] = reason
                if expected is not None:
                    case["expected"] = expected
                if actual is not None:
                    case["actual"] = actual
    if status in {"compile_failed", "timeout"} and not cases:
        cases = [{
            "id": "java-run",
            "name": "当前 Java 测试",
            "status": status,
            "reason": reason,
            "location": _java_location(output),
            "duration_ms": duration_ms,
        }]
    passed_count = sum(1 for case in cases if case["status"] == "passed")
    total_count = len(cases) or 1
    failed_count = total_count - passed_count
    return {
        "success": True,
        "status": status,
        "passed": status == "passed",
        "passed_count": passed_count,
        "total_count": total_count,
        "failed_categories": [] if status == "passed" else ["compile" if status == "compile_failed" else status],
        "duration_ms": duration_ms,
        "stdout": "",
        "stderr": "" if status == "passed" else output,
        "compile_error": output if status == "compile_failed" else None,
        "exit_code": exit_code,
        "cases": cases,
        "technical_details": output[-12000:],
        "summary": f"通过 {passed_count}/{total_count}" if not failed_count else f"{failed_count} 个样例未通过",
    }
