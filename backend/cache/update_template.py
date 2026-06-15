import json, os, sys
sys.path.insert(0, r"C:\Users\26477\Desktop\ai_study_platform\backend")
os.chdir(r"C:\Users\26477\Desktop\ai_study_platform\backend")
from exam_paper_parser import CACHE_DIR

sk = "data_structure"
template_path = CACHE_DIR / sk / "manual_fix_template.json"
template = json.loads(template_path.read_text(encoding="utf-8"))

fixes = [
    {"year": 2022, "number": 1, "stem": "下列程序段的时间复杂度是（ ）。\n\nint sum=0;\n\nfor(int i = 1; i <= n; i *= 2)\n    for(int j = 1; j < i; j++)\n        sum++;", "options": {"A": "O(log n)", "B": "O(n)", "C": "O(nlogn)", "D": "O(n^2)"}, "answer": "B", "notes": "人工根据图片 2022_1_1.jpg 补录。"},
    {"year": 2022, "number": 8, "stem": "在下图所示的 5 阶 B 树 T 中，删除关键字 260 之后需要进行必要的调整，得到新的 B 树 T1。下列选项中，不可能是 T1 根结点中关键字序列的是（ ）。", "options": {"A": "60，90，280", "B": "60，90，350", "C": "60，85，110，350", "D": "60，90，110，350"}, "answer": "D", "notes": "人工根据图片补录；题目依赖原图中的 B 树结构，image_urls 必须保留。"},
    {"year": 2022, "number": 9, "stem": "下列因素中，影响散列（哈希）方法平均查找长度的是（ ）。\n\nI、装填因子\nII、散列函数\nIII、冲突解决方法", "options": {"A": "仅 I、II", "B": "仅 I、III", "C": "仅 II、III", "D": "I、II、III"}, "answer": "D", "notes": "人工根据图片 2022_9_1.jpg 补录。"},
    {"year": 2025, "number": 1, "stem": "下列程序段的时间复杂度是：\n\nint count=0, j;\nfor(i=1; i*i<=n; i++)\n    for(j=1; j<=i; j++)\n        count++;", "options": {"A": "O(log n)", "B": "O(n)", "C": "O(nlogn)", "D": "O(n^2)"}, "answer": "B", "notes": "人工根据图片 2025_1_1.jpg 补录。"},
    {"year": 2025, "number": 4, "stem": "下列关于二叉树及森林的叙述中，正确的是（ ）。", "options": {"A": "完全二叉树中不存在度为 1 的结点", "B": "任意一个森林都可以转换为一棵二叉树", "C": "二叉树的分支结点个数比叶结点个数少", "D": "表达式树的根中保存的是最先计算的运算符"}, "answer": "B", "notes": "人工根据图片 2025_4_1.jpg 补录。"},
]

fixed_count = 0
for fix in fixes:
    for item in template["items"]:
        if item["year"] == fix["year"] and item["number"] == fix["number"]:
            item["fix_fields"]["stem"] = fix["stem"]
            item["fix_fields"]["options"] = fix["options"]
            item["fix_fields"]["answer"] = fix["answer"]
            item["notes"] = fix["notes"]
            fixed_count += 1
            print(f"Updated {fix['year']} Q{fix['number']}: {fix['notes']}")
            break
    else:
        print(f"NOT FOUND: {fix['year']} Q{fix['number']}")

template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nUpdated {fixed_count}/{len(fixes)} items in template")
