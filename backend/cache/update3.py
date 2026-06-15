import json, os, sys
sys.path.insert(0, r"C:\Users\26477\Desktop\ai_study_platform\backend")
os.chdir(r"C:\Users\26477\Desktop\ai_study_platform\backend")
from exam_paper_parser import CACHE_DIR

sk = "data_structure"
template_path = CACHE_DIR / sk / "manual_fix_template.json"
template = json.loads(template_path.read_text(encoding="utf-8"))

fixes = [
    {"year": 2022, "number": 41, "stem": "已知非空二叉树 T 的结点值均为正整数，采用顺序存储方式保存，数据结构定义如下：\n\ntypedef struct {\n    int SqBiTNode[MAX_SIZE];\n    int ElemNum;\n} SqBiTree;\n\nT 中不存在的结点在数组 SqBiTNode 中用 -1 来表示。对于下图所示的两棵非空二叉树 T1 和 T2，T1 的存储结果如下：\nT1.SqBiTNode = [40, 25, 60, -1, 30, -1, 80, -1, -1, 27]\nT1.ElemNum = 10\n\nT2 的存储结果如下：\nT2.SqBiTNode = [40, 50, 60, -1, 30, -1, -1, -1, -1, -1, 35]\nT2.ElemNum = 11\n\n请设计一个尽可能高效的算法，判定一棵采用这种方式存储的二叉树是否为二叉搜索树，若是，则返回 true，否则返回 false。\n\n要求：\n（1）给出算法的基本设计思想。\n（2）根据设计思想，采用 C 或 C++ 语言描述算法，关键之处给出注释。", "notes": "人工根据 2022 第41题两张图片补录。"},
    {"year": 2023, "number": 41, "stem": "已知有向图 G 采用邻接矩阵存储，类型定义如下：\n\ntypedef struct {\n    int numVertices, numEdges;\n    char VerticesList[MAXV];\n    int Edge[MAXV][MAXV];\n} MGraph;\n\n将图中出度大于入度的顶点称为 K 顶点，例如题 41 图中，顶点 a 和 b 为 K 顶点。\n\n请设计算法：int printVertices(MGraph G)，对给定的任意非空有向图 G，输出 G 中所有的 K 顶点，并返回 K 顶点的个数。\n\n（1）给出算法的基本设计思想。\n（2）根据设计思想，采用 C 或 C++ 语言描述算法，关键之处给出注释。", "notes": "人工根据 2023 第41题两张图片补录。"},
    {"year": 2024, "number": 41, "stem": "2023 年 10 月 26 日，神舟十七号载人飞船发射取得圆满成功，再次彰显了中国航天事业的辉煌成就。载人航天工程是包含众多子工程的复杂系统工程，为了保证工程的有序开展，需要明确各子工程的前导工程，以协调各子工程的实施。该问题可以简化、抽象为有向图的拓扑序列问题。已知有向图 G 采用邻接矩阵存储，类型定义如下：\n\ntypedef struct {\n    int numVertices, numEdges;\n    char VerticesList[MAXV];\n    int Edge[MAXV][MAXV];\n} MGraph;\n\n请设计算法：int uniquely(MGraph G)，判定 G 是否存在唯一的拓扑序列，若是则返回 1，否则返回 0。\n\n要求：\n（1）给出算法的基本设计思想（4 分）。\n（2）根据设计思想，采用 C 或 C++ 语言描述算法，关键之处给出注释（9 分）。", "notes": "人工根据 2024 第41题两张图片补录。"},
    {"year": 2025, "number": 41, "stem": "设有两个长度均为 n 的一维整型数组 A 和 res，对数组 A 中的每个元素 A[i]，计算 A[i] 与 A[j]（0≤i≤j≤n-1）乘积的最大值，并将其保存到 res[i] 中。例如，若 A[] = {1, 4, -9, 6}，则得到 res[] = {6, 24, 81, 36}。现给定数组 A，请设计一个时间和空间上尽可能高效的算法 calMulMax，求 res 中各元素的值。函数原型为：void calMulMax(int A[], int res[], int n)。要求如下：\n\n（1）给出算法的基本设计思想。（4 分）\n（2）根据设计思想，采用 C 或 C++ 语言描述算法，关键之处给出注释。（7 分）\n（3）说明你所设计算法的时间复杂度和空间复杂度。（2 分）", "notes": "人工根据 2025 第41题图片补录。"},
    {"year": 2026, "number": 41, "stem": "假定二叉搜索树使用二叉链表存储，存储结构如下：\n\ntypedef struct BSTNode {\n    int data;\n    struct BSTNode *left, *right;\n} BSTNode;\n\ntypedef BSTNode BTNode;\n\n给一棵二叉搜索树 T 和整数 K，查找树中关键字与 K 之差的绝对值最小的所有结点，并输出该绝对值与结点中的关键字。\n\n（1）给出算法的基本思想。（4 分）\n（2）使用 C/C++ 描述算法思想。（8 分）", "notes": "人工根据 2026 第41题图片补录。"},
    {"year": 2026, "number": 8, "stem": "在高度为 4 的平衡二叉树中，根的左、右子树结点数相差最多的是（ ）。", "options": {"A": "1", "B": "2", "C": "3", "D": "5"}, "answer": "D", "notes": "人工根据最后一张 2026 第8题截图补录。"},
]

fixed_count = 0
for fix in fixes:
    for item in template["items"]:
        if item["year"] == fix["year"] and item["number"] == fix["number"]:
            item["fix_fields"]["stem"] = fix["stem"]
            if "options" in fix:
                item["fix_fields"]["options"] = fix["options"]
            if "answer" in fix:
                item["fix_fields"]["answer"] = fix["answer"]
            item["notes"] = fix["notes"]
            fixed_count += 1
            print(f"Updated {fix['year']} Q{fix['number']}")
            break
    else:
        print(f"NOT FOUND: {fix['year']} Q{fix['number']}")

template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nUpdated {fixed_count}/{len(fixes)} items")
