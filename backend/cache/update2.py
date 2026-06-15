import json, os, sys
sys.path.insert(0, r"C:\Users\26477\Desktop\ai_study_platform\backend")
os.chdir(r"C:\Users\26477\Desktop\ai_study_platform\backend")
from exam_paper_parser import CACHE_DIR

sk = "data_structure"
template_path = CACHE_DIR / sk / "manual_fix_template.json"
template = json.loads(template_path.read_text(encoding="utf-8"))

fixes = [
    {"year": 2022, "number": 4, "stem": "若三叉树 T 中有 244 个结点（叶结点高度为 1），则 T 的高度至少是（ ）。", "options": {"A": "8", "B": "7", "C": "6", "D": "5"}, "answer": "C", "notes": "人工根据异常图补录。"},
    {"year": 2023, "number": 5, "stem": "已知一棵二叉树的树型如下图所示，若其后序遍历序列为 f，d，b，e，c，a，则其先（前）序遍历序列是（ ）。", "options": {"A": "a，e，d，f，b，c", "B": "a，c，e，b，d，f", "C": "c，a，b，e，f，d", "D": "d，f，e，b，a，c"}, "answer": "A", "notes": "题目依赖原图中的二叉树结构，image_urls 必须保留。"},
    {"year": 2024, "number": 5, "stem": "下列数据结构中，不适合直接使用折半查找的是（ ）。\n\nI. 有序链表\nII. 无序数组\nIII. 有序静态链表\nIV. 无序静态链表", "options": {"A": "仅 I、III", "B": "仅 II、IV", "C": "仅 II、III、IV", "D": "I、II、III、IV"}, "answer": "D", "notes": "人工根据两张异常图补录。"},
    {"year": 2024, "number": 6, "stem": "给定 7 个不同的关键字，能够构造的不同 4 阶 B 树的个数最多是（ ）。", "options": {"A": "7", "B": "8", "C": "9", "D": "10"}, "answer": "A", "notes": "人工根据异常图补录。"},
    {"year": 2024, "number": 10, "stem": "现有由关键字组成的 3 个有序序列（3，5）、（7，9）和（6），若按从左至右的次序选择有序序列进行二路归并排序，则关键字之间的总比较次数是（ ）。", "options": {"A": "3", "B": "4", "C": "5", "D": "6"}, "answer": "C", "notes": "人工根据异常图补录。"},
    {"year": 2025, "number": 8, "stem": "在高度为 4 的平衡二叉树中，根的左、右子树结点数相差最多的是（ ）。", "options": {"A": "1", "B": "2", "C": "3", "D": "5"}, "answer": "C", "notes": "人工根据两张异常图补录。"},
    {"year": 2026, "number": 2, "stem": "设有一个双向链表 L，结构为 [p2, p1]，头结点为 head。初始时 head = cu。现要将每个结点的 p2 指向 p1 指向结点的直接后继，应进行的操作是（ ）。", "options": {"A": "while(cu!=NULL){cu->p2=cu->p1->p1; cu=cu->p1;}", "B": "while(cu!=NULL && cu->p2!=NULL){cu->p2=cu->p1->p1; cu=cu->p1;}", "C": "while(cu!=NULL){if(cu->p1!=NULL){cu->p2=cu->p1->p1; cu=cu->p1;}}", "D": "while(cu!=NULL){if(cu->p1!=NULL){cu->p2=cu->p1->p1;} else {cu->p2=NULL; cu=cu->p1;}}"}, "answer": "D", "notes": "本题原异常报告显示仅 D 缺失，但这里一并给出完整四个选项文本，便于统一修正。"},
    {"year": 2026, "number": 5, "stem": "已知字符 abcdefg 对应权值为 1、2、4、5、8、10、12，使得带权路径长度最小，与 e 同层的结点有（ ）。", "options": {"A": "d", "B": "g", "C": "d 和 f", "D": "f 和 g"}, "answer": "D", "notes": "人工根据两张异常图补录。"},
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
            print(f"Updated {fix['year']} Q{fix['number']}")
            break
    else:
        print(f"NOT FOUND: {fix['year']} Q{fix['number']}")

template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nUpdated {fixed_count}/8 items")
