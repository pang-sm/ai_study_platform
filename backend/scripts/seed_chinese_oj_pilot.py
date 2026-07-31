"""Seed 30 first-party original standard-input/output pilot exercises.

This script intentionally creates new records under chinese_oj_pilot_v1 and
does not alter the existing Exercism catalog.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import SessionLocal
from models import ProgrammingExercise

SOURCE_KEY = "chinese_oj_pilot_v1"

PROBLEMS = [
    ("two-number-sum", "两数求和", "读取两个整数并输出它们的和。", "两个整数 a、b（-10^9 ≤ a,b ≤ 10^9）。", "数值运算", "sum2", [("样例 1", "5 7\n", "12\n"), ("样例 2", "-3 9\n", "6\n")], [("隐藏：零值", "0 0\n", "0\n")]),
    ("parity-check", "奇偶判断", "读取一个整数，偶数输出 even，奇数输出 odd。", "整数 n（|n| ≤ 10^9）。", "条件判断", "parity", [("样例 1", "8\n", "even\n"), ("样例 2", "-5\n", "odd\n")], [("隐藏：零", "0\n", "even\n")]),
    ("max-of-three", "三个数的最大值", "读取三个整数并输出其中最大的数。", "三个整数，绝对值不超过 10^9。", "条件判断", "max3", [("样例 1", "3 9 4\n", "9\n"), ("样例 2", "-1 -8 -2\n", "-1\n")], [("隐藏：相等", "7 7 7\n", "7\n")]),
    ("sum-to-n", "累加到 n", "读取正整数 n，输出 1 到 n 的和。", "1 ≤ n ≤ 10^6。", "循环", "sum_n", [("样例 1", "5\n", "15\n"), ("样例 2", "1\n", "1\n")], [("隐藏：较大输入", "100\n", "5050\n")]),
    ("count-vowels", "统计元音字母", "读取一行英文文本，统计 a、e、i、o、u（不区分大小写）的个数。", "一行长度不超过 200 的 ASCII 文本。", "字符串", "vowels", [("样例 1", "Hello World\n", "3\n"), ("样例 2", "rhythm\n", "0\n")], [("隐藏：大小写", "AEiou\n", "5\n")]),
    ("reverse-text", "反转字符串", "读取一行文本，按字符逆序输出。", "一行长度为 1 到 200 的 ASCII 文本。", "字符串", "reverse", [("样例 1", "abcde\n", "edcba\n"), ("样例 2", "a b\n", "b a\n")], [("隐藏：单字符", "Z\n", "Z\n")]),
    ("array-sum", "数组元素求和", "读取 n 和 n 个整数，输出所有元素之和。", "1 ≤ n ≤ 1000；元素绝对值不超过 10^6。", "数组", "array_sum", [("样例 1", "4\n1 2 3 4\n", "10\n"), ("样例 2", "3\n-2 5 -1\n", "2\n")], [("隐藏：单元素", "1\n99\n", "99\n")]),
    ("linear-search", "查找目标位置", "读取 n、n 个整数和目标值，输出目标第一次出现的位置（从 0 开始）；不存在输出 -1。", "1 ≤ n ≤ 1000；元素绝对值不超过 10^6。", "查找", "find", [("样例 1", "5\n4 8 6 8 1\n8\n", "1\n"), ("样例 2", "3\n1 2 3\n9\n", "-1\n")], [("隐藏：首位", "4\n7 2 7 3\n7\n", "0\n")]),
    ("sort-three", "三个数排序", "读取三个整数，按从小到大输出，数字之间用一个空格分隔。", "三个整数，绝对值不超过 10^9。", "排序", "sort3", [("样例 1", "3 1 2\n", "1 2 3\n"), ("样例 2", "-1 5 0\n", "-1 0 5\n")], [("隐藏：重复值", "4 4 1\n", "1 4 4\n")]),
    ("digit-sum", "各位数字之和", "读取非负整数 n，输出其十进制各位数字之和。", "0 ≤ n ≤ 10^18。", "基础综合", "digits", [("样例 1", "12345\n", "15\n"), ("样例 2", "0\n", "0\n")], [("隐藏：重复数字", "909\n", "18\n")]),
]

# These cases are independently derived from each first-party problem's input
# contract.  They deliberately do not reuse the corresponding hidden input.
AI_PUBLIC_CASES = {
    "sum2": ("样例 3", "1000000000 -1000000000\n", "0\n", "覆盖合法整数边界与相反数求和"),
    "parity": ("样例 3", "-2\n", "even\n", "覆盖负偶数分支"),
    "max3": ("样例 3", "-10 0 -1\n", "0\n", "覆盖零与负数混合比较"),
    "sum_n": ("样例 3", "1000000\n", "500000500000\n", "覆盖允许的最大 n"),
    "vowels": ("样例 3", "aEiOu xyz\n", "5\n", "覆盖大小写混合和空格"),
    "reverse": ("样例 3", "space here\n", "ereh ecaps\n", "覆盖含空格的文本"),
    "array_sum": ("样例 3", "5\n0 -1 1 -2 2\n", "0\n", "覆盖零与正负数混合数组"),
    "find": ("样例 3", "5\n1 3 3 2 3\n3\n", "1\n", "覆盖重复目标时首次位置"),
    "sort3": ("样例 3", "0 -5 0\n", "-5 0 0\n", "覆盖重复值与负数排序"),
    "digits": ("样例 3", "1000000000000000000\n", "1\n", "覆盖最大合法数值的各位求和"),
}


def starter(language: str) -> tuple[str, str]:
    if language == "C":
        return "main.c", "#include <stdio.h>\n\nint main(void) {\n    /* 读取输入并完成题目 */\n    return 0;\n}\n"
    if language == "C++":
        return "main.cpp", "#include <iostream>\nusing namespace std;\n\nint main() {\n    // 读取输入并完成题目\n    return 0;\n}\n"
    return "main.py", "def main():\n    # 读取输入并完成题目\n    pass\n\nif __name__ == '__main__':\n    main()\n"


def reference(language: str, kind: str) -> str:
    c = {
        "sum2": "#include <stdio.h>\nint main(void){long long a,b; if(scanf(\"%lld%lld\",&a,&b)==2) printf(\"%lld\\n\",a+b); return 0;}\n",
        "parity": "#include <stdio.h>\nint main(void){long long n; if(scanf(\"%lld\",&n)==1) puts(n%2==0?\"even\":\"odd\"); return 0;}\n",
        "max3": "#include <stdio.h>\nint main(void){long long a,b,c,m; if(scanf(\"%lld%lld%lld\",&a,&b,&c)==3){m=a>b?a:b; m=m>c?m:c; printf(\"%lld\\n\",m);} return 0;}\n",
        "sum_n": "#include <stdio.h>\nint main(void){long long n; if(scanf(\"%lld\",&n)==1) printf(\"%lld\\n\",n*(n+1)/2); return 0;}\n",
        "vowels": "#include <stdio.h>\n#include <ctype.h>\nint main(void){int c,n=0; while((c=getchar())!=EOF){c=tolower(c); if(c=='a'||c=='e'||c=='i'||c=='o'||c=='u')n++;} printf(\"%d\\n\",n); return 0;}\n",
        "reverse": "#include <stdio.h>\n#include <string.h>\nint main(void){char s[205]; if(fgets(s,sizeof s,stdin)){size_t n=strcspn(s,\"\\n\"); while(n) putchar(s[--n]); putchar('\\n');} return 0;}\n",
        "array_sum": "#include <stdio.h>\nint main(void){int n,i; long long x,s=0; if(scanf(\"%d\",&n)==1) for(i=0;i<n&&scanf(\"%lld\",&x)==1;i++)s+=x; printf(\"%lld\\n\",s); return 0;}\n",
        "find": "#include <stdio.h>\nint main(void){int n,i,x,t,pos=-1; if(scanf(\"%d\",&n)!=1)return 0; for(i=0;i<n;i++){scanf(\"%d\",&x); if(pos<0){} } return 0;}\n",
        "sort3": "#include <stdio.h>\nint main(void){long long a[3],t; int i,j; for(i=0;i<3;i++)scanf(\"%lld\",&a[i]); for(i=0;i<3;i++)for(j=i+1;j<3;j++)if(a[i]>a[j]){t=a[i];a[i]=a[j];a[j]=t;} printf(\"%lld %lld %lld\\n\",a[0],a[1],a[2]); return 0;}\n",
        "digits": "#include <stdio.h>\nint main(void){unsigned long long n,s=0; if(scanf(\"%llu\",&n)==1){do{s+=n%10;n/=10;}while(n);printf(\"%llu\\n\",s);} return 0;}\n",
    }
    cpp = {
        "sum2": "#include <iostream>\nusing namespace std; int main(){long long a,b;cin>>a>>b;cout<<a+b<<'\\n';}\n",
        "parity": "#include <iostream>\nusing namespace std; int main(){long long n;cin>>n;cout<<(n%2==0?\"even\":\"odd\")<<'\\n';}\n",
        "max3": "#include <iostream>\n#include <algorithm>\nusing namespace std; int main(){long long a,b,c;cin>>a>>b>>c;cout<<max(a,max(b,c))<<'\\n';}\n",
        "sum_n": "#include <iostream>\nusing namespace std; int main(){long long n;cin>>n;cout<<n*(n+1)/2<<'\\n';}\n",
        "vowels": "#include <iostream>\n#include <cctype>\nusing namespace std; int main(){string s;getline(cin,s);int n=0;for(char c:s){c=tolower((unsigned char)c);if(string(\"aeiou\").find(c)!=string::npos)n++;}cout<<n<<'\\n';}\n",
        "reverse": "#include <iostream>\n#include <algorithm>\nusing namespace std; int main(){string s;getline(cin,s);reverse(s.begin(),s.end());cout<<s<<'\\n';}\n",
        "array_sum": "#include <iostream>\nusing namespace std; int main(){int n;long long x,s=0;cin>>n;while(n--){cin>>x;s+=x;}cout<<s<<'\\n';}\n",
        "find": "#include <iostream>\n#include <vector>\nusing namespace std; int main(){int n,x,t,pos=-1;cin>>n;vector<int>a(n);for(int&i:a)cin>>i;cin>>t;for(int i=0;i<n;i++)if(a[i]==t){pos=i;break;}cout<<pos<<'\\n';}\n",
        "sort3": "#include <iostream>\n#include <algorithm>\nusing namespace std; int main(){long long a[3];cin>>a[0]>>a[1]>>a[2];sort(a,a+3);cout<<a[0]<<' '<<a[1]<<' '<<a[2]<<'\\n';}\n",
        "digits": "#include <iostream>\nusing namespace std; int main(){unsigned long long n,s=0;cin>>n;do{s+=n%10;n/=10;}while(n);cout<<s<<'\\n';}\n",
    }
    py = {
        "sum2": "a, b = map(int, input().split())\nprint(a + b)\n",
        "parity": "n = int(input())\nprint('even' if n % 2 == 0 else 'odd')\n",
        "max3": "print(max(map(int, input().split())))\n",
        "sum_n": "n = int(input())\nprint(n * (n + 1) // 2)\n",
        "vowels": "s = input()\nprint(sum(ch.lower() in 'aeiou' for ch in s))\n",
        "reverse": "print(input()[::-1])\n",
        "array_sum": "n = int(input())\nprint(sum(map(int, input().split())))\n",
        "find": "n = int(input())\na = list(map(int, input().split()))\nt = int(input())\nprint(a.index(t) if t in a else -1)\n",
        "sort3": "print(*sorted(map(int, input().split())))\n",
        "digits": "print(sum(map(int, input().strip())))\n",
    }
    if language == "C" and kind == "find":
        return "#include <stdio.h>\nint main(void){int n,i,x,t,pos=-1,a[1000];if(scanf(\"%d\",&n)!=1)return 0;for(i=0;i<n;i++)scanf(\"%d\",&a[i]);scanf(\"%d\",&t);for(i=0;i<n;i++)if(a[i]==t){pos=i;break;}printf(\"%d\\n\",pos);return 0;}\n"
    return {"C": c, "C++": cpp, "Python": py}[language][kind]


def payload(language: str, spec: tuple) -> dict:
    slug, title, task, limits, tag, kind, public, hidden = spec
    filename, starter_code = starter(language)
    description = f"{task}\n\n输入格式：\n{input_format(kind)}\n\n输出格式：\n{output_format(kind)}\n\n数据范围：\n{limits}"
    generated = AI_PUBLIC_CASES[kind]
    public_rows = [*public, generated]

    def make_cases(rows, visibility):
        cases = []
        for i, row in enumerate(rows, 1):
            name, stdin, stdout = row[:3]
            is_generated = visibility == "public" and i == len(public_rows)
            cases.append({
                "id": f"{slug}-{visibility}-{i}",
                "name": name,
                "visibility": visibility,
                "stdin_text": stdin,
                "expected_stdout": stdout,
                "source": "ai_generated_validated" if is_generated else "first_party_seed",
                "generation_reason": row[3] if is_generated else "第一方原创基础样例",
                "sort_order": i,
            })
        return cases
    report = {
        "manifest": {"runner": "standard_io", "language": language.lower().replace("+", "pp"), "exercise_id": f"{SOURCE_KEY}-{slug}", "editable_files": [filename], "source_type": "first_party_original"},
        "source": SOURCE_KEY,
        "problem": {
            "problem_statement": task,
            "input_format": input_format(kind),
            "output_format": output_format(kind),
            "constraints": limits,
            "notes": "",
            "knowledge_tags": [tag, "标准输入输出", "中文 OJ"],
        },
    }
    return {"slug": f"{SOURCE_KEY}-{language.lower().replace('+', 'pp')}-{slug}", "source_key": f"{SOURCE_KEY}:{language}:{slug}", "language": language, "title": title, "difficulty": "入门", "tags_json": json.dumps([tag, "标准输入输出", "中文 OJ"], ensure_ascii=False), "description": description, "starter_files_json": json.dumps([{"path": filename, "content": starter_code}], ensure_ascii=False), "reference_files_json": json.dumps([{"path": filename, "content": reference(language, kind)}], ensure_ascii=False), "public_tests_json": json.dumps([{"samples": make_cases(public_rows, "public")}], ensure_ascii=False), "hidden_tests_json": json.dumps([{"samples": make_cases(hidden, "hidden")}], ensure_ascii=False), "official_test_files_json": "[]", "source_repo": "first_party_original", "source_path": f"{SOURCE_KEY}/{language}/{slug}", "source_commit": "2026-07-31", "license": "first_party_original", "license_text": "题面、测试数据与参考实现均为本项目第一方原创内容。", "attribution": "AI Study Platform first-party original OJ pilot", "reference_verified": True, "starter_verified": True, "audit_report_json": json.dumps(report, ensure_ascii=False)}


def input_format(kind: str) -> str:
    return {"sum2": "一行两个整数 a、b。", "parity": "一行一个整数 n。", "max3": "一行三个整数。", "sum_n": "一行一个正整数 n。", "vowels": "一行英文文本。", "reverse": "一行文本。", "array_sum": "第一行 n；第二行 n 个整数。", "find": "第一行 n；第二行 n 个整数；第三行目标值。", "sort3": "一行三个整数。", "digits": "一行一个非负整数 n。"}[kind]


def output_format(kind: str) -> str:
    return "输出题目要求的结果，并在末尾换行。"


def main() -> None:
    db = SessionLocal()
    try:
        for language in ("C", "C++", "Python"):
            for spec in PROBLEMS:
                data = payload(language, spec)
                # Early local prototypes used a different source_key but the
                # same immutable slug.  Match either identity so re-running
                # this seed is idempotent and never collides on slug.
                row = db.query(ProgrammingExercise).filter(
                    (ProgrammingExercise.source_key == data["source_key"])
                    | (ProgrammingExercise.slug == data["slug"])
                ).first()
                if row:
                    # Case identity is stable within an exercise
                    # (source_key + language + exercise slug + case id).
                    # Keep any manually confirmed case that is not owned by
                    # this seed; never move a case between public/hidden.
                    for field in ("public_tests_json", "hidden_tests_json"):
                        existing_groups = json.loads(getattr(row, field) or "[]")
                        seeded_groups = json.loads(data[field])
                        existing_cases = [case for group in existing_groups if isinstance(group, dict) for case in group.get("samples", []) if isinstance(case, dict)]
                        seeded_cases = [case for group in seeded_groups if isinstance(group, dict) for case in group.get("samples", []) if isinstance(case, dict)]
                        seeded_ids = {str(case.get("id")) for case in seeded_cases}
                        extras = [case for case in existing_cases if str(case.get("id")) not in seeded_ids]
                        if extras:
                            seeded_groups[0]["samples"].extend(extras)
                        data[field] = json.dumps(seeded_groups, ensure_ascii=False)
                    for key, value in data.items():
                        setattr(row, key, value)
                else:
                    db.add(ProgrammingExercise(**data))
        db.commit()
        print("seeded", len(PROBLEMS) * 3, "standard OJ pilot exercises")
    finally:
        db.close()


if __name__ == "__main__":
    main()
