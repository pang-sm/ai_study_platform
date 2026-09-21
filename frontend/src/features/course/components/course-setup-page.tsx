import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { SaveRow } from '@/components/ui/save-row';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { TextField } from '@/components/ui/text-field';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { resolveReturnDestination } from '@/features/auth/return-to';
import {
  COURSE_GOALS,
  COURSE_GRADES,
  COURSE_SEMESTERS,
  readCourseList,
  readCourseOnboarding,
  type CourseOnboardingState,
  type CourseSummary,
} from '../course-context';
import { useCourseCatalog, useCourseOnboarding, useSaveCourseOnboarding } from '../api/course';

const controlClasses =
  'mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

/**
 * Where a learner's course context is established.
 *
 * There is no course catalogue in the API — a course is created by being declared, and the
 * backend resolves a declared name onto the identity it already knows (`subjects.py`), keeping an
 * unrecognised name as itself. So this screen is an editor over the declared set, and it says so:
 * the field is a name field, not a picker over a list that does not exist. Nothing here is
 * pre-filled from a client-side list of "available courses".
 *
 * The course rows are the unit the product actually works in: `course_learning_preferences` is
 * keyed by course, and materials, knowledge points, practice and wrong answers all hang off one.
 * Each row therefore carries its own goal, because the backend stores one per course.
 */
/**
 * The courses to open the editor with.
 *
 * The declared list and the course space's own list are two views of one thing, and they can
 * disagree: `GET /course-learning/onboarding` reports only what the setup flow wrote, while the
 * course space also honours an account-level course list that predates it. Opening the editor on
 * the narrower of the two would show a learner who has courses an empty form. So the declared
 * list wins when it exists, and the courses the space actually holds are used otherwise — which
 * is the same set the learner can see on the课程学习首页.
 */
function initialCourses(state: CourseOnboardingState, established: readonly CourseSummary[]): string[] {
  if (state.selectedCourses.length) return state.selectedCourses;
  return established.map((course) => course.name);
}

export function CourseSetupPage({ returnTo }: { returnTo?: string }) {
  const onboarding = useCourseOnboarding();
  const catalog = useCourseCatalog();
  const destination = resolveReturnDestination(returnTo, '/course');

  if (onboarding.isPending || catalog.isPending) {
    return (
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <LoadingState label="正在读取课程设置…" />
      </div>
    );
  }

  if (onboarding.isError) {
    return (
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <PageHeader eyebrow="课程学习" title="课程学习设置" />
        <StatusNote tone="danger" className="mt-8">
          课程设置暂时无法读取，因此这里不能安全地保存。请稍后重试。
        </StatusNote>
      </div>
    );
  }

  const state = readCourseOnboarding(onboarding.data);
  return (
    <CourseSetupForm
      initial={state}
      seededFromSpace={state.selectedCourses.length === 0}
      destination={destination}
    />
  );
}

function CourseSetupForm({
  initial,
  seededFromSpace,
  destination,
}: {
  initial: CourseOnboardingState;
  /** True when the opening list came from the courses the space already holds. */
  seededFromSpace: boolean;
  destination: string;
}) {
  const navigate = useNavigate();
  const save = useSaveCourseOnboarding();
  const catalog = useCourseCatalog();
  const establishedNow = readCourseList(catalog.data);

  const [courses, setCourses] = useState<string[]>(() => initialCourses(initial, establishedNow));
  const [goals, setGoals] = useState<Record<string, string>>(initial.courseGoals);
  const [draft, setDraft] = useState('');
  const [major, setMajor] = useState(initial.major);
  const [grade, setGrade] = useState(initial.grade);
  const [semester, setSemester] = useState(initial.semester);
  const [errorText, setErrorText] = useState<string | null>(null);

  const established = establishedNow;
  const configured = initial.selectedCourses.length > 0;

  const addCourse = () => {
    const value = draft.trim().slice(0, 60);
    if (!value) return;
    setCourses((current) => (current.includes(value) ? current : [...current, value]));
    setDraft('');
    setGoals((current) => (value in current ? current : { ...current, [value]: '平日学习' }));
  };

  const removeCourse = (course: string) => {
    setCourses((current) => current.filter((value) => value !== course));
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorText(null);
    // The three checks the endpoint refuses on, applied here first so the learner is told in the
    // same place they are typing. The messages are the server's own wording, not a second
    // explanation of the same rule.
    if (courses.length === 0) {
      setErrorText('请选择至少一门想学习的课程');
      return;
    }
    if (!major.trim()) {
      setErrorText('请选择专业');
      return;
    }
    if (!grade) {
      setErrorText('请选择年级');
      return;
    }
    try {
      await save.mutateAsync({
        major: major.trim(),
        grade,
        semester,
        selected_courses: courses,
        // The request type requires the key. An empty list is the honest value — this screen does
        // not ask about material types — and the endpoint keeps any existing value for an
        // already-onboarded learner rather than replacing it with the empty one.
        material_types: [],
        course_goals: Object.fromEntries(courses.map((course) => [course, goals[course] ?? '平日学习'])),
        onboarding_completed: true,
      });
      await navigate({ href: destination });
    } catch (error) {
      setErrorText(
        error instanceof ApiRequestError
          ? (serverMessage(error.detail) ?? '保存未成功，请稍后重试。')
          : '网络连接异常，请检查网络后重试。',
      );
    }
  };

  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="课程学习"
        title={configured ? '课程学习设置' : '设置课程学习'}
        description="课程学习按课组织：资料、知识点、练习、错题与计划都挂在你声明的课程下。先声明课程，空间里才有内容可做。"
      />

      <form onSubmit={onSubmit} noValidate className="mt-8 max-w-3xl space-y-12">
        <section aria-labelledby="course-setup-courses">
          <SectionHeading
            id="course-setup-courses"
            title="你的课程"
            description="填写课程名称并添加。平台会把已知的课程名归并到同一门课；无法识别的名称会按你填写的内容保存。"
          />

          {seededFromSpace && established.length ? (
            <StatusNote className="mt-5">
              下面的课程来自课程学习空间当前已有的课程。保存后，它们会一并写入你的课程设置。
            </StatusNote>
          ) : null}

          <div className="mt-5 flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1">
              <TextField
                label="添加课程"
                name="course-draft"
                type="text"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter') return;
                  // Enter adds a course here; it must not submit a half-filled form.
                  event.preventDefault();
                  addCourse();
                }}
                placeholder="例如：数据结构"
              />
            </div>
            <Button type="button" variant="secondary" onClick={addCourse}>
              添加到课程
            </Button>
          </div>

          {courses.length ? (
            <ul className="mt-6 border-t border-border-default">
              {courses.map((course) => (
                <li
                  key={course}
                  className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 border-b border-border-default py-4"
                >
                  <div className="min-w-0">
                    <p className="text-body font-medium text-text-primary">{course}</p>
                  </div>
                  <div className="flex flex-wrap items-end gap-3">
                    <div>
                      <label
                        htmlFor={`course-goal-${course}`}
                        className="block text-metadata text-text-secondary"
                      >
                        学习方式
                      </label>
                      <select
                        id={`course-goal-${course}`}
                        value={goals[course] ?? '平日学习'}
                        onChange={(event) =>
                          setGoals((current) => ({ ...current, [course]: event.target.value }))
                        }
                        className="mt-1 h-11 rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                      >
                        {COURSE_GOALS.map((goal) => (
                          <option key={goal.value} value={goal.value}>
                            {goal.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() => removeCourse(course)}
                      aria-label={`移除课程 ${course}`}
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      移除
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              className="mt-6"
              title="还没有添加课程。"
              description="课程由你声明的名称建立；至少添加一门才能保存。"
            />
          )}
        </section>

        <section aria-labelledby="course-setup-identity">
          <SectionHeading
            id="course-setup-identity"
            title="学习信息"
            description="专业、年级与学期会写入你的学习档案，并作为课程内容匹配的依据。"
          />
          <div className="mt-5 space-y-5">
            <TextField
              label="专业"
              name="course-major"
              type="text"
              value={major}
              onChange={(event) => setMajor(event.target.value)}
              placeholder="例如：计算机科学与技术"
            />
            <div>
              <label htmlFor="course-setup-grade" className="block text-body font-medium text-text-primary">
                年级
              </label>
              <select
                id="course-setup-grade"
                value={grade}
                onChange={(event) => setGrade(event.target.value)}
                className={controlClasses}
              >
                <option value="">未选择</option>
                {COURSE_GRADES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="course-setup-semester" className="block text-body font-medium text-text-primary">
                学期
              </label>
              <select
                id="course-setup-semester"
                value={semester}
                onChange={(event) => setSemester(event.target.value)}
                className={controlClasses}
              >
                <option value="">未填写</option>
                {COURSE_SEMESTERS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {courses.length === 0 ? (
          <StatusNote tone="warning">请至少添加一门课程。</StatusNote>
        ) : null}
        {courses.length > 0 && !major.trim() ? (
          <StatusNote tone="warning">请填写专业。</StatusNote>
        ) : null}
        {courses.length > 0 && !grade ? <StatusNote tone="warning">请选择年级。</StatusNote> : null}

        <SaveRow
          label={configured ? '保存课程设置' : '保存并开始'}
          isPending={save.isPending}
          saved={false}
          error={errorText}
        />
      </form>

      <section aria-labelledby="course-setup-established" className="mt-12 border-t border-border-default pt-8">
        <SectionHeading
          id="course-setup-established"
          title="课程空间中已建立的课程"
          description="这些是服务端当前真正持有的课程，以及它们已有的资料与待办。"
        />
        {catalog.isPending ? (
          <LoadingState label="正在读取已建立的课程…" className="mt-5" />
        ) : catalog.isError ? (
          <StatusNote tone="warning" className="mt-5">
            已建立的课程暂时无法读取；这不影响上面的保存。
          </StatusNote>
        ) : established.length ? (
          <>
            {/* The two lists are one thing seen twice: the editor holds what the learner
                declared, this holds what the space really built. Saying so per row is what
                stops the reader from having to work out whether the same name in both places
                means the same course — without taking away the link into either of them. */}
            <p className="mt-5 max-w-3xl text-body text-text-secondary">
              {established.every((course) => courses.includes(course.name))
                ? '这些课程已经在上面的列表里；下面是它们在课程学习空间中的实际状态。'
                : '下面这些课程已经在课程学习空间中建立；其中标注的课程同时也在上面的列表里。'}
            </p>
            <ul className="mt-3 max-w-3xl border-t border-border-default">
              {established.map((course) => (
                <li
                  key={course.id}
                  className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-border-default py-4"
                >
                  <span className="flex flex-wrap items-baseline gap-x-3">
                    <Link
                      to="/course/$courseId"
                      params={{ courseId: course.id }}
                      className="text-body font-medium text-primary-ink hover:text-primary-hover"
                    >
                      {course.name}
                    </Link>
                    {courses.includes(course.name) ? (
                      <span className="text-metadata text-text-muted">已在上方列出</span>
                    ) : null}
                  </span>
                  <p className="text-metadata text-text-secondary">
                    {course.primaryModeLabel} · 资料 {course.materialCount} · 待办任务 {course.pendingTaskCount}
                  </p>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <EmptyState
            className="mt-5"
            title="课程空间里还没有课程。"
            description="保存上面的课程后，它们会出现在这里，并出现在课程学习首页。"
          />
        )}
      </section>
    </div>
  );
}
