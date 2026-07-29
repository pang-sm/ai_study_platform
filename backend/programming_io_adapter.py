"""Hidden stdin/stdout adapters for structured Exercism public samples.

The adapter is created in a fresh temporary directory and is never returned to
the browser. It calls the learner's editable implementation and compares the
real stdout with the canonical sample stdout. Exercises whose manifest cannot
be adapted safely return ``None`` and continue through the audited official
runner instead of guessing a callable or changing its signature.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath


def _safe_path(value: str) -> str:
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe adapter path")
    return str(path)


def _normalize_stdout(value: str | None) -> str:
    return str(value or "").replace("\r\n", "\n").rstrip("\n")


def _result(sample: dict, started: float, proc: subprocess.CompletedProcess, technical: str = "") -> dict:
    expected = str(sample.get("expected_stdout") or "")
    actual = str(proc.stdout or "")
    stderr = str(proc.stderr or "").strip()
    passed = proc.returncode == 0 and _normalize_stdout(actual) == _normalize_stdout(expected)
    return {
        "success": True,
        "passed": passed,
        "passed_count": 1 if passed else 0,
        "total_count": 1,
        "failed_categories": [] if passed else (["compile"] if proc.returncode != 0 and not actual else ["tests"]),
        "duration_ms": int((time.time() - started) * 1000),
        "stdout": actual,
        "stderr": stderr,
        "actual_output": actual,
        "expected_output": expected,
        "actual_stdout": actual,
        "expected_stdout": expected,
        "test_name": sample.get("name") or sample.get("source_test_name"),
        "exit_code": proc.returncode,
        "compile_error": stderr if proc.returncode != 0 and not actual else None,
        "technical_details": technical or stderr or None,
    }


def _write_user_files(temp: Path, files: list[dict]) -> list[Path]:
    paths = []
    for item in files:
        relative = _safe_path(item.get("relative_path") or item.get("path"))
        target = temp / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(item.get("content") or ""), encoding="utf-8")
        paths.append(target)
    return paths


def _python_adapter(temp: Path, paths: list[Path], sample: dict, config: dict) -> tuple[list[str], list[str]] | None:
    source = next((path for path in paths if path.suffix == ".py"), None)
    callable_name = str(config.get("callable") or "")
    if not source or not callable_name.isidentifier():
        return None
    schemas = json.dumps(config.get("input_schema") or [], ensure_ascii=False)
    adapter = temp / "__exercise_adapter.py"
    adapter.write_text(
        f'''import importlib\nimport json\nimport sys\n\nSCHEMAS = json.loads({schemas!r})\nmodule = importlib.import_module({source.stem!r})\nlines = sys.stdin.read().splitlines()\nline_index = 0\n\ndef scalar(schema):\n    global line_index\n    if line_index >= len(lines):\n        return ""\n    value = lines[line_index]\n    line_index += 1\n    kind = schema if isinstance(schema, str) else "string"\n    if kind in ("integer", "number"):\n        return int(value) if kind == "integer" else float(value)\n    if kind == "boolean":\n        return value.strip().lower() == "true"\n    return value\n\ndef parse(schema):\n    global line_index\n    if isinstance(schema, dict) and schema.get("type") == "array":\n        count = int(lines[line_index]) if line_index < len(lines) and lines[line_index].strip() else 0\n        line_index += 1\n        values = lines[line_index].split() if line_index < len(lines) else []\n        line_index += 1\n        item = schema.get("item", "string")\n        return [int(value) if item == "integer" else float(value) if item == "number" else value for value in values[:count]]\n    if isinstance(schema, dict) and schema.get("type") == "matrix":\n        rows, columns = (int(value) for value in lines[line_index].split()[:2])\n        line_index += 1\n        return [[int(value) for value in lines[line_index + row].split()[:columns]] for row in range(rows)]\n    return scalar(schema)\n\ntry:\n    args = [parse(schema) for schema in SCHEMAS]\n    value = getattr(module, {callable_name!r})(*args)\n    if isinstance(value, bool):\n        print("true" if value else "false")\n    elif hasattr(value, "isoformat"):\n        print(value.isoformat())\n    elif isinstance(value, (list, tuple)):\n        print(" ".join(str(item) for item in value))\n    elif isinstance(value, dict) and set(value) == {{"error"}}:\n        print(value["error"])\n    else:\n        print(value, end="" if str(value).endswith("\\n") else "\\n")\nexcept Exception as exc:\n    print(str(exc), file=sys.stderr)\n    raise\n''',
        encoding="utf-8",
    )
    return [sys.executable, adapter.name], []


def _c_family_adapter(temp: Path, paths: list[Path], sample: dict, config: dict, language: str) -> tuple[list[str], list[str]] | None:
    schemas = config.get("input_schema") or []
    callable_name = str(config.get("callable") or "")
    if len(schemas) > 1 or any(isinstance(schema, dict) for schema in schemas) or not re.fullmatch(r"[A-Za-z_]\w*", callable_name):
        return None
    header = next((path.name for path in paths if path.suffix in {".h", ".hpp"}), None)
    source_exts = {".cpp", ".cc", ".cxx"} if language == "C++" else {".c"}
    sources = [path for path in paths if path.suffix in source_exts]
    if not header or not sources:
        return None
    namespaces = re.findall(r"\bnamespace\s+([A-Za-z_]\w*)\s*\{", "\n".join(path.read_text(encoding="utf-8") for path in paths))
    call = f"{namespaces[0]}::{callable_name}" if language == "C++" and namespaces else callable_name
    output = config.get("output_schema")
    argument = "value" if schemas else ""
    if output in {"integer", "number"}:
        declaration, invoke, print_value = "long long result;", f"result = {call}({argument});", 'printf("%lld\\n", result);'
    elif output == "boolean":
        declaration, invoke, print_value = "int result;", f"result = {call}({argument});", 'printf("%s\\n", result ? "true" : "false");'
    elif language == "C++":
        declaration, invoke, print_value = "std::string result;", f"result = {call}({argument});", "std::cout << result << std::endl;"
    else:
        declaration, invoke, print_value = "char *result;", f"result = {call}({argument});", "fputs(result, stdout); putchar('\\n'); free(result);"
    if schemas and schemas[0] == "integer":
        input_decl, read_input = "unsigned int value;", "if (scanf(\"%u\", &value) != 1) return 2;"
    elif schemas and schemas[0] == "number":
        input_decl, read_input = "double value;", "if (scanf(\"%lf\", &value) != 1) return 2;"
    elif schemas:
        input_decl, read_input = "char value[5000] = {0};", 'if (!fgets(value, sizeof(value), stdin)) value[0] = 0; value[strcspn(value, "\\r\\n")] = 0;'
    else:
        input_decl, read_input = "int value = 0;", "(void)value;"
    includes = f'#include "{header}"\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n'
    if language == "C++":
        includes += "#include <iostream>\n#include <string>\n"
    adapter_name = "__exercise_adapter.cpp" if language == "C++" else "__exercise_adapter.c"
    body = f"{includes}\nint main() {{ {input_decl} {read_input} {declaration} {invoke} {print_value} return 0; }}\n"
    (temp / adapter_name).write_text(body, encoding="utf-8")
    compiler = shutil.which("g++") if language == "C++" else shutil.which("gcc")
    command = [compiler or ("g++" if language == "C++" else "gcc"), "-std=c++17" if language == "C++" else "-std=c11", "-I.", *[path.name for path in sources], adapter_name, "-o", "exercise-adapter.exe"]
    return command, [str(temp / "exercise-adapter.exe")]


def _java_adapter(temp: Path, paths: list[Path], sample: dict, config: dict, manifest: dict) -> tuple[list[str], list[str]] | None:
    callable_name = str(config.get("callable") or "")
    if not callable_name:
        return None
    class_name, method_name = callable_name.rsplit(".", 1) if "." in callable_name else ("", callable_name)
    if not class_name:
        class_match = next((re.search(r"\bclass\s+([A-Za-z_$][\w$]*)", path.read_text(encoding="utf-8")) for path in paths if path.suffix == ".java"), None)
        class_name = class_match.group(1) if class_match else ""
    if not class_name:
        return None
    package_name = str(manifest.get("package_name") or "")
    qualified = f"{package_name}.{class_name}" if package_name else class_name
    package_line = f"package {package_name};\n" if package_name else ""
    adapter_rel = f"{package_name.replace('.', '/') + '/' if package_name else ''}__ExerciseAdapter.java"
    adapter = temp / adapter_rel
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(f'''{package_line}import java.lang.reflect.*;\nimport java.time.*;\nimport java.util.*;\npublic class __ExerciseAdapter {{\n  static Object parse(Class<?> type, String value) {{\n    if (type == String.class) return value;\n    if (type == int.class || type == Integer.class) return Integer.valueOf(value.trim());\n    if (type == long.class || type == Long.class) return Long.valueOf(value.trim());\n    if (type == LocalDate.class) return LocalDate.parse(value.trim());\n    if (type == LocalDateTime.class) return LocalDateTime.parse(value.trim());\n    if (type == boolean.class || type == Boolean.class) return Boolean.valueOf(value.trim());\n    return value;\n  }}\n  public static void main(String[] args) throws Exception {{\n    String input = new String(System.in.readAllBytes()).trim();\n    Class<?> target = Class.forName({qualified!r});\n    Method method = Arrays.stream(target.getDeclaredMethods()).filter(item -> item.getName().equals({method_name!r})).findFirst().orElseThrow();\n    method.setAccessible(true);\n    Object receiver = Modifier.isStatic(method.getModifiers()) ? null : target.getDeclaredConstructor().newInstance();\n    Object result = method.getParameterCount() == 0 ? method.invoke(receiver) : method.invoke(receiver, parse(method.getParameterTypes()[0], input));\n    if (result != null) System.out.println(result);\n  }}\n}}\n'''.replace("'", '"'), encoding="utf-8")
    java_sources = [path.name for path in paths if path.suffix == ".java"] + [adapter_rel]
    return ["javac", "-d", ".", *java_sources], ["java", "-cp", ".", f"{package_name + '.' if package_name else ''}__ExerciseAdapter"]


def run_sample(language: str, exercise, files: list, sample: dict, manifest: dict | None = None) -> dict | None:
    config = sample.get("adapter_config") or {}
    if config.get("protocol") != "stdin_stdout_v1":
        return None
    started = time.time()
    file_dicts = []
    for item in files:
        if hasattr(item, "relative_path"):
            file_dicts.append({"relative_path": item.relative_path, "content": item.content})
        else:
            file_dicts.append({"relative_path": item.get("relative_path"), "content": item.get("content")})
    with tempfile.TemporaryDirectory(prefix="programming-io-adapter-") as raw:
        temp = Path(raw)
        try:
            paths = _write_user_files(temp, file_dicts)
            language = str(language)
            if language == "Python":
                prepared = _python_adapter(temp, paths, sample, config)
            elif language in {"C", "C++"}:
                prepared = _c_family_adapter(temp, paths, sample, config, language)
            elif language == "Java":
                prepared = _java_adapter(temp, paths, sample, config, manifest or {})
            else:
                prepared = None
            if prepared is None:
                return None
            compile_command, run_command = prepared
            if language == "Python":
                proc = subprocess.run(compile_command, cwd=temp, input=str(sample.get("stdin_text") or ""), capture_output=True, text=True, timeout=6)
                return _result(sample, started, proc)
            compile_proc = subprocess.run(compile_command, cwd=temp, capture_output=True, text=True, timeout=30)
            if compile_proc.returncode != 0:
                return _result(sample, started, compile_proc, compile_proc.stderr or compile_proc.stdout)
            proc = subprocess.run(run_command, cwd=temp, input=str(sample.get("stdin_text") or ""), capture_output=True, text=True, timeout=6)
            return _result(sample, started, proc)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            return {
                "success": True, "passed": False, "passed_count": 0, "total_count": 1,
                "failed_categories": ["runtime"], "duration_ms": int((time.time() - started) * 1000),
                "stdout": "", "stderr": str(exc), "actual_output": "", "expected_output": sample.get("expected_stdout"),
                "actual_stdout": "", "expected_stdout": sample.get("expected_stdout"), "test_name": sample.get("name"),
                "exit_code": -1, "technical_details": str(exc),
            }
