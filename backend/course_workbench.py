from subjects import COURSE_OPTIONS, normalize_subject

COURSE_PROGRESS_STATUSES = (
    "未开始",
    "学习中",
    "已掌握",
    "薄弱",
    "待复习",
)

COURSE_ROADMAPS = {
    "计算系统基础": [
        "计算机系统概述",
        "数据的表示与编码",
        "程序的编译与执行",
        "指令与指令系统",
        "存储层次结构",
        "函数调用与栈",
        "输入输出基础",
        "软硬件协同",
    ],
    "C语言": [
        "C语言基础语法",
        "分支与循环",
        "函数设计",
        "数组与字符串",
        "指针基础",
        "结构体与共用体",
        "文件读写",
        "编译与调试",
    ],
    "C++": [
        "C++ 基础语法",
        "类与对象",
        "继承与多态",
        "引用与运算符重载",
        "STL 容器",
        "模板基础",
        "内存管理",
        "编译错误与调试",
    ],
    "Python": [
        "Python 基础语法",
        "列表与字典",
        "函数与作用域",
        "字符串与文件",
        "异常处理",
        "模块与库使用",
        "面向对象基础",
        "脚本实践",
    ],
    "Java": [
        "Java 基础语法",
        "面向对象",
        "集合框架",
        "异常处理",
        "JVM 基础",
        "多线程",
        "文件与 IO",
        "项目实践",
    ],
    "离散数学": [
        "集合与集合运算",
        "关系与等价关系",
        "函数与映射",
        "命题逻辑",
        "谓词逻辑",
        "图论基础",
        "证明方法",
        "递推与归纳",
    ],
    "数据结构与算法": [
        "复杂度分析",
        "线性表",
        "栈和队列",
        "树与二叉树",
        "图",
        "排序算法",
        "查找算法",
        "贪心与动态规划",
    ],
    "计算机组成结构": [
        "数据表示",
        "运算方法",
        "指令系统",
        "CPU 结构",
        "控制器基础",
        "存储系统",
        "总线与输入输出",
        "流水线与性能",
    ],
    "互联网计算": [
        "网络体系结构",
        "TCP/IP 基础",
        "HTTP 与 HTTPS",
        "DNS 与域名解析",
        "路由与分层",
        "Web 基础",
        "分布式入门",
        "网络应用实践",
    ],
    "计算机操作系统": [
        "操作系统概述",
        "进程与线程",
        "CPU 调度",
        "同步与互斥",
        "死锁",
        "内存管理",
        "文件系统",
        "I/O 管理",
    ],
    "编译原理": [
        "编译过程概述",
        "词法分析",
        "语法分析",
        "语义分析",
        "中间代码生成",
        "代码优化",
        "目标代码生成",
        "自动机与文法",
    ],
    "数据管理": [
        "数据库基本概念",
        "关系模型",
        "SQL 基础",
        "多表查询",
        "索引",
        "事务",
        "范式",
        "查询优化",
    ],
    "人机交互": [
        "人机交互概述",
        "用户研究",
        "任务分析",
        "交互设计原则",
        "可用性评估",
        "界面设计",
        "原型设计",
        "可访问性",
    ],
}

STATUS_PROGRESS_SCORES = {
    "未开始": 0.0,
    "学习中": 0.45,
    "薄弱": 0.2,
    "待复习": 0.65,
    "已掌握": 1.0,
}


def normalize_progress_status(status: str | None, default: str = "未开始") -> str:
    normalized = (status or "").strip() or default
    if normalized not in COURSE_PROGRESS_STATUSES:
        return default
    return normalized


def get_course_roadmap(course: str | None) -> list[str]:
    normalized_course = normalize_subject(course)
    return COURSE_ROADMAPS.get(normalized_course, COURSE_ROADMAPS[COURSE_OPTIONS[0]])


def build_course_progress(course: str | None, saved_statuses: dict[str, str] | None = None):
    saved = saved_statuses or {}
    roadmap = get_course_roadmap(course)
    return [
        {
            "knowledge_point": point,
            "status": normalize_progress_status(saved.get(point)),
        }
        for point in roadmap
    ]


def calculate_progress_percent(progress_items: list[dict]) -> int:
    if not progress_items:
        return 0

    total_score = sum(
        STATUS_PROGRESS_SCORES.get(item.get("status") or "未开始", 0.0)
        for item in progress_items
    )
    return round((total_score / len(progress_items)) * 100)
