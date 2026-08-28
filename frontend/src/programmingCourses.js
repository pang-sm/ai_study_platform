/**
 * 编程学习方向统一课程身份。
 *
 * 编程学习侧栏语言标签为 C / C++ / Python / Java；知识点脉络、AI 问答、
 * 历史记录与资料引用都必须使用同一套稳定课程标识，禁止通过显示名或
 * 默认 fallback 猜测课程。
 *
 * 语言标签 → 稳定课程标识（canonical course_id + 标准显示名）：
 *   - courseId   英文 canonical id，用于知识点脉络（KnowledgeLearningPage）。
 *   - courseName 标准显示名，作为 AI 聊天 subject/course 的作用域（与后端
 *                normalize_subject_course_learning 的输出一致，保证 chat/history
 *                两端 scope 稳定）。
 */

export const PROGRAMMING_LANGUAGES = ["C", "C++", "Python", "Java"];

export const PROGRAMMING_COURSE_MAP = {
  C: { courseId: "c_programming", courseName: "C 语言程序设计" },
  "C++": { courseId: "cpp_programming", courseName: "C++ 程序设计" },
  Python: { courseId: "python_programming", courseName: "Python 程序设计" },
  Java: { courseId: "java_programming", courseName: "Java 程序设计" },
};

/**
 * 严格解析编程课程。未知语言直接抛错，不允许 silent fallback 到 Python 或其他默认课程。
 */
export function resolveProgrammingCourse(language) {
  const key = String(language || "").trim();
  const entry = PROGRAMMING_COURSE_MAP[key];
  if (!entry) {
    throw new Error(`未知编程课程：${key || "（空）"}。编程学习仅支持 C、C++、Python、Java。`);
  }
  return { language: key, ...entry };
}

/** 已知编程课程 id 集合（用于校验外部传入的 canonical course id）。 */
export const PROGRAMMING_COURSE_IDS = new Set(
  Object.values(PROGRAMMING_COURSE_MAP).map((item) => item.courseId)
);

export function isProgrammingCourseId(courseId) {
  return PROGRAMMING_COURSE_IDS.has(String(courseId || "").trim());
}

/** courseId → 语言标签（用于 URL 恢复） */
export const PROGRAMMING_COURSE_ID_TO_LANGUAGE = Object.fromEntries(
  Object.entries(PROGRAMMING_COURSE_MAP).map(([language, entry]) => [entry.courseId, language])
);

/** 严格解析 courseId → 编程课程；未知直接抛错 */
export function resolveProgrammingCourseById(courseId) {
  const language = PROGRAMMING_COURSE_ID_TO_LANGUAGE[String(courseId || "").trim()];
  if (!language) {
    throw new Error(`未知编程课程 ID：${courseId || "（空）"}。`);
  }
  return resolveProgrammingCourse(language);
}

// URL section（对外可恢复路径段）↔ 侧栏 activeNav 内部键
export const PROGRAMMING_SECTIONS = ["home", "knowledge", "workbench", "questions", "materials", "chat"];

export const SECTION_TO_NAV = {
  home: "home",
  knowledge: "status",
  workbench: "workbench",
  questions: "questions",
  materials: "materials",
  chat: "chat",
};

export const NAV_TO_SECTION = {
  home: "home",
  status: "knowledge",
  workbench: "workbench",
  questions: "questions",
  materials: "materials",
  chat: "chat",
};

export function isProgrammingSection(section) {
  return PROGRAMMING_SECTIONS.includes(String(section || "").trim());
}
