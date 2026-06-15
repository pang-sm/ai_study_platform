"""Generate chapter practice questions for data_structure.
Usage: python scripts/generate_chapter_questions_data_structure.py --dry-run --limit 3
       python scripts/generate_chapter_questions_data_structure.py --all
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import SessionLocal
import models

SK = "data_structure"
SUBJECT_NAME = "数据结构"

# Pre-built question templates per knowledge point
# Each template: stem, options (choice) or empty (big), answer, analysis, difficulty
CHAPTER_TEMPLATES = {
    "1.1 数据结构的基本概念": [
        {"type": "choice", "stem": "以下关于数据结构的说法中，正确的是（ ）。", "options": {"A": "数据结构仅研究数据的逻辑结构", "B": "数据结构研究数据的逻辑结构、存储结构和运算", "C": "数据结构只与存储方式有关", "D": "算法与数据结构无关"}, "answer": "B", "analysis": "数据结构包含逻辑结构、存储结构和运算三个层面，三者密切相关。", "difficulty": "基础"},
        {"type": "choice", "stem": "数据的逻辑结构可以被分为（ ）。", "options": {"A": "顺序结构和链式结构", "B": "线性结构和非线性结构", "C": "静态结构和动态结构", "D": "内部结构和外部结构"}, "answer": "B", "analysis": "逻辑结构分为线性结构（如线性表、栈、队列）和非线性结构（如树、图）。", "difficulty": "基础"},
        {"type": "choice", "stem": "以下选项中，属于数据的存储结构的是（ ）。", "options": {"A": "线性表", "B": "二叉树", "C": "顺序存储", "D": "有向图"}, "answer": "C", "analysis": "顺序存储和链式存储是两种基本的存储结构。A、B、D 属于逻辑结构。", "difficulty": "基础"},
        {"type": "big", "stem": "请简述数据结构的三个要素，并各举一例说明。", "options": {}, "answer": "三个要素：1）逻辑结构：数据元素之间的逻辑关系，如线性结构（线性表）、非线性结构（树、图）。2）存储结构（物理结构）：数据结构在计算机中的表示，如顺序存储、链式存储。3）运算：对数据进行的操作，如查找、插入、删除。", "analysis": "考查数据结构的基本概念，需从逻辑、存储、运算三个层面回答。", "difficulty": "基础"},
    ],
    "2.1 线性表的定义和基本操作": [
        {"type": "choice", "stem": "线性表是一种（ ）。", "options": {"A": "非线性结构", "B": "线性结构", "C": "树形结构", "D": "图形结构"}, "answer": "B", "analysis": "线性表是典型的线性结构，元素之间是一对一的关系。", "difficulty": "基础"},
        {"type": "choice", "stem": "在长度为 n 的线性表中插入一个元素，平均需要移动的元素个数是（ ）。", "options": {"A": "n", "B": "n/2", "C": "(n-1)/2", "D": "n-1"}, "answer": "B", "analysis": "平均移动次数为 n/2，因为插入位置等概率分布。", "difficulty": "基础"},
        {"type": "choice", "stem": "顺序表插入操作的时间复杂度是（ ）。", "options": {"A": "O(1)", "B": "O(n)", "C": "O(logn)", "D": "O(n²)"}, "answer": "B", "analysis": "顺序表插入需要移动元素，最坏和平均情况都是 O(n)。", "difficulty": "基础"},
        {"type": "big", "stem": "已知顺序表 L 长度为 n，设计算法删除 L 中所有值为 x 的元素，并分析时间复杂度。", "options": {}, "answer": "思路：使用双指针，k 记录有效元素位置。遍历顺序表，如果当前元素不等于 x，则将其移到位置 k，k++。最后修改表长为 k。时间复杂度 O(n)，空间复杂度 O(1)。", "analysis": "考查顺序表删除操作，关键是移动元素和复杂度分析。", "difficulty": "中等"},
    ],
    "2.2 线性表的顺序表示": [
        {"type": "choice", "stem": "顺序表的特点是（ ）。", "options": {"A": "逻辑上相邻的元素在物理位置上不一定相邻", "B": "需要额外空间存储指针", "C": "支持随机存取", "D": "插入删除不需要移动元素"}, "answer": "C", "analysis": "顺序表的最大优点是支持随机存取，即通过下标 O(1) 访问。", "difficulty": "基础"},
        {"type": "choice", "stem": "长度为 n 的顺序表中删除第 i 个元素，需要移动（ ）个元素。", "options": {"A": "i", "B": "n-i", "C": "i-1", "D": "n-i+1"}, "answer": "B", "analysis": "删除第 i 个元素后，后面的 n-i 个元素需要前移。", "difficulty": "基础"},
        {"type": "big", "stem": "设计算法将两个有序顺序表 A 和 B 合并为一个新的有序顺序表 C。", "options": {}, "answer": "使用归并思想：i=j=k=0，比较 A[i] 和 B[j]，较小的放入 C[k]，对应指针后移。当一表遍历完后，将另一表剩余元素直接复制到 C。时间复杂度 O(m+n)。", "analysis": "考查归并算法，是有序顺序表的基本操作。", "difficulty": "中等"},
    ],
    "3.1 栈": [
        {"type": "choice", "stem": "栈的特点是（ ）。", "options": {"A": "先进先出", "B": "先进后出", "C": "只能在一端插入", "D": "可在任意位置操作"}, "answer": "B", "analysis": "栈是后进先出(LIFO)的线性结构，插入和删除都在栈顶进行。", "difficulty": "基础"},
        {"type": "choice", "stem": "若元素入栈序列为 1,2,3,4，则不可能的出栈序列是（ ）。", "options": {"A": "1,2,3,4", "B": "4,3,2,1", "C": "3,2,4,1", "D": "3,1,4,2"}, "answer": "D", "analysis": "D 不可能：3出栈时1,2已在栈中，2必须在1之前出栈，所以1不能紧跟在3后出栈。", "difficulty": "中等"},
        {"type": "choice", "stem": "链栈的入栈操作，栈顶指针 top 应（ ）。", "options": {"A": "top=top->next", "B": "top->next=top", "C": "新结点的 next 指向 top，top 指向新结点", "D": "top=新结点"}, "answer": "C", "analysis": "链栈入栈：新结点 next 指向当前栈顶，然后栈顶指针移到新结点。", "difficulty": "基础"},
        {"type": "big", "stem": "设计算法判断一个表达式中的括号是否匹配（包括( )、[ ]、{ }）。", "options": {}, "answer": "使用栈：遇到左括号入栈，遇到右括号检查栈顶是否匹配，匹配则出栈，否则不匹配。遍历结束后栈为空则匹配成功。时间复杂度 O(n)。", "analysis": "栈的经典应用——括号匹配。", "difficulty": "中等"},
    ],
    "3.2 队列": [
        {"type": "choice", "stem": "队列的特点是（ ）。", "options": {"A": "先进后出", "B": "先进先出", "C": "两端都可操作", "D": "只能在队尾插入"}, "answer": "B", "analysis": "队列是先进先出(FIFO)的线性结构，插入在队尾，删除在队头。", "difficulty": "基础"},
        {"type": "choice", "stem": "循环队列用数组 Q[0..m-1] 存放元素，队头 front 指向第一个元素，队尾 rear 指向最后一个元素的下一个位置，则队列满的条件是（ ）。", "options": {"A": "front==rear", "B": "(rear+1)%m==front", "C": "rear==m-1", "D": "front==0 && rear==m-1"}, "answer": "B", "analysis": "循环队列中，为区分队空和队满，通常牺牲一个单元，队满条件为 (rear+1)%m==front。", "difficulty": "中等"},
        {"type": "choice", "stem": "链队列的出队操作中，若队列只有一个结点，则出队后（ ）。", "options": {"A": "front不变", "B": "rear不变", "C": "front和rear都应置为NULL", "D": "front指向rear"}, "answer": "C", "analysis": "链队列只有一个结点时，出队后队列为空，front 和 rear 都应置为 NULL。", "difficulty": "中等"},
        {"type": "big", "stem": "设计一个循环队列的基本操作：入队和出队，并用测试用例验证。", "options": {}, "answer": "定义结构体包含 data 数组和 front、rear。入队：data[rear]=x; rear=(rear+1)%MAXSIZE。出队：x=data[front]; front=(front+1)%MAXSIZE。需处理队满和队空条件。", "analysis": "循环队列的基本实现，注意取模运算和边界条件。", "difficulty": "中等"},
    ],
    "4.1 树的基本概念": [
        {"type": "choice", "stem": "一棵有 n 个结点的树中，所有结点的度数之和为（ ）。", "options": {"A": "n", "B": "n-1", "C": "2n", "D": "n²"}, "answer": "B", "analysis": "树中除根结点外每个结点恰有一条边与其父结点相连，因此所有结点度数之和 = n-1。", "difficulty": "基础"},
        {"type": "choice", "stem": "深度为 k 的完全二叉树最多有（ ）个结点。", "options": {"A": "2ᵏ-1", "B": "2ᵏ", "C": "2ᵏ⁺¹-1", "D": "2ᵏ⁻¹"}, "answer": "A", "analysis": "深度为 k 的完全二叉树最多有 2ᵏ-1 个结点（满二叉树）。", "difficulty": "基础"},
        {"type": "big", "stem": "证明：任意一棵二叉树中，若叶子结点数为 n₀，度为 2 的结点数为 n₂，则 n₀ = n₂ + 1。", "options": {}, "answer": "设总结点数为 n，n=n₀+n₁+n₂。又 n = 分支数+1 = n₁+2n₂+1。联立得 n₀ = n₂+1。", "analysis": "二叉树性质的经典证明，利用结点数等于分支数加一。", "difficulty": "基础"},
    ],
    "5.1 图的基本概念": [
        {"type": "choice", "stem": "具有 n 个顶点的无向完全图的边数是（ ）。", "options": {"A": "n", "B": "n(n-1)", "C": "n(n-1)/2", "D": "2n"}, "answer": "C", "analysis": "无向完全图每对顶点之间有一条边，边数为 C(n,2)=n(n-1)/2。", "difficulty": "基础"},
        {"type": "choice", "stem": "在无向图中，所有顶点的度数之和等于边数的（ ）倍。", "options": {"A": "1", "B": "2", "C": "n", "D": "n-1"}, "answer": "B", "analysis": "每条边贡献两个度，因此所有顶点度数之和等于边数的 2 倍。", "difficulty": "基础"},
        {"type": "choice", "stem": "一个连通图的最小生成树（ ）。", "options": {"A": "是唯一的", "B": "边的权值之和最小", "C": "一定包含所有顶点", "D": "边数等于顶点数"}, "answer": "B", "analysis": "最小生成树是包含所有顶点的权值和最小的生成树，可能不唯一，边数为 n-1。", "difficulty": "基础"},
        {"type": "big", "stem": "分别用 Prim 算法和 Kruskal 算法求下图的最小生成树，并比较两种算法的适用场景。", "options": {}, "answer": "Prim：从任意顶点开始，每次选择与当前连通分量相连的最小权边，时间复杂度 O(n²)，适合稠密图。Kruskal：按边权排序，每次选择不构成回路的最小边，时间复杂度 O(eloge)，适合稀疏图。", "analysis": "两种经典最小生成树算法的比较。", "difficulty": "中等"},
    ],
    "7.1 查找的基本概念": [
        {"type": "choice", "stem": "顺序查找法的平均查找长度是（ ）。", "options": {"A": "n", "B": "(n+1)/2", "C": "log₂n", "D": "n/2"}, "answer": "B", "analysis": "顺序查找的平均查找长度为 (n+1)/2，查找成功的平均比较次数。", "difficulty": "基础"},
        {"type": "choice", "stem": "折半查找要求查找表是（ ）。", "options": {"A": "顺序存储且有序", "B": "链式存储且有序", "C": "任意存储方式", "D": "顺序存储但无需有序"}, "answer": "A", "analysis": "折半查找要求查找表采用顺序存储且关键字有序。", "difficulty": "基础"},
        {"type": "choice", "stem": "哈希表解决冲突的常用方法不包括（ ）。", "options": {"A": "链地址法", "B": "开放定址法", "C": "再哈希法", "D": "归并法"}, "answer": "D", "analysis": "归并法是排序算法，不是哈希冲突解决方法。链地址法、开放定址法、再哈希法是常用方法。", "difficulty": "基础"},
        {"type": "big", "stem": "给定关键字序列 19,14,23,1,68,20,84,27,55,11,10,79，散列函数 H(key)=key%13，用线性探测法处理冲突，构造散列表并计算平均查找长度。", "options": {}, "answer": "按顺序插入，若位置被占则线性探测下一个空位。ASL = 成功查找的平均比较次数。", "analysis": "散列表构造和冲突处理，考查线性探测法的实现。", "difficulty": "中等"},
    ],
    "8.1 排序的基本概念": [
        {"type": "choice", "stem": "下列排序算法中，时间复杂度为 O(nlogn) 的是（ ）。", "options": {"A": "直接插入排序", "B": "简单选择排序", "C": "快速排序", "D": "冒泡排序"}, "answer": "C", "analysis": "快速排序平均时间复杂度为 O(nlogn)，其余三个平均为 O(n²)。", "difficulty": "基础"},
        {"type": "choice", "stem": "快速排序在（ ）情况下退化为 O(n²)。", "options": {"A": "待排序序列基本有序", "B": "待排序序列完全逆序", "C": "A和B都是", "D": "只有B是"}, "answer": "C", "analysis": "当序列基本有序或完全逆序时，若每次枢轴选得不好，快速排序退化为 O(n²)。", "difficulty": "基础"},
        {"type": "choice", "stem": "归并排序的空间复杂度是（ ）。", "options": {"A": "O(1)", "B": "O(logn)", "C": "O(n)", "D": "O(n²)"}, "answer": "C", "analysis": "归并排序需要辅助数组，空间复杂度为 O(n)。", "difficulty": "基础"},
        {"type": "big", "stem": "用快速排序对序列 49,38,65,97,76,13,27 进行升序排序，画出第一趟排序过程。", "options": {}, "answer": "选 49 为枢轴，从右向左找小于 49 的(27)，从左向右找大于 49 的(65)，交换。最终枢轴归位，左边 <49，右边 >49。第一趟结果：[27,38,13],49,[76,97,65]。", "analysis": "快速排序的划分过程，理解枢轴的选择和元素交换。", "difficulty": "中等"},
    ],
}

def generate():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    existing = db.query(models.ExamQuestionBank).filter(
        models.ExamQuestionBank.subject_key == SK,
        models.ExamQuestionBank.source_type == "chapter",
    ).count()
    print(f"Existing chapter questions: {existing}")

    total_imported = 0
    for kp_path, templates in CHAPTER_TEMPLATES.items():
        if args.limit > 0 and total_imported >= args.limit:
            break
        kp_parts = kp_path.split(" ", 1)
        kp_id = kp_parts[0] if kp_parts else kp_path
        kp_name = kp_parts[1] if len(kp_parts) > 1 else kp_path
        for tmpl in templates:
            if args.limit > 0 and total_imported >= args.limit:
                break
            # Check duplicate
            dup = db.query(models.ExamQuestionBank).filter(
                models.ExamQuestionBank.subject_key == SK,
                models.ExamQuestionBank.source_type == "chapter",
                models.ExamQuestionBank.knowledge_point_id == kp_id,
                models.ExamQuestionBank.stem == tmpl["stem"],
            ).first()
            if dup:
                continue

            if args.dry_run:
                print(f"[DRY] {kp_path}: {tmpl['type']} \"{tmpl['stem'][:60]}...\"")
                total_imported += 1
                continue

            item = models.ExamQuestionBank(
                subject_key=SK, subject_name=SUBJECT_NAME,
                source_type="chapter", visibility="public",
                knowledge_point_id=kp_id, knowledge_point_name=kp_name,
                knowledge_point_path=kp_path,
                question_type="choice" if tmpl.get("type") == "choice" else "big",
                stem=tmpl["stem"],
                options_json=json.dumps(tmpl.get("options", {}), ensure_ascii=False),
                standard_answer=tmpl["answer"],
                analysis=tmpl["analysis"],
                difficulty=tmpl.get("difficulty", "基础"),
            )
            db.add(item)
            total_imported += 1

    if not args.dry_run:
        db.commit()
        print(f"Imported {total_imported} chapter questions (dry_run={args.dry_run})")
    else:
        print(f"DRY RUN: would import {total_imported} questions")

    db.close()


if __name__ == "__main__":
    generate()
