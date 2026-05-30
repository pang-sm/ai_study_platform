/**
 * Route node structure:
 * {
 *   id: string,
 *   title: string,
 *   subtitle: string,
 *   knowledgePoints: string[],
 *   sourceType: "planned" | "materials",
 *   status: "mastered" | "learning" | "review" | "locked",
 *   progress: 0..1,
 * }
 */

const C_LANGUAGE_PLANNED_ROUTE = [
  {
    id: "c-stage-1",
    title: "C语言入门与开发环境",
    subtitle: "认识C语言，搭建编程环境，写出第一行代码",
    knowledgePoints: [
      "C语言是什么", "人与计算机通过程序语言沟通", "编译、链接与可执行文件",
      "Hello World", "printf 基础", "代码基本框架", "编程环境与OJ练习",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-2",
    title: "变量、类型、表达式与 I/O",
    subtitle: "掌握数据类型、运算符和基本输入输出",
    knowledgePoints: [
      "变量和内存", "变量定义与命名", "int、double、float、char",
      "常量与基本数据类型", "算术运算符", "赋值与复合赋值",
      "printf 格式化输出", "scanf 输入", "字符与字符串数组入门",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-3",
    title: "分支、循环与一维数组",
    subtitle: "用条件判断和循环控制程序流程",
    knowledgePoints: [
      "if / else", "逻辑表达式", "关系运算符与判等运算符", "switch",
      "for 循环", "while / do while", "break / continue",
      "一维数组", "数组初始化", "数组遍历", "数组下标从0开始",
      "常见练习：闰年、阶乘、猜数字、逆序、素数",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-4",
    title: "数组进阶、排序与多维数组",
    subtitle: "深入数组操作，掌握经典排序算法",
    knowledgePoints: [
      "数组与地址", "数组和循环结合", "选择排序", "冒泡排序",
      "归并排序", "插入排序", "多维数组", "二维数组存储",
      "矩阵相乘", "五子棋棋盘建模",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-5",
    title: "函数与模块化思维",
    subtitle: "用函数组织代码，培养模块化编程习惯",
    knowledgePoints: [
      "函数定义与调用", "函数声明", "返回值", "形式参数与实际参数",
      "值传递", "本地变量", "数组作为函数参数", "函数调用栈",
      "用函数改写位数、闰年、数组求和、排序等程序",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-6",
    title: "数据表示、类型系统与安全边界",
    subtitle: "理解计算机如何表示数据，建立安全编码意识",
    knowledgePoints: [
      "整数类型", "signed / unsigned", "补码", "sizeof", "整型提升",
      "类型转换", "位运算", "未定义行为UB", "整数溢出",
      "浮点数IEEE754", "浮点精度", "安全编码意识",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-7",
    title: "指针、动态内存与字符串",
    subtitle: "掌握C语言核心难点——指针与内存管理",
    knowledgePoints: [
      "指针含义", "& 和 *", "指针赋值", "指针作为函数参数",
      "指针与数组", "指针运算", "多维数组与指针", "const与指针",
      "malloc / free", "动态数组", "内存泄漏", "字符串指针与字符数组",
      "string.h 常用函数", "指针数组", "函数指针",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
  {
    id: "c-stage-8",
    title: "结构体、链表、递归与程序组织",
    subtitle: "数据结构入门与多文件程序设计",
    knowledgePoints: [
      "struct", "struct 成员访问", "struct 作为参数和返回值",
      "struct 内存对齐", "union", "enum", "位域",
      "链表", "单向链表 / 双向链表 / 循环链表", "二叉树",
      "递归", "斐波那契", "分治", "归并排序 / 快速排序",
      "预处理", "宏定义", "条件编译", "多文件程序",
      "Makefile / CMake", "文件 I/O",
    ],
    sourceType: "planned",
    status: "locked",
    progress: 0,
  },
];

const CPP_PLANNED_ROUTE = [
  {
    id: "cpp-stage-1",
    title: "C++ 基础语法与编译",
    subtitle: "认识C++程序结构，掌握基本输入输出与命名空间",
    knowledgePoints: [
      "C++ 程序结构", "输入输出 cin / cout", "命名空间 namespace",
      "基本数据类型", "表达式与控制流", "编译与运行",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-2",
    title: "函数、引用与重载",
    subtitle: "掌握函数定义、参数传递和函数重载",
    knowledgePoints: [
      "函数定义与声明", "默认参数", "函数重载",
      "引用 &", "const 引用", "作用域与生命周期",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-3",
    title: "类与对象",
    subtitle: "理解面向对象基础，掌握类的定义与使用",
    knowledgePoints: [
      "class / struct", "成员变量", "成员函数",
      "构造函数", "析构函数", "this 指针", "访问控制 public / private / protected",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-4",
    title: "面向对象进阶",
    subtitle: "掌握继承、多态和运算符重载",
    knowledgePoints: [
      "封装", "继承", "多态", "虚函数 virtual",
      "抽象类与纯虚函数", "运算符重载", "友元函数",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-5",
    title: "模板与泛型编程",
    subtitle: "掌握模板语法和泛型编程思想",
    knowledgePoints: [
      "函数模板", "类模板", "模板实例化",
      "模板特化", "STL 基础概念",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-6",
    title: "STL 容器与算法",
    subtitle: "掌握标准库容器和常用算法",
    knowledgePoints: [
      "vector", "string", "map / set",
      "iterator 迭代器", "algorithm 算法库", "sort / find / count",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-7",
    title: "内存管理与智能指针",
    subtitle: "掌握C++内存管理和RAII编程范式",
    knowledgePoints: [
      "new / delete", "RAII 资源管理", "unique_ptr",
      "shared_ptr / weak_ptr", "内存泄漏检测", "资源管理最佳实践",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
  {
    id: "cpp-stage-8",
    title: "工程实践",
    subtitle: "多文件组织、构建系统和项目实战",
    knowledgePoints: [
      "多文件组织", "头文件与实现分离", "CMake 构建",
      "调试技巧", "单元测试", "小项目实践",
    ],
    sourceType: "planned", status: "locked", progress: 0,
  },
];

/** Courses that should use the planned C language route */
const C_LANGUAGE_COURSE_KEYS = new Set([
  "c_programming",
  "computer_programming_language",
  "cpl",
  "c_language",
  "programming_fundamentals",
]);

/** Courses that should use the planned C++ route */
const CPP_COURSE_KEYS = new Set([
  "c++",
  "c++_programming",
  "cpp",
  "cpp_programming",
  "cplusplus",
]);

/** Courses whose display name contains C-language-related keywords */
const C_LANGUAGE_NAME_PATTERNS = [
  "C语言", "C语言程序设计", "CPL", "程序设计基础",
];

/** Courses whose display name contains C++-related keywords */
const CPP_NAME_PATTERNS = [
  "C++", "C＋+", "cpp", "CPP",
];

/**
 * Determine the knowledge route source for a course.
 * Returns "planned_c" for C-language, "planned_cpp" for C++, "materials" otherwise.
 */
export function getRouteSource(courseKey, courseLabel) {
  const normalizedKey = (courseKey || "").toLowerCase().replace(/[_-]/g, "");
  if (C_LANGUAGE_COURSE_KEYS.has(normalizedKey)) return "planned";
  if (CPP_COURSE_KEYS.has(normalizedKey)) return "planned";

  const label = (courseLabel || "").toLowerCase();
  for (const pattern of C_LANGUAGE_NAME_PATTERNS) {
    if (label.includes(pattern.toLowerCase())) return "planned";
  }
  for (const pattern of CPP_NAME_PATTERNS) {
    if (label.includes(pattern.toLowerCase())) return "planned";
  }
  return "materials";
}

/**
 * Get the planned route for a course.
 * Status and progress should be merged with existing learning records.
 * @param {string} courseKey - course identifier
 * @param {object} progressMap - map of knowledge point → progress status
 * @param {object} statusMap - map of knowledge point → status
 */
export function getPlannedRoute(courseKey, progressMap = {}, statusMap = {}) {
  const routeSource = getRouteSource(courseKey, courseKey);
  let route;
  if (routeSource === "materials") return [];
  // Both C and C++ use "planned" routeSource, but we distinguish by course key patterns
  const isCpp = CPP_COURSE_KEYS.has((courseKey || "").toLowerCase().replace(/[_-]/g, ""));
  route = isCpp ? CPP_PLANNED_ROUTE : C_LANGUAGE_PLANNED_ROUTE;

  return route.map((stage) => {
    const masteredCount = stage.knowledgePoints.filter(
      (kp) => (statusMap[kp] || progressMap[kp]) === "mastered"
    ).length;
    const learningCount = stage.knowledgePoints.filter(
      (kp) => (statusMap[kp] || progressMap[kp]) === "learning"
    ).length;
    const total = stage.knowledgePoints.length;

    let status = "locked";
    let progress = 0;

    if (total > 0) {
      progress = Math.round((masteredCount / total) * 100) / 100;
      if (masteredCount === total) {
        status = "mastered";
      } else if (learningCount > 0 || masteredCount > 0) {
        status = "learning";
      }
    }

    return { ...stage, status, progress };
  });
}

/**
 * Derive a flat knowledge-points overview list from route nodes.
 */
export function deriveKnowledgePointsOverview(routeNodes) {
  if (!Array.isArray(routeNodes)) return [];
  return routeNodes.map((node) => ({
    stageId: node.id,
    stageTitle: node.title,
    status: node.status,
    progress: node.progress,
    pointCount: (node.knowledgePoints || []).length,
    points: node.knowledgePoints || [],
  }));
}

/**
 * Calculate overall learning progress from route nodes.
 */
export function calculateOverallProgress(routeNodes) {
  if (!Array.isArray(routeNodes) || routeNodes.length === 0) {
    return { percent: 0, masteredPoints: 0, totalPoints: 0, reviewCount: 0 };
  }
  let totalPoints = 0;
  let masteredPoints = 0;
  let reviewCount = 0;
  routeNodes.forEach((node) => {
    totalPoints += (node.knowledgePoints || []).length;
    masteredPoints += node.status === "mastered" ? (node.knowledgePoints || []).length : 0;
    if (node.status === "review") reviewCount += 1;
  });
  return {
    percent: totalPoints > 0 ? Math.round((masteredPoints / totalPoints) * 100) : 0,
    masteredPoints,
    totalPoints,
    reviewCount,
  };
}

/**
 * Unlock first N stages based on actual learning progress data.
 * Default: first 2 stages are unlocked, rest are locked.
 */
export function applyProgressToRoute(routeNodes, progressMap = {}, statusMap = {}) {
  if (!Array.isArray(routeNodes)) return [];
  return routeNodes.map((node, index) => {
    const pointStatuses = (node.knowledgePoints || []).map(
      (kp) => statusMap[kp] || progressMap[kp] || "locked"
    );
    const masteredCount = pointStatuses.filter((s) => s === "mastered").length;
    const learningCount = pointStatuses.filter((s) => s === "learning").length;
    const total = node.knowledgePoints.length;

    let status = "locked";
    let progress = 0;
    if (total > 0) {
      progress = Math.round((masteredCount / total) * 100) / 100;
      if (masteredCount === total) status = "mastered";
      else if (learningCount > 0 || masteredCount > 0) status = "learning";
      else if (index <= 1) status = "learning";
    }

    return { ...node, status, progress };
  });
}
