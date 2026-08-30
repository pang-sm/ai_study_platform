// Stable enum → user-facing Chinese labels. Keep the backend enum untouched;
// these are display-only mappings for the frontend.

export const PROGRAMMING_LEVEL_LABELS = {
  beginner_zero: "零基础",
  beginner: "入门",
  basic: "基础",
  advanced: "进阶",
};

export const PROGRAMMING_PROBLEM_LABELS = {
  concept_confusion: "概念理解不牢",
  syntax_confusion: "语法容易混淆",
  logic_to_code: "不会把思路转成代码",
  problem_analysis: "题目分析困难",
  debugging: "Debug / 定位错误困难",
  ds_algo_weak: "数据结构与算法薄弱",
  oop_unfamiliar: "面向对象不熟",
  no_plan: "缺少系统练习计划",
  engineering_weak: "代码规范 / 工程能力不足",
  no_clear_problem: "暂时没有明确问题",
};

export function formatProgrammingLevel(level) {
  if (!level) return "未设置";
  return PROGRAMMING_LEVEL_LABELS[level] || level;
}

export function formatProgrammingProblems(problems) {
  const list = Array.isArray(problems) ? problems : [];
  if (!list.length) return "未设置";
  return list.map((item) => PROGRAMMING_PROBLEM_LABELS[item] || item).join("、");
}

export function formatProgrammingLanguages(selectedLanguages, mainLanguage) {
  const list = Array.isArray(selectedLanguages) && selectedLanguages.length ? selectedLanguages : (mainLanguage ? [mainLanguage] : []);
  if (!list.length) return "未设置";
  return list.join("、");
}

/** ISO timestamp / date → YYYY-MM-DD；空值返回 "--"。纯字符串切片，不产生 Invalid Date。 */
export function formatDate(value) {
  const s = String(value || "").trim();
  if (!s) return "--";
  const datePart = s.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(datePart) ? datePart : "--";
}
