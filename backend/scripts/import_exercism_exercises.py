"""Import a small, audited batch of Exercism exercises.

The source checkouts are intentionally external to the application repository.
Only MIT-licensed exercise metadata, starter files, public test files, and the
server-side reference/hidden data are copied into the database.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
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
CONCEPT_LABELS = {
    "basics": "基础语法", "conditionals": "条件判断", "loops": "循环", "functions": "函数",
    "strings": "字符串处理", "string-methods": "字符串方法", "lists": "列表", "list-methods": "列表操作",
    "dicts": "字典", "dict-methods": "字典操作", "sets": "集合", "comprehensions": "推导式",
    "regular-expressions": "正则表达式", "exceptions": "异常处理", "classes": "类与对象",
    "class-composition": "类组合", "class-customization": "类定制", "class-inheritance": "类继承",
    "numbers": "数值运算", "integers": "整数运算", "sequences": "序列", "arrays": "数组",
    "pointers": "指针", "memory": "内存管理", "memory-management": "内存管理", "structures": "结构体",
    "structs": "结构体", "enums": "枚举", "bitwise-operations": "位运算", "booleans": "布尔逻辑",
    "bools": "布尔逻辑", "comparisons": "比较运算", "logic": "逻辑运算", "math": "数值算法",
    "filtering": "过滤", "sorting": "排序", "searching": "查找", "algorithms": "算法",
    "recursion": "递归", "stacks": "栈", "buffers": "缓冲区", "lists": "列表",
    "flexible-array-members": "柔性数组", "function-pointers": "函数指针", "variable-argument-lists": "可变参数",
    "control-flow-case-statements": "条件判断", "control-flow-if-statements": "条件判断",
    "control-flow-if-else-statements": "条件判断", "control-flow-loops": "循环",
    "control-flow-loops-switch-if-statements": "循环与分支", "text-formatting": "文本格式化",
    "dates": "日期处理", "time": "时间处理", "time-functions": "时间函数",
    "performance-optimizations": "性能优化", "preprocessor-x-macros-in-test": "预处理器宏",
    "stl": "STL 容器", "vector-arrays": "vector 容器", "iterators": "迭代器", "maps": "映射容器",
    "data-structures": "数据结构", "templates": "模板", "namespaces": "命名空间", "includes": "头文件",
    "headers": "头文件", "auto": "类型推导", "references": "引用", "smart-pointers": "智能指针",
    "operator-overloading": "运算符重载", "exceptions": "异常处理", "interfaces": "接口",
    "parsing": "解析", "pattern-matching": "模式匹配", "pattern-recognition": "模式识别",
    "regular-expressions": "正则表达式", "switch": "switch 分支", "threads": "线程",
    "variables": "变量", "optional-values": "可选值", "pairs": "键值对", "randomness": "随机数",
    "string-formatting": "字符串格式化", "generator-expressions": "生成器表达式", "generators": "生成器",
    "decorators": "装饰器", "descriptors": "描述器", "function-arguments": "函数参数",
    "higher-order-functions": "高阶函数", "iteration": "迭代", "iterators": "迭代器", "itertools": "迭代工具",
    "functools": "函数工具", "none": "None 值", "operator-overloading": "运算符重载",
    "raising-and-handling-errors": "异常处理", "rich-comparisons": "比较运算",
    "unpacking-and-multiple-assignment": "解包与多重赋值", "user-defined-errors": "自定义异常",
    "with-statement": "上下文管理",
    "character-mapping": "字符映射", "validation-algorithm": "校验算法",
    "if-statements": "条件判断", "literals": "字面量", "tuples": "元组",
    "collections": "集合与容器", "other-comprehensions": "推导式",
    "list-comprehensions": "推导式", "context-manager-customization": "上下文管理",
}

CONCEPT_LABELS.update({
    "methods": "函数与方法", "chars": "字符", "for-loops": "循环", "foreach-loops": "循环",
    "if-else-statements": "条件判断", "switch-statement": "switch 分支", "datetime": "日期与时间",
    "collections": "集合", "interfaces": "接口", "inheritance": "继承", "generics": "泛型",
    "streams": "Stream API", "maps": "Map", "sets": "Set", "enums": "枚举",
})

JAVA_SAMPLE_NAMES_ZH = {
    "Say Hi!": "返回问候语",
    "a word": "反转普通单词",
    "an empty string": "处理空字符串",
    "a capitalized word": "处理首字母大写单词",
    "a sentence with punctuation": "处理带标点的句子",
    "a palindrome": "处理回文字符串",
    "an even-sized word": "处理偶数长度单词",
    "full time specified": "完整日期时间输入",
    "date only specification of time": "日期输入测试",
    "third test for date only specification of time": "日期输入边界测试（三）",
    "second test for date only specification of time": "日期输入边界测试（二）",
    "full time with day roll-over": "跨天日期时间计算",
    "does not mutate the input": "不修改原始日期时间",
}


def run(command: list[str], cwd: Path, timeout: int = 90) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    return result.returncode == 0, output[-4000:]


def python_test_command() -> list[str]:
    if importlib.util.find_spec("pytest") is not None:
        return [sys.executable, "-m", "pytest", "-q"]
    if os.name == "nt":
        return ["py", "-3.13", "-m", "pytest", "-q"]
    return [sys.executable, "-m", "unittest", "discover", "-v", "-p", "*_test.py"]


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


def normalize_test_files(language: str, test_files: list[dict]) -> list[dict]:
    if language != "C":
        # Do not let official runner support files be appended to the caller's
        # public/business test list.  C++'s Catch2 headers must stay server
        # side and must never participate in sample or concept extraction.
        return [dict(item) for item in test_files]
    return [
        {
            **item,
            "content": re.sub(r"(?m)^\s*TEST_IGNORE\(\);[^\n]*\n?", "", str(item.get("content") or "")),
        }
        for item in test_files
    ]


def java_enabled_test_content(content: str) -> str:
    """Enable the full official Java suite only inside an isolated runner."""
    return re.sub(r"(?m)^\s*@Disabled(?:\([^\n]*\))?\s*\n", "", str(content or ""))


def official_test_bundle(language: str, exercise_dir: Path, test_files: list[dict]) -> list[dict]:
    """Include the track's test runner support without exposing it as starter code."""
    result = normalize_test_files(language, test_files)
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


def localized_tags(language: str, tags: list[str]) -> list[str]:
    result = []
    for tag in tags:
        normalized = str(tag).strip().lower().replace("_", "-")
        label = CONCEPT_LABELS.get(normalized)
        if not label:
            continue
        if label not in result:
            result.append(label)
    if len(result) > 1:
        result = [item for item in result if item != "基础语法"]
    for preferred in ("字符映射", "校验算法"):
        if preferred in result:
            result.remove(preferred)
            result.insert(0, preferred)
    if "校验算法" in result and "字符串处理" in result:
        result.remove("字符串处理")
        result.insert(1, "字符串处理")
    return result[:4]


def source_derived_tags(language: str, starter_files: list[dict], reference_files: list[dict], test_files: list[dict]) -> list[str]:
    """Add only concepts evidenced by the official solution/test source."""
    implementation_text = "\n".join(
        str(item.get("content") or "")
        for item in [*starter_files, *reference_files]
    )
    test_text = "\n".join(str(item.get("content") or "") for item in test_files)
    tags = []
    if language == "Python":
        nodes = []
        for item in [*starter_files, *reference_files]:
            try:
                nodes.extend(ast.walk(ast.parse(str(item.get("content") or ""))))
            except SyntaxError:
                continue
        node_types = {type(node) for node in nodes}
        if ast.FunctionDef in node_types or ast.AsyncFunctionDef in node_types:
            tags.append("functions")
        if ast.For in node_types or ast.While in node_types:
            tags.append("loops")
        if ast.If in node_types:
            tags.append("conditionals")
        if ast.List in node_types:
            tags.append("lists")
        if ast.Dict in node_types:
            tags.append("dicts")
        if ast.Set in node_types:
            tags.append("sets")
        if any(isinstance(node, ast.Constant) and isinstance(node.value, str) for node in nodes):
            tags.append("strings")
        if any(isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex)) for node in nodes):
            tags.append("numbers")
    elif language == "C++":
        if re.search(r"\b[A-Za-z_:<>]+\s+[A-Za-z_]\w*\s*\([^;{}]*\)\s*(?:const\s*)?\{", implementation_text):
            tags.append("functions")
        if re.search(r"\bnamespace\s+[A-Za-z_]", implementation_text):
            tags.append("namespaces")
        if re.search(r"\b(?:std::)?string\b|[\"'](?:[^\"']|\\.)+[\"']", implementation_text):
            tags.append("strings")
        if re.search(r"\b(?:for|while)\s*\(", implementation_text):
            tags.append("loops")
        if re.search(r"\b(?:if|else\s+if|switch)\s*\(", implementation_text):
            tags.append("conditionals")
        if re.search(r"\b(?:valid|is_valid|verify)\w*\b", test_text, re.IGNORECASE):
            tags.append("validation-algorithm")
    elif language == "C":
        if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\([^;{}]*\)\s*\{", implementation_text):
            tags.append("functions")
        if re.search(r"\bchar\b[\s\S]{0,180}(?:\[[^]]*\]|\*\w+)", implementation_text):
            tags.append("strings")
        if re.search(r"['\"](?:A|C|G|T|U)['\"]", implementation_text):
            tags.append("character-mapping")
        if re.search(r"\b(?:for|while)\s*\(", implementation_text):
            tags.append("loops")
        if re.search(r"\b(?:if|else\s+if|switch)\s*\(", implementation_text):
            tags.append("conditionals")
    elif language == "Java":
        if re.search(r"\b(?:public|private|protected)?\s*(?:static\s+)?[A-Za-z_$][\w$<>\[\]]*\s+[A-Za-z_$][\w$]*\s*\([^;{}]*\)", implementation_text):
            tags.append("methods")
        if re.search(r"\bclass\s+[A-Za-z_$][\w$]*", implementation_text):
            tags.append("classes")
        if re.search(r"\b(?:interface|implements)\b", implementation_text):
            tags.append("interfaces")
        if re.search(r"\b(?:extends|super)\b", implementation_text):
            tags.append("inheritance")
        if re.search(r"\b(?:List|ArrayList|Collection|Map|HashMap|Set|HashSet)\b", implementation_text):
            tags.append("collections")
        if re.search(r"\b(?:LocalDate|LocalDateTime|Instant|Duration|Period|ZonedDateTime)\b|java\.time", implementation_text):
            tags.append("datetime")
        if re.search(r"\b(?:try|catch|throw|throws)\b", implementation_text):
            tags.append("exceptions")
        if re.search(r"\b(?:for|while|do)\b", implementation_text):
            tags.append("loops")
        if re.search(r"\b(?:if|else|switch|case)\b", implementation_text):
            tags.append("conditionals")
        if re.search(r"\b(?:String|char|Character)\b|\"(?:[^\"]|\\.)*\"", implementation_text):
            tags.append("strings")
        if re.search(r"\b(?:enum|Enum)\b", implementation_text):
            tags.append("enums")
    elif language == "Python":
        if re.search(r"\b(?:for|while)\b", text):
            tags.append("loops")
        if re.search(r"\bif\b|\belif\b", text):
            tags.append("conditionals")
        if re.search(r"\[[^\]]*\]|\blist\s*\(", text):
            tags.append("lists")
        if re.search(r"\{[^\n]*:\s*[^\n]*\}", text):
            tags.append("dicts")
        if re.search(r"\bstr\b|[\"'](?:[^\"']|\\.)+[\"']", text):
            tags.append("strings")
        if re.search(r"\b(?:int|float)\b|\b\d+(?:\.\d+)?\b", text):
            tags.append("numbers")
    return tags


def _display_value(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _test_selectors(language: str, test_files: list[dict]) -> list[dict]:
    """Find real test entry points without exposing test framework source."""
    selectors = []
    for item in test_files:
        path = str(item.get("path") or "")
        content = str(item.get("content") or "")
        if language == "Python" and path.endswith(".py"):
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    selectors.append({"path": path, "selector": node.name})
                elif isinstance(node, ast.ClassDef):
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                            selectors.append({"path": path, "selector": f"{node.name}::{child.name}"})
        elif language == "C++" and path.endswith(('.cpp', '.cc', '.cxx')):
            for match in re.finditer(r"\bTEST_CASE(?:_METHOD)?\s*\(\s*\"([^\"]+)\"(?:\s*,\s*\"\[([^\"]+)\]\")?", content):
                selectors.append({"path": path, "selector": match.group(1), "case_id": match.group(2)})
        elif language == "C" and path.endswith(".c") and "test-framework/" not in path:
            for match in re.finditer(r"(?:static\s+)?void\s+(test_[A-Za-z0-9_]+)\s*\(", content):
                selectors.append({"path": path, "selector": match.group(1)})
        elif language == "Java" and path.endswith(".java") and "/test/" in ("/" + path.replace("\\", "/")):
            class_match = re.search(r"\bclass\s+([A-Za-z_$][\w$]*)", content)
            class_name = class_match.group(1) if class_match else Path(path).stem
            pending_display = None
            pending_test = False
            for line in content.splitlines():
                if re.search(r"@Test\b", line):
                    pending_test = True
                display_match = re.search(r"@DisplayName\(\s*\"([^\"]+)\"\s*\)", line)
                if display_match:
                    pending_display = display_match.group(1)
                    continue
                method_match = re.search(r"\b(?:public\s+)?void\s+([A-Za-z_$][\w$]*)\s*\(", line)
                if method_match and pending_test:
                    method_name = method_match.group(1)
                    selectors.append({
                        "path": path,
                        "selector": f"{class_name}.{method_name}",
                        "source_test_name": method_name,
                        "display_name": pending_display or method_name,
                    })
                    pending_display = None
                    pending_test = False
    return selectors


def canonical_samples(problem_root: Path | None, language: str, slug: str, test_files: list[dict]) -> list[dict]:
    if not problem_root:
        return []
    path = problem_root / "exercises" / slug / "canonical-data.json"
    if not path.is_file():
        return []
    try:
        cases = read_json(path).get("cases", [])
    except (OSError, ValueError, TypeError):
        return []
    selectors = _test_selectors(language, test_files)
    # canonical-data.json may group several leaf cases under one property
    # (for example grains.square).  Only leaf cases map to runnable test
    # selectors; importing the group itself produces a misleading null
    # expected value and shifts every following selector.
    leaf_cases = []
    for group in cases:
        nested = group.get("cases") if isinstance(group, dict) else None
        if isinstance(nested, list):
            for child in nested:
                if isinstance(child, dict):
                    leaf = dict(child)
                    if not leaf.get("property") and group.get("property"):
                        leaf["property"] = group["property"]
                    leaf_cases.append(leaf)
        elif isinstance(group, dict):
            leaf_cases.append(group)

    samples = []
    remaining_selectors = list(selectors)
    stop_words = {"a", "an", "and", "as", "be", "can", "is", "of", "on", "the", "to", "with"}
    for index, case in enumerate(leaf_cases):
        selector = next((item for item in remaining_selectors if item.get("case_id") == case.get("uuid")), None)
        if selector is not None:
            remaining_selectors.remove(selector)
        else:
            description_words = set(re.findall(r"[a-z]+", str(case.get("description") or "").lower())) - stop_words
            description_numbers = set(re.findall(r"-?\d+", str(case.get("description") or "")))
            ranked = []
            for candidate in remaining_selectors:
                candidate_text = str(candidate.get("selector") or "").lower()
                candidate_words = set(re.findall(r"[a-z]+", candidate_text))
                candidate_numbers = set(re.findall(r"-?\d+", candidate_text))
                if description_numbers and not description_numbers.issubset(candidate_numbers):
                    continue
                if "negative" in description_words and "negative" not in candidate_words:
                    continue
                score = len(description_words & candidate_words)
                if score:
                    ranked.append((score, candidate))
            if ranked:
                selector = max(ranked, key=lambda item: item[0])[1]
                remaining_selectors.remove(selector)
            elif not description_numbers and "negative" not in description_words and remaining_selectors:
                # Some tracks use a human-readable canonical description that
                # does not share words with the test function (e.g. hello-world).
                # Preserve order only when there is no numeric constraint that
                # could silently bind this sample to the wrong test.
                selector = remaining_selectors.pop(0)
        if selector is None:
            # The canonical specification can contain cases omitted by a
            # language track (for example negative grains in C).  Do not
            # fabricate a selector for such a case.
            continue
        input_value = case.get("input") or {}
        raw_name = str(case.get("description") or f"官方测试 {index + 1}")
        samples.append({
            "id": str(case.get("uuid") or f"{slug}-{len(samples) + 1}"),
            "name": JAVA_SAMPLE_NAMES_ZH.get(raw_name, raw_name) if language == "Java" else raw_name,
            "arguments": list(input_value.values()) if isinstance(input_value, dict) else [input_value],
            "input_display": "无参数" if not input_value else _display_value(input_value),
            "expected": _display_value(case.get("expected")),
            "source_test_name": selector.get("source_test_name") or selector["selector"],
            "test_path": selector["path"],
            "selector": selector["selector"],
        })
    return samples


def find_exercise(repo_dir: Path, slug: str) -> tuple[Path | None, str | None]:
    for track in ("concept", "practice"):
        path = repo_dir / "exercises" / track / slug
        if path.is_dir():
            return path, track
    return None, None


def audit_reference(language: str, exercise_dir: Path, starter_files: list[dict], reference_files: list[dict], test_files: list[dict]) -> tuple[bool, dict]:
    if not reference_files or not test_files:
        return False, {"reference": "missing reference or official tests"}
    with tempfile.TemporaryDirectory(prefix="exercism-audit-") as raw:
        temp = Path(raw) / exercise_dir.name
        shutil.copytree(exercise_dir, temp)
        for item in starter_files:
            target = temp / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
        for item in reference_files:
            target = temp / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
        for item in test_files:
            target = temp / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            content = java_enabled_test_content(item["content"]) if language == "Java" else item["content"]
            target.write_text(content, encoding="utf-8")
        commands = {
            "Python": python_test_command(),
            "C": ["gcc", "-std=c99", "-DEXERCISM_RUN_ALL_TESTS", "-DUNITY_SUPPORT_64", "-DUNITY_OUTPUT_COLOR", "test-framework/unity.c", "-o", "tests.exe"],
        }
        if language == "C++":
            cpp_sources = [str(item["path"]) for item in reference_files if str(item.get("path", "")).endswith((".cpp", ".cc", ".cxx"))]
            test_contents = [item for item in test_files if str(item.get("path", "")).endswith((".cpp", ".cc", ".cxx"))]
            included_sources = {
                match.group(1).replace("\\", "/")
                for item in test_contents
                for match in re.finditer(r'#include\s+"([^" ]+\.c(?:pp|cxx)?)"', str(item.get("content") or ""))
            }
            included_names = {Path(item).name for item in included_sources}
            cpp_sources = [path for path in cpp_sources if path.replace("\\", "/") not in included_sources and Path(path).name not in included_names]
            cpp_sources.extend(str(item["path"]) for item in test_contents)
            runner = temp / "test" / "tests-main.cpp"
            if runner.is_file():
                cpp_sources.append(str(runner.relative_to(temp)))
            unique_cpp_sources = []
            seen_cpp_sources = set()
            for path in cpp_sources:
                key = str(Path(path)).replace("\\", "/").lower()
                if key in seen_cpp_sources:
                    continue
                seen_cpp_sources.add(key)
                unique_cpp_sources.append(path)
            cpp_sources = unique_cpp_sources
            ok, output = run(["g++", "-std=c++17", "-DEXERCISM_RUN_ALL_TESTS", "-I.", *cpp_sources, "-o", "exercise-tests.exe"], temp)
            if ok:
                ok, output = run([str(temp / "exercise-tests.exe")], temp)
        elif language == "C":
            sources = [str(item["path"]) for item in reference_files if str(item.get("path", "")).endswith(".c")]
            tests = [str(item["path"]) for item in test_files if str(item.get("path", "")).startswith("test_") and str(item.get("path", "")).endswith(".c")]
            ok, output = run(["gcc", "-std=c99", "-DEXERCISM_RUN_ALL_TESTS", "-I.", *sources, *tests, "test-framework/unity.c", "-lm", "-o", "tests.exe"], temp)
            if ok:
                ok, output = run([str(temp / "tests.exe")], temp)
        elif language == "Java":
            gradle_wrapper = temp / ("gradlew.bat" if os.name == "nt" else "gradlew")
            if gradle_wrapper.is_file():
                if os.name != "nt":
                    gradle_wrapper.chmod(gradle_wrapper.stat().st_mode | 0o111)
                ok, output = run([str(gradle_wrapper), "test", "--no-daemon"], temp)
            else:
                ok, output = run(["gradle", "test", "--no-daemon"], temp)
        else:
            ok, output = run(commands[language], temp)
        report = {"reference": "pass" if ok else "fail", "output": output}
        if language == "Java" and ok:
            mutated = False
            for item in reference_files:
                target = temp / item["path"]
                original = target.read_text(encoding="utf-8")
                wrong, replacements = re.subn(
                    r"(?m)^(\s*return\s+)(?!;)([^;]+);",
                    r"\1null;",
                    original,
                    count=1,
                )
                if replacements:
                    target.write_text(wrong, encoding="utf-8")
                    mutated = True
                    break
            if mutated:
                wrong_ok, wrong_output = run(
                    [str(gradle_wrapper), "test", "--no-daemon"] if gradle_wrapper.is_file() else ["gradle", "test", "--no-daemon"],
                    temp,
                )
                report["wrong_solution_rejected"] = not wrong_ok
                report["wrong_solution_output"] = wrong_output
            else:
                report["wrong_solution_rejected"] = False
                report["wrong_solution_output"] = "No deterministic mutation was applied"
        return ok and report.get("wrong_solution_rejected", True), report


def starter_compile(language: str, starter_files: list[dict], exercise_dir: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory(prefix="exercism-starter-") as raw:
        temp = Path(raw)
        for item in starter_files:
            target = temp / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"], encoding="utf-8")
        source_paths = [str(temp / item["path"]) for item in starter_files]
        if language == "Python":
            return run([sys.executable, "-m", "py_compile", *source_paths], temp)
        if language == "C":
            return run(["gcc", "-fsyntax-only", *source_paths], temp)
        if language == "C++":
            return run(["g++", "-std=c++17", "-fsyntax-only", *source_paths], temp)
        return run(["javac", *source_paths], temp)


def import_language(
    db,
    source_root: Path,
    language: str,
    max_count: int,
    requested_slugs: list[str] | None = None,
    prune_unlisted: bool = False,
    problem_root: Path | None = None,
) -> dict:
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
    imported_source_keys = set()
    audited = []
    skipped = []
    for item in candidates:
        if imported >= max_count:
            break
        exercise_dir, track = find_exercise(repo_dir, item["slug"])
        if not exercise_dir:
            skipped.append({"slug": item["slug"], "reason": "exercise directory missing"})
            continue
        config_path = exercise_dir / ".meta" / "config.json"
        if not config_path.is_file():
            skipped.append({"slug": item["slug"], "reason": "metadata config missing"})
            continue
        config = read_json(config_path)
        starter = files_from_config(exercise_dir, config, "solution")
        starter.extend(files_from_config(exercise_dir, config, "editor"))
        reference = reference_files_from_config(exercise_dir, config)
        tests = files_from_config(exercise_dir, config, "test")
        if not starter or not reference or not tests:
            skipped.append(
                {
                    "slug": item["slug"],
                    "reason": {
                        "starter_files": len(starter),
                        "reference_files": len(reference),
                        "test_files": len(tests),
                    },
                }
            )
            continue
        official_tests = official_test_bundle(language, exercise_dir, tests)
        compile_ok, compile_output = starter_compile(language, starter, exercise_dir)
        reference_ok, reference_report = audit_reference(language, exercise_dir, starter, reference, normalize_test_files(language, tests))
        audit = {"starter_compile": "pass" if compile_ok else "fail", "reference_tests": reference_report, "ai_hidden_tests": 0}
        audited.append({"slug": item["slug"], "audit": audit})
        if not compile_ok or not reference_ok:
            skipped.append(
                {
                    "slug": item["slug"],
                    "reason": {
                        "starter_compile": compile_output[-1200:],
                        "reference_tests": reference_report,
                    },
                }
            )
            continue
        instructions = exercise_dir / ".docs" / "instructions.md"
        description = instructions.read_text(encoding="utf-8") if instructions.is_file() else config.get("blurb", "")
        raw_tags = []
        for key in ("concepts", "practices", "prerequisites", "topics"):
            raw_tags.extend(item.get(key) or [])
        raw_tags = list(dict.fromkeys(raw_tags))
        raw_tags.extend(source_derived_tags(language, starter, reference, tests))
        tags = localized_tags(language, raw_tags)
        if not tags:
            skipped.append({"slug": item["slug"], "reason": "official concepts/topics missing or unmapped"})
            continue
        hidden_tests = normalize_test_files(language, tests)
        samples = canonical_samples(problem_root, language, item["slug"], tests)
        samples_by_path = {}
        for sample in samples:
            samples_by_path.setdefault(sample["test_path"], []).append(sample)
        public_tests = [
            {"path": test["path"], "content": test["content"], "samples": samples_by_path.get(test["path"], [])}
            for test in tests
        ]
        manifest = {
            "language": language.lower(),
            "exercise_id": item["slug"],
            "editable_files": [str(entry.get("path") or "") for entry in starter],
            "support_files": [],
            "test_files": [str(entry.get("path") or "") for entry in tests],
            "package_name": next(
                (
                    match.group(1)
                    for entry in starter
                    for match in [re.search(r"(?m)^\s*package\s+([\w.]+)\s*;", str(entry.get("content") or ""))]
                    if match
                ),
                "",
            ),
            "test_framework": "junit5" if language == "Java" else None,
            "build_type": "gradle" if language == "Java" else None,
        }
        audit["manifest"] = manifest
        payload = {
            "slug": f"{language.lower().replace('+', 'p')}-{item['slug']}",
            "source_key": f"https://github.com/exercism/{repo}|{language}|{item['slug']}",
            "language": language,
            "title": item.get("name") or item["slug"].replace("-", " ").title(),
            "difficulty": difficulty_for(item, imported),
            "tags_json": json.dumps(tags, ensure_ascii=False),
            "description": description,
            "starter_files_json": json.dumps(starter, ensure_ascii=False),
            "reference_files_json": json.dumps(reference, ensure_ascii=False),
            "public_tests_json": json.dumps(public_tests, ensure_ascii=False),
            "hidden_tests_json": json.dumps(hidden_tests, ensure_ascii=False),
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
        existing = (
            db.query(models.ProgrammingExercise)
            .filter(
                (models.ProgrammingExercise.source_key == payload["source_key"])
                | (models.ProgrammingExercise.slug == payload["slug"])
            )
            .order_by(models.ProgrammingExercise.id.asc())
            .first()
        )
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
        else:
            db.add(models.ProgrammingExercise(**payload))
        imported_source_keys.add(payload["source_key"])
        imported += 1
    if prune_unlisted:
        expected_source_keys = {
            f"https://github.com/exercism/{repo}|{language}|{slug}"
            for slug in (requested_slugs or [])
        }
        if imported_source_keys != expected_source_keys:
            missing_source_keys = sorted(expected_source_keys - imported_source_keys)
            raise RuntimeError(
                f"Refusing to prune {language}: audited import set is incomplete "
                f"({len(imported_source_keys)}/{len(expected_source_keys)}); "
                f"missing={json.dumps(missing_source_keys, ensure_ascii=False)}; "
                f"skipped={json.dumps(skipped, ensure_ascii=False)}"
            )
        db.query(models.ProgrammingExercise).filter(
            models.ProgrammingExercise.language == language,
            (
                models.ProgrammingExercise.source_key.is_(None)
                | ~models.ProgrammingExercise.source_key.in_(expected_source_keys)
            ),
        ).delete(synchronize_session=False)
    db.commit()
    return {
        "language": language,
        "imported": imported,
        "audited": audited,
        "pruned_unlisted": prune_unlisted,
        "license": "MIT",
        "commit": commit,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--max-per-language", type=int, default=20)
    parser.add_argument("--languages", default=",".join(LANGUAGE_REPOS))
    parser.add_argument("--slugs", default="", help="Optional comma-separated exercise slugs to audit first")
    parser.add_argument(
        "--prune-unlisted",
        action="store_true",
        help="After a complete requested batch passes audit, remove other rows for those languages",
    )
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        selected = [item.strip() for item in args.languages.split(",") if item.strip() in LANGUAGE_REPOS]
        requested = [item.strip() for item in args.slugs.split(",") if item.strip()]
        report = [
            import_language(
                db,
                Path(args.source_root),
                language,
                args.max_per_language,
                requested,
                args.prune_unlisted,
                Path(args.source_root) / "problem-specifications",
            )
            for language in selected
        ]
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
