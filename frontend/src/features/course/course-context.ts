/**
 * Readers for the course space's two context payloads.
 *
 * Both endpoints (`/course-learning/onboarding`, `/course-learning/courses`) are typed `unknown`
 * by the OpenAPI document, so every field is read and checked here rather than asserted at the
 * call site. Nothing is invented: a field the server did not send reads as absent, and a course
 * without an id is reported as unusable rather than given a made-up key.
 */

export type CourseSummary = {
  id: string;
  name: string;
  /** `daily` | `exam` — the stored per-course mode, as the server states it. */
  primaryMode: string;
  /** The server's own label for that mode, so the page does not name it a second way. */
  primaryModeLabel: string;
  materialCount: number;
  pendingTaskCount: number;
};

export type CourseOnboardingState = {
  major: string;
  grade: string;
  semester: string;
  selectedCourses: string[];
  /** course name → 平日学习 / 考前突击, the two values the save endpoint accepts. */
  courseGoals: Record<string, string>;
};

function record(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === 'string' && item.trim() !== '');
}

/** The course rows `GET /course-learning/courses` returns, id-required. */
export function readCourseList(value: unknown): CourseSummary[] {
  const rows = Array.isArray(value)
    ? value
    : (record(value).courses ?? record(value).items ?? record(value).data);
  if (!Array.isArray(rows)) return [];
  return rows.flatMap((row) => {
    const item = record(row);
    const id = text(item.course_id) || text(item.id);
    if (!id) return [];
    return [
      {
        id,
        name: text(item.course_name) || text(item.display_name) || text(item.name) || id,
        primaryMode: text(item.primary_mode) || 'daily',
        primaryModeLabel: text(item.primary_mode_label) || '平日学习',
        materialCount: count(item.material_count),
        pendingTaskCount: count(item.pending_task_count),
      },
    ];
  });
}

/**
 * The stored course-learning context.
 *
 * `course_goals` is kept as the server stores it — the value is a goal label such as 平日学习,
 * and it is what a save sends back. Translating it to `daily`/`exam` here would put a second
 * vocabulary between the form and the record for no gain.
 */
export function readCourseOnboarding(value: unknown): CourseOnboardingState {
  const row = record(value);
  return {
    major: text(row.major),
    grade: text(row.grade),
    semester: text(row.semester),
    selectedCourses: stringList(row.selected_courses),
    courseGoals: Object.fromEntries(
      Object.entries(record(row.course_goals)).flatMap(([course, goal]) =>
        typeof goal === 'string' && goal ? [[course, goal] as const] : [],
      ),
    ),
  };
}

/** The two goals `POST /course-learning/onboarding` accepts for a course. */
export const COURSE_GOALS = [
  { value: '平日学习', label: '平日学习', detail: '按课程进度推进，资料与练习按日常节奏安排。' },
  { value: '考前突击', label: '考前突击', detail: '以考试日期与范围为中心安排复习。' },
] as const;

export const COURSE_GRADES = ['大一', '大二', '大三', '大四', '研究生'] as const;
export const COURSE_SEMESTERS = ['上学期', '下学期'] as const;
