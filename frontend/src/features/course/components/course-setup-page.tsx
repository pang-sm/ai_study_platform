import { useState, type FormEvent } from 'react';
import { useNavigate } from '@tanstack/react-router';
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
import { CourseFrameworkPanel } from './course-framework-panel';

const controlClasses =
  'mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

/**
 * 学习设置 — the one place a learner's course context is edited.
 *
 * Three sections, because there are three different things to change and no more: who the
 * learner is (专业与年级), which courses they hold (我的课程), and where those courses sit in a
 * course of study (学习框架). The home page has one entry that lands here; nothing else in the
 * course space edits any of it.
 *
 * There is no course catalogue in the API — a course is created by being declared, and the
 * backend resolves a declared name onto the identity it already knows (`subjects.py`), keeping an
 * unrecognised name as itself. So 我的课程 is an editor over the declared set, not a picker over a
 * list that does not exist.
 *
 * One save writes all three: `course_learning_preferences` and the account row are one context,
 * and the endpoint takes one payload for it.
 */
/**
 * The courses to open the editor with.
 *
 * The declared list and the course space's own list are two views of one thing, and they can
 * disagree: `GET /course-learning/onboarding` reports only what the setup flow wrote, while the
 * course space also honours an account-level course list that predates it. Opening the editor on
 * the narrower of the two would show a learner who has courses an empty form. So the declared
 * list wins when it exists, and the courses the space actually holds are used otherwise — which
 * is the same set the learner can see on the 专业学习首页.
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
        <LoadingState label="正在读取学习设置…" />
      </div>
    );
  }

  if (onboarding.isError) {
    return (
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <PageHeader eyebrow="专业学习" title="学习设置" />
        <StatusNote tone="danger" className="mt-8">
          学习设置暂时无法读取，因此这里不能安全地保存。请稍后重试。
        </StatusNote>
      </div>
    );
  }

  return <CourseSetupForm initial={readCourseOnboarding(onboarding.data)} destination={destination} />;
}

function CourseSetupForm({
  initial,
  destination,
}: {
  initial: CourseOnboardingState;
  destination: string;
}) {
  const navigate = useNavigate();
  const save = useSaveCourseOnboarding();
  const catalog = useCourseCatalog();
  const establishedNow = readCourseList(catalog.data);

  const [courses, setCourses] = useState<string[]>(() => initialCourses(initial, establishedNow));
  const [goals, setGoals] = useState<Record<string, string>>(initial.courseGoals);
  // Which of the courses came from 智学AI推荐学习框架. Tracked here so the record can say so later:
  // the framework is recomputed against the CURRENT major, so it cannot be used after the fact to
  // reconstruct what was recommended when the learner actually confirmed.
  const [recommended, setRecommended] = useState<string[]>(initial.recommendedCourses);
  const [draft, setDraft] = useState('');
  const [major, setMajor] = useState(initial.major);
  const [grade, setGrade] = useState(initial.grade);
  const [semester, setSemester] = useState(initial.semester);
  const [errorText, setErrorText] = useState<string | null>(null);

  const addCourse = () => {
    const value = draft.trim().slice(0, 60);
    if (!value) return;
    setCourses((current) => (current.includes(value) ? current : [...current, value]));
    setDraft('');
    setGoals((current) => (value in current ? current : { ...current, [value]: '平日学习' }));
  };

  const removeCourse = (course: string) => {
    setCourses((current) => current.filter((value) => value !== course));
    // Dropping it also drops the provenance: re-adding it later is the learner's own act, not
    // the framework's.
    setRecommended((current) => current.filter((value) => value !== course));
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
        recommended_courses: recommended.filter((name) => courses.includes(name)),
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
      <PageHeader eyebrow="专业学习" title="学习设置" />

      <form onSubmit={onSubmit} noValidate className="mt-8 max-w-3xl space-y-12">
        <section aria-labelledby="course-setup-identity">
          <SectionHeading id="course-setup-identity" title="专业与年级" />
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

        <section aria-labelledby="course-setup-courses">
          <SectionHeading id="course-setup-courses" title="我的课程" />

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
            <EmptyState className="mt-6" title="还没有课程。" />
          )}
        </section>

        <CourseFrameworkPanel
          major={major}
          grade={grade}
          existing={courses}
          onAdd={(names) => {
            setCourses((current) => [...current, ...names.filter((name) => !current.includes(name))]);
            setRecommended((current) => [...current, ...names.filter((name) => !current.includes(name))]);
            setGoals((current) => {
              const next = { ...current };
              for (const name of names) if (!(name in next)) next[name] = '平日学习';
              return next;
            });
          }}
        />

        <SaveRow label="保存" isPending={save.isPending} saved={false} error={errorText} />
      </form>
    </div>
  );
}
