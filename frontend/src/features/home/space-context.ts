import { useCourseCatalog } from '@/features/course/api/course';
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
  configured: boolean;
  pending: boolean;
  failed: boolean;
  /** The real place a learner changes this — never a stub. */
  action: { to: string; label: string; search?: Record<string, unknown> };
  /** What is missing, stated as a fact. */
  missing: string;
};

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
} {
  const courses = useCourseCatalog();
  const exam = useExamProfile();
  const programming = useProgrammingOnboarding();

  const courseConfigured = listOf(courses.data, ['courses', 'items', 'data']).length > 0;
  // `configured` is the backend's own statement; the subject list is the same fact spelled out.
  const examConfigured = Boolean(exam.data?.configured) || (exam.data?.subjects?.length ?? 0) > 0;
  const programmingPayload = programming.data as Record<string, unknown> | undefined;
  const programmingConfigured = Boolean(
    (typeof programmingPayload?.main_language === 'string' && programmingPayload.main_language) ||
      (Array.isArray(programmingPayload?.selected_languages) && programmingPayload.selected_languages.length) ||
      programmingPayload?.onboarding_completed === true,
  );

  // Every action is the space's own setup screen, and each one is asked to come back here. The
  // three rows are the same three screens the profile points at, so there is one place per space
  // where its context is established rather than a second, indirect one.
  const spaces: SpaceContext[] = [
    {
      id: 'course',
      label: '课程学习',
      purpose: '按课程组织资料、知识点、练习与错题。',
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
      configured: programmingConfigured,
      pending: programming.isPending,
      failed: programming.isError,
      action: { to: '/programming/setup', label: '设置编程学习', search: { returnTo: '/' } },
      missing: '还没有声明编程语言。',
    },
  ];

  const settled = spaces.every((space) => !space.pending);
  return { spaces, anyConfigured: spaces.some((space) => space.configured), settled };
}
