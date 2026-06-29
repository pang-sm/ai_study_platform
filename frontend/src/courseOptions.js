export const DEFAULT_SUBJECT = "计算系统基础";

export const COURSE_OPTIONS = [
  DEFAULT_SUBJECT,
  "C语言",
  "C++",
  "Python",
  "Java",
  "离散数学",
  "数据结构与算法",
  "计算机组成结构",
  "互联网计算",
  "计算机操作系统",
  "编译原理",
  "数据管理",
  "人机交互",
];

export const SUBJECT_ALIASES = {
  "": DEFAULT_SUBJECT,
  "数据库": "数据管理",
  "数据管理": "数据管理",
  "操作系统": "计算机操作系统",
  "计算机操作系统": "计算机操作系统",
  "计算机组成": "计算机组成结构",
  "计算机组成原理": "计算机组成结构",
  "计算机组成结构": "计算机组成结构",
  "计算机网络": "计算机网络",
  "网络": "互联网计算",
  "互联网计算": "互联网计算",
  "数据结构": "数据结构与算法",
  "算法": "数据结构与算法",
  "数据结构与算法": "数据结构与算法",
  "C": "C语言",
  "c": "C语言",
  "C语言": "C语言",
  "C++": "C++",
  "c++": "C++",
  "c＋+": "C++",
  "C＋+": "C++",
  "Python": "Python",
  "python": "Python",
  "Java": "Java",
  "java": "Java",
  "离散数学": "离散数学",
  "编译原理": "编译原理",
  "人机交互": "人机交互",
  "计算系统基础": DEFAULT_SUBJECT,
};

export function normalizeSubject(subject, fallback = DEFAULT_SUBJECT) {
  const rawValue = String(subject || "").trim();
  if (!rawValue) return fallback;

  if (SUBJECT_ALIASES[rawValue]) return SUBJECT_ALIASES[rawValue];

  const lowered = rawValue.toLowerCase();
  if (SUBJECT_ALIASES[lowered]) return SUBJECT_ALIASES[lowered];

  return rawValue;
}

export function getSubjectLabel(subject) {
  return normalizeSubject(subject, "") || "";
}
