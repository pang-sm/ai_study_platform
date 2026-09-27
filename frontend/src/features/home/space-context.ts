import { toCourseIdentity, useCourseCatalog } from '@/features/course/api/course';
import { useExamProfile } from '@/features/exam/api/profile';
import { useProgrammingOnboarding } from '@/features/programming/api/programming';

/**
 * Whether each learning space is actually set up — read from the space's own context, not from
 * the legacy account-level onboarding flag.
 *
 * `needs_onboarding` is a single boolean on the user row and it is only ever cleared by one
 * legacy programming route, so a learner who has declared courses and chosen exam subjects can
 * still carry `needs_onboarding: true` forever. Keying the first-user screen off it is what made
 * the prompt un-dismissable, so this reads the three spaces instead:
 *
 *   course_learning → the courses the learner has declared (`GET /course-learning/courses`)
 *   exam_prep       → the backend's own `configured` flag (`GET /exam/prep/profile`)
 *   programming     → the declared language context (`GET /programming/onboarding`)
 *
 * One configured space is enough: the product then behaves normally and the space itself, not
 * the home page, is where an unconfigured space explains itself.
 */
export type SpaceId = 'course' | 'exam' | 'programming';

export type SpaceContext = {
  id: SpaceId;
  label: string;
  /** What the space is organised around, in one line. */
  purpose: string;
  /** Where the learner stands in this direction, in one short line — or null when nothing
   *  recorded here can be said honestly. Never a count the space did not actually return. */
  status: string | null;
  /** What the card's link does, named from what this direction actually holds. Never a promise
   *  the space cannot keep, and never a claim about the learner. */
  cta: string;
  configured: boolean;
  pending: boolean;
  failed: boolean;
  /** The real place a learner changes this — never a stub. */
  action: { to: string; label: string; search?: Record<string, unknown> };
  /** What is missing, stated as a fact. */
  missing: string;
};

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is string => typeof entry === 'string' && Boolean(entry.trim()))
    : [];
}

function listOf(value: unknown, keys: readonly string[]): unknown[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'object' && value !== null) {
    const row = value as Record<string, unknown>;
    for (const key of keys) {
      if (Array.isArray(row[key])) return row[key] as unknown[];
    }
  }
  return [];
}

export function useSpaceContext(): {
  spaces: SpaceContext[];
  anyConfigured: boolean;
  /** True once every space has answered, so the home page never guesses mid-flight. */
  settled: boolean;
  /** Declared course id → its own display name, so a course id is never printed raw. */
  courseNames: Map<string, string>;
} {
  const courses = useCourseCatalog();
  const exam = useExamProfile();
  const programming = useProgrammingOnboarding();

  const courseRows = listOf(courses.data, ['courses', 'items', 'data']);
  const courseIdentities = courseRows.map(toCourseIdentity);
  const courseNames = new Map<string, string>();
  for (const identity of courseIdentities) {
    if (identity.id && identity.name) courseNames.set(identity.id, identity.name);
  }
  const declaredCourseNames = courseIdentities
    .map((identity) => identity.name)
    .filter((name): name is string => Boolean(name));

  const courseConfigured = courseRows.length > 0;
  // `configured` is the backend's own statement; the subject list is the same fact spelled out.
  const examConfigured = Boolean(exam.data?.configured) || (exam.data?.subjects?.length ?? 0) > 0;
  const programmingPayload = programming.data as Record<string, unknown> | undefined;
  const programmingConfigured = Boolean(
    (typeof programmingPayload?.main_language === 'string' && programmingPayload.main_language) ||
      (Array.isArray(programmingPayload?.selected_languages) && programmingPayload.selected_languages.length) ||
      programmingPayload?.onboarding_completed === true,
  );

  // What each direction says about itself, built only from values its own endpoint returned. A
  // direction with nothing recorded states nothing: an empty line is honest, a zero is a claim.
  const examSubjectNames = (exam.data?.subjects ?? [])
    .map((subject) => ('display_name' in subject ? subject.display_name : undefined))
    .filter((name): name is string => typeof name === 'string' && Boolean(name.trim()));
  const selectedSubjectCount = exam.data?.selected_subjects?.length ?? 0;
  const mainLanguage = typeof programmingPayload?.main_language === 'string'
    ? programmingPayload.main_language.trim()
    : '';
  const selectedLanguages = stringList(programmingPayload?.selected_languages);

  const courseStatus = declaredCourseNames.length === 1
    ? `课程：${declaredCourseNames[0]}`
    : declaredCourseNames.length > 1
      ? `已声明 ${declaredCourseNames.length} 门课程`
      : null;
  const examStatus = examSubjectNames.length
    ? `备考：${examSubjectNames.slice(0, 2).join(' · ')}${
        examSubjectNames.length > 2 ? ` 等 ${examSubjectNames.length} 科` : ''
      }`
    : selectedSubjectCount
      ? `已选择 ${selectedSubjectCount} 个科目`
      : null;
  const programmingStatus = mainLanguage
    ? `当前语言：${mainLanguage}`
    : selectedLanguages.length
      ? `已声明：${selectedLanguages.slice(0, 3).join(' · ')}`
      : null;

  // What each card's link says it does. A declared value names the thing it opens (the language
  // being practised, the courses being studied); a direction with nothing declared, or one whose
  // read failed, gets a wording that promises nothing it cannot verify.
  const language = mainLanguage || selectedLanguages[0] || '';
  const courseCta = courses.isError ? '进入专业学习' : courseConfigured ? '查看课程' : '开始专业学习';
  const examCta = exam.isError ? '进入考研学习' : examConfigured ? '进入备考' : '开始备考';
  const programmingCta = programming.isError
    ? '进入编程学习'
    : language
      ? `继续 ${language} 编程`
      : '开始编程学习';

  // Every action is the space's own setup screen, and each one is asked to come back here. The
  // three rows are the same three screens the profile points at, so there is one place per space
  // where its context is established rather than a second, indirect one.
  const spaces: SpaceContext[] = [
    {
      id: 'course',
      label: '专业学习',
      purpose: '按课程组织资料、知识点、练习与错题。',
      status: courses.isError ? null : courseStatus,
      cta: courseCta,
      configured: courseConfigured,
      pending: courses.isPending,
      failed: courses.isError,
      action: { to: '/course/setup', label: '设置课程', search: { returnTo: '/' } },
      missing: '还没有声明任何课程。',
    },
    {
      id: 'exam',
      label: '11408 考研学习',
      purpose: '按考试科目与模块组织备考、真题与错题。',
      status: exam.isError ? null : examStatus,
      cta: examCta,
      configured: examConfigured,
      pending: exam.isPending,
      failed: exam.isError,
      action: { to: '/exam/setup', label: '设置备考', search: { returnTo: '/' } },
      missing: '还没有选择备考方向与科目。',
    },
    {
      id: 'programming',
      label: '编程学习',
      purpose: '按语言组织练习、运行、提交与调试。',
      status: programming.isError ? null : programmingStatus,
      cta: programmingCta,
      configured: programmingConfigured,
      pending: programming.isPending,
      failed: programming.isError,
      action: { to: '/programming/setup', label: '设置编程学习', search: { returnTo: '/' } },
      missing: '还没有声明编程语言。',
    },
  ];

  const settled = spaces.every((space) => !space.pending);
  return { spaces, anyConfigured: spaces.some((space) => space.configured), settled, courseNames };
}
