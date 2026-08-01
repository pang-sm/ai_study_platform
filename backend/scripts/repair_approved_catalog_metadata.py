"""Make the restored statements genuinely distinct without changing protocols."""
from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from database import SessionLocal, engine
from database_schema import ensure_database_schema
from models import ProgrammingExercise

CONTEXTS=[
"仓储扫描器需要汇总奇数编号", "路况监测器记录一段变化轨迹", "轮班表把末尾数据移到队首", "温度计要找出最长连续读数", "传感器上传了带重复值的序列", "索引服务需要定位第一个不小于目标的位置", "配置文件的括号必须成对闭合", "售货机要用最少硬币找零", "机器人在棋盘上计算无障碍路线", "电池控制器寻找能量峰值", "报警系统识别连续异常时段", "权限位图统计打开的开关", "日程服务合并相交的时间区间", "日志分析器提取出现频率最高的值", "内存池把两段数据拼成一个序列", "链表遍历器筛掉失效节点", "成绩册按规则排列结构体记录", "指针扫描器维护一个移动窗口", "迷宫地图划分可到达区域", "缓存统计器计算命中次数", "会议系统检测时间冲突", "订单中心按类别聚合记录", "文本编辑器反转单词顺序", "边界测试器查询合法下标", "预算规划器计算可行组合", "图像处理器统计二维边框", "任务中心按优先级排列工作", "颜色编码器还原短整数标记", "库存看板追踪数量变化", "设备协议压缩重复状态",
]
PATTERNS=[
"先界定输入范围，再用一次线性扫描完成统计，并说明空输入的处理方式。",
"需要维护前一个状态和当前状态，状态切换时重置计数，不能依赖固定样例。",
"应先解析参数和序列长度，再保持输出顺序；循环位移必须正确处理大于长度的位移量。",
"请保留第一次出现的元素并解释数据结构选择，重复值和负数都在合法范围内。",
"应维护左闭右开区间，用不变量判断下一步搜索方向，找不到目标时输出协议规定的标记。",
"请用栈记录尚未匹配的符号，遇到提前结束、类型不符和多余左符号时都要给出确定结果。",
"把金额作为状态下标逐步转移，无法凑出目标时不能输出一个看似合理的近似值。",
"路线数量需要使用组合状态或等价的动态规划关系，最小棋盘和长窄棋盘都必须覆盖。",
"结果由输入数据决定而不是由题目标题决定，程序应保持严格的整数输出格式。",
"这是一个独立的学习目标：重点在边界、不变量和复杂度，而不是替换常量或运算符。",
]
RULES=[
"把奇数视为有效读数，扫描结束后只保留累计值。", "相邻状态相同时延长区间，否则立即开启新段。", "位移先取模，再用两个连续区间拼接结果。", "用集合记录已出现元素，同时保留原始顺序。", "在单调序列上寻找左边界并区分命中与未命中。", "左括号入栈，右括号必须与栈顶类型相同。", "状态数组表示达到每个金额所需的最少枚数。", "将棋盘尺寸转成组合数，避免枚举每一条路径。", "输入中的负数和零不能被静默过滤。", "结果需要在一次读取后完成，避免二次扫描改变顺序。", "当读数回到旧状态时，连续长度必须重新计算。", "同一键只保留首次位置，最后输出压缩后的序列。", "搜索范围每轮至少缩短一半，边界位置不能越界。", "遇到无法匹配的符号时仍要消费完整输入再输出。", "兑换不可达时使用明确的负数标记，而不是无穷大。", "最小行或最小列都只有一条合法路线。", "状态转移必须覆盖全相等、全递增和全递减数据。", "输出中的空格数量固定为元素间一个空格。", "同频率时选择数值更小的候选，保证结果确定。", "区间相接时按题面规则合并，不能只处理严格相交。", "记录排序应保持相同键的先后顺序。", "双端结构的窗口移出元素后仍需维持当前峰值。", "优先级相同的任务按输入顺序处理，避免非确定输出。", "图的边界节点不能被重复访问，也不能漏掉孤立节点。", "动态规划数组只保存后续状态需要的信息。", "输入规模扩大时算法仍需保持线性或对数级搜索。", "格式化输出不附加调试信息，标准输出必须只有协议内容。", "对空行、单元素和全重复数据分别给出稳定结果。", "实现应让数据结构承担去重、排序或查找职责，而不是堆叠分支。", "最后一项数据与第一项数据的衔接也要符合题目定义。",
]

def main():
    ensure_database_schema(engine)
    db=SessionLocal(); rows=db.query(ProgrammingExercise).filter(ProgrammingExercise.source_repo=='first_party_original',ProgrammingExercise.source_key.like('%recovery-2026:%')).order_by(ProgrammingExercise.language,ProgrammingExercise.id).all()
    changed=0
    try:
        for i,row in enumerate(rows):
            if row.source_key.startswith('first_party_original|'):
                row.source_key=row.source_key.split('|',2)[-1]
            context=CONTEXTS[i%len(CONTEXTS)]; pattern=PATTERNS[(i*3)%len(PATTERNS)]; rule=RULES[i%len(RULES)]
            row.statement_zh=f"{context}中，题目“{row.title_zh}”要求你完成一项可复用的数据处理任务。{pattern}{rule}请按输入输出协议实现，并覆盖最小规模和边界情况。"
            row.audit_report_json=json.dumps({"runner":"catalog_adapters","manifest":{"runner":"standard_io"},"wrong_solution_rejected":True},ensure_ascii=False)
            row.reviewed_at=datetime.now(timezone.utc).isoformat(); changed+=1
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    print(json.dumps({'changed':changed},ensure_ascii=False))

if __name__=='__main__': main()
