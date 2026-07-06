/**
 * 课程学习方向统一课程目录
 * 所有 course_learning 页面均以此目录为准。
 */

export const COURSE_LEARNING_CATALOG = [
  { displayName: "计算机导论",           courseId: "computer_intro" },
  { displayName: "程序设计基础",         courseId: "programming_fundamentals" },
  { displayName: "C 语言程序设计",       courseId: "c_programming" },
  { displayName: "Python 程序设计",      courseId: "python_programming" },
  { displayName: "Java 程序设计",        courseId: "java_programming" },
  { displayName: "面向对象程序设计",     courseId: "oop" },
  { displayName: "数据结构",             courseId: "data_structure" },
  { displayName: "算法设计与分析",       courseId: "algorithm_design" },
  { displayName: "离散数学",             courseId: "discrete_math" },
  { displayName: "数字逻辑",             courseId: "digital_logic" },
  { displayName: "计算机组成原理",       courseId: "computer_organization" },
  { displayName: "操作系统",             courseId: "operating_system" },
  { displayName: "计算机网络",           courseId: "computer_network" },
  { displayName: "数据库系统",           courseId: "database_systems" },
  { displayName: "软件工程",             courseId: "software_engineering" },
  { displayName: "编译原理",             courseId: "compiler_principles" },
  { displayName: "Linux / Unix 系统基础", courseId: "linux_unix_basics" },
];

/** 仅显示名列表（兼容旧代码 .map 直接取字符串） */
export const COURSE_DISPLAY_NAMES = COURSE_LEARNING_CATALOG.map((c) => c.displayName);

/** 仅 courseId 列表 */
export const COURSE_IDS = COURSE_LEARNING_CATALOG.map((c) => c.courseId);

/** displayName → courseId 反查 */
export const DISPLAY_TO_ID = {};
for (const c of COURSE_LEARNING_CATALOG) {
  DISPLAY_TO_ID[c.displayName] = c.courseId;
}

/** courseId → displayName 反查 */
export const ID_TO_DISPLAY = {};
for (const c of COURSE_LEARNING_CATALOG) {
  ID_TO_DISPLAY[c.courseId] = c.displayName;
}

/**
 * 课程学习专用 normalize：把用户输入/历史名称统一为标准 displayName。
 * 若无法匹配，返回原始输入（不强制改名）。
 */
const COURSE_ALIAS_MAP = {
  // 旧名 → 标准名
  "C语言": "C 语言程序设计",
  "C 语言": "C 语言程序设计",
  "C语言程序设计": "C 语言程序设计",
  "c语言": "C 语言程序设计",
  "Python": "Python 程序设计",
  "python": "Python 程序设计",
  "Python程序设计": "Python 程序设计",
  "Java": "Java 程序设计",
  "java": "Java 程序设计",
  "Java程序设计": "Java 程序设计",
  "数据结构与算法": "数据结构",
  "互联网计算": "计算机网络",
  "网络": "计算机网络",
  "计算机操作系统": "操作系统",
  "计算机组成结构": "计算机组成原理",
  "计算机组成": "计算机组成原理",
  "数据管理": "数据库系统",
  "数据库": "数据库系统",
  "面向对象": "面向对象程序设计",
  "OOP": "面向对象程序设计",
  "oop": "面向对象程序设计",
  "Linux": "Linux / Unix 系统基础",
  "Unix": "Linux / Unix 系统基础",
  "Linux基础": "Linux / Unix 系统基础",
  "Unix基础": "Linux / Unix 系统基础",
};

export function normalizeCourseLearningName(raw) {
  const key = (raw || "").trim();
  if (!key) return "";
  // 精确匹配标准目录
  if (DISPLAY_TO_ID[key]) return key;
  // 别名映射
  if (COURSE_ALIAS_MAP[key]) return COURSE_ALIAS_MAP[key];
  // 大小写 insensitive
  const lowered = key.toLowerCase();
  if (COURSE_ALIAS_MAP[lowered]) return COURSE_ALIAS_MAP[lowered];
  // 未匹配 → 返回原值（兼容已有数据）
  return key;
}

/** 获取 courseId（先尝试 normalize，再查表） */
export function resolveCourseId(displayName) {
  const normalized = normalizeCourseLearningName(displayName);
  return DISPLAY_TO_ID[normalized] || "";
}

/** 获取显示名 */
export function resolveDisplayName(input) {
  const normalized = normalizeCourseLearningName(input);
  return normalized || input;
}
