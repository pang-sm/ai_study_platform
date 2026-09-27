/**
 * 学习框架 — the bands a course of study is read in.
 *
 * WHAT THIS IS
 * A learner declares a major and a grade, the backend answers with the courses it associates
 * with that major (`GET /membership/recommendation` → `suggested_courses`), and this file turns a
 * flat list of course names — the recommended ones and the learner's own — into the five bands a
 * course of study is actually read in: 数学基础 / 物理基础 / 专业基础 / 专业核心 / 方向课程.
 *
 * WHAT THIS IS NOT
 * It is not a curriculum. The bands are a reading order, not a syllabus: nothing here says a
 * course is compulsory, in which semester it is taught, how much credit it carries, or that any
 * institution requires it.
 *
 * The classification is by course name because that is the only thing the recommendation carries.
 * A name no rule recognises is not forced into a band it does not belong to; it goes to 方向课程,
 * which is where an elective belongs by default.
 */
export const FRAMEWORK_CATEGORIES = ['数学基础', '物理基础', '专业基础', '专业核心', '方向课程'] as const;
export type FrameworkCategory = (typeof FRAMEWORK_CATEGORIES)[number];

/**
 * Which band a course name belongs to, tried in this order.
 *
 * The rules are ordered and the first match wins, which is what puts 数据结构基础 in 专业核心
 * rather than 专业基础: a course whose subject is unambiguous belongs with its subject, and the
 * word 基础 modifies it rather than reclassifying it.
 */
const RULES: ReadonlyArray<{ category: FrameworkCategory; keywords: readonly string[] }> = [
  { category: '数学基础', keywords: ['数学', '代数', '概率', '统计', '离散'] },
  { category: '物理基础', keywords: ['物理', '力学', '电磁', '光学', '电路'] },
  {
    category: '专业核心',
    keywords: ['数据结构', '操作系统', '计算机网络', '数据库', '算法', '编译', '计算机组成', '软件工程'],
  },
  {
    category: '专业基础',
    keywords: [
      '程序设计', '编程', '语言', '基础', '导论', '入门', '建模', '仿真',
      'Python', '数据分析', '可视化', '办公自动化',
    ],
  },
];

export function classifyCourse(name: string): FrameworkCategory {
  for (const rule of RULES) {
    if (rule.keywords.some((keyword) => name.includes(keyword))) return rule.category;
  }
  return '方向课程';
}

/**
 * Which bands a grade reads first.
 *
 * This is display order and nothing more — an earlier-year student meets the foundations before
 * the core, a later-year student is already past them. It is not a statement about the learner.
 */
export function gradeOrder(grade: string): readonly FrameworkCategory[] {
  const later = grade === '大三' || grade === '大四' || grade === '研究生';
  return later
    ? ['专业核心', '方向课程', '专业基础', '数学基础', '物理基础']
    : ['数学基础', '物理基础', '专业基础', '专业核心', '方向课程'];
}

export type FrameworkBand = { category: FrameworkCategory; courses: readonly string[] };

/** A flat list of course names, grouped into bands and ordered for the grade. Empty bands are dropped. */
export function buildFramework(courses: readonly string[], grade: string): FrameworkBand[] {
  const grouped = new Map<FrameworkCategory, string[]>();
  for (const course of courses) {
    const name = course.trim();
    if (!name) continue;
    const category = classifyCourse(name);
    const bucket = grouped.get(category);
    if (bucket) bucket.push(name);
    else grouped.set(category, [name]);
  }
  return gradeOrder(grade)
    .flatMap((category) => {
      const names = grouped.get(category);
      return names?.length ? [{ category, courses: names }] : [];
    });
}
