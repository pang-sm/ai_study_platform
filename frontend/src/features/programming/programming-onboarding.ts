import { programmingLanguages, type CanonicalProgrammingLanguage } from './programming-language';

/**
 * The onboarding vocabulary, mirroring the backend's own enums.
 *
 * The **keys are the contract** — `PROGRAMMING_LEVEL_ENUMS` and `PROGRAMMING_PROBLEM_ENUMS` in
 * the API — and are stored as-is. The Chinese strings are presentation only and are never sent:
 * the backend keeps its own label maps so that a stored fact does not depend on this file. The
 * backend does not expose either enum through an endpoint, so the lists are repeated here; a key
 * that the server stops accepting is refused by `/programming/onboarding` with its own 400 and
 * that message is what the learner sees.
 */
export const PROGRAMMING_LEVELS = [
  { key: 'beginner_zero', label: '零基础' },
  { key: 'beginner', label: '入门' },
  { key: 'basic', label: '基础' },
  { key: 'advanced', label: '进阶' },
] as const;

export const PROGRAMMING_PROBLEMS = [
  { key: 'concept_confusion', label: '概念理解不牢' },
  { key: 'syntax_confusion', label: '语法容易混淆' },
  { key: 'logic_to_code', label: '不会把思路转成代码' },
  { key: 'problem_analysis', label: '题目分析困难' },
  { key: 'debugging', label: 'Debug / 定位错误困难' },
  { key: 'ds_algo_weak', label: '数据结构与算法薄弱' },
  { key: 'oop_unfamiliar', label: '面向对象不熟' },
  { key: 'no_plan', label: '缺少系统练习计划' },
  { key: 'engineering_weak', label: '代码规范 / 工程能力不足' },
  { key: 'no_clear_problem', label: '暂时没有明确问题' },
] as const;

export type ProgrammingLevelKey = (typeof PROGRAMMING_LEVELS)[number]['key'];
export type ProgrammingProblemKey = (typeof PROGRAMMING_PROBLEMS)[number]['key'];

/** The four languages the runner can actually execute, in the order the product presents them. */
export const CANONICAL_LANGUAGES: readonly CanonicalProgrammingLanguage[] = [
  programmingLanguages.c,
  programmingLanguages.cpp,
  programmingLanguages.python,
  programmingLanguages.java,
];

const LEVEL_LABELS: Record<string, string> = Object.fromEntries(
  PROGRAMMING_LEVELS.map((level) => [level.key, level.label]),
);
const PROBLEM_LABELS: Record<string, string> = Object.fromEntries(
  PROGRAMMING_PROBLEMS.map((problem) => [problem.key, problem.label]),
);

/**
 * A stored level shown by its label. A key this build does not know is NOT shown as itself: the
 * stored value is a code from the API's enum, and a learner reading `beginner_zero` is reading the
 * backend's vocabulary, not their own setting. `未设置` is the honest product word for a level the
 * product cannot name — the form still shows what is selected and saving replaces it.
 */
export function levelLabel(key: string | null | undefined): string {
  const value = (key ?? '').trim();
  if (!value) return '未设置';
  return LEVEL_LABELS[value] ?? '未设置';
}

/** Same rule for the difficulty tags: an unknown code is `其他`, never the code. */
export function problemLabel(key: string): string {
  return PROBLEM_LABELS[key] ?? '其他';
}

/**
 * Keep only what the request may carry.
 *
 * The server accepts a language list, so a stored value that is not one of the four executable
 * languages is reported rather than quietly dropped: a learner whose stored context says
 * `JavaScript` should see that fact and be able to replace it, not have it vanish from the form
 * and survive in the database.
 */
export function splitLanguages(stored: readonly string[]): {
  known: CanonicalProgrammingLanguage[];
  unknown: string[];
} {
  const known: CanonicalProgrammingLanguage[] = [];
  const unknown: string[] = [];
  for (const item of stored) {
    const value = (item ?? '').trim();
    if (!value) continue;
    const match = CANONICAL_LANGUAGES.find((language) => language === value);
    if (match) {
      if (!known.includes(match)) known.push(match);
    } else if (!unknown.includes(value)) {
      unknown.push(value);
    }
  }
  return { known, unknown };
}

export type ProgrammingOnboardingState = {
  /** The languages the form may carry forward — the executable set, in canonical spelling. */
  languages: CanonicalProgrammingLanguage[];
  /** Stored languages the runner cannot execute; surfaced, never silently dropped. */
  unknownLanguages: string[];
  level: string;
  problems: string[];
  /** The stored package. The form never offers it; it is echoed back so a save cannot reset it. */
  plan: string;
  completed: boolean;
};

function stringsOf(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string');
}

/**
 * `GET /programming/onboarding` is typed `unknown` by the OpenAPI document, so it is read field
 * by field here rather than asserted. The old single-language field is folded in because the
 * backend still writes it for accounts that predate the list.
 */
export function readProgrammingOnboarding(value: unknown): ProgrammingOnboardingState {
  const row = (typeof value === 'object' && value !== null ? value : {}) as Record<string, unknown>;
  const stored = stringsOf(row.selected_languages);
  const mainLanguage = typeof row.main_language === 'string' ? row.main_language : '';
  const { known, unknown } = splitLanguages(stored.length ? stored : [mainLanguage]);
  return {
    languages: known,
    unknownLanguages: unknown,
    level: typeof row.level === 'string' ? row.level : '',
    problems: stringsOf(row.problems),
    plan: typeof row.plan === 'string' && row.plan ? row.plan : 'free',
    completed: row.onboarding_completed === true,
  };
}
