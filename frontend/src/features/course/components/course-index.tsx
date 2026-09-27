import { Link } from '@tanstack/react-router';
import { EmptyState } from '@/components/ui/empty-state';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { useCourseCatalog, useCourseOnboarding } from '@/features/course/api/course';
import { readCourseList, readCourseOnboarding, type CourseSummary } from '@/features/course/course-context';
import { useRecentRecords, type LearningRecord } from '@/features/records/api/learning-records';

const secondaryAction =
  'inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-4 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

const primaryAction =
  'inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

/** The one course the learner was last active in, from the stream the server keeps. */
function mostRecentCourseId(
  records: readonly LearningRecord[] | undefined,
  known: ReadonlySet<string>,
): string | undefined {
  for (const record of records ?? []) {
    const id = record.context?.course_id;
    if (id && known.has(id)) return id;
  }
  return undefined;
}

/**
 * One course, as this page lists it: the name, and where it leads.
 *
 * The action is named only when the server has a fact behind it — the course the learner was last
 * active in is 继续学习, the rest are 进入课程. Before there is any activity there is nothing to
 * claim, so the rows are bare names and the whole row is the link.
 */
function CourseRow({ course, action }: { course: CourseSummary; action?: string }) {
  return (
    <li className="border-b border-border-default">
      <Link
        to="/course/$courseId"
        params={{ courseId: course.id }}
        className="flex min-h-14 flex-wrap items-center gap-x-3 gap-y-1 py-4 hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        <span className="min-w-0 flex-1 text-body font-medium text-text-primary">{course.name}</span>
        {action ? <span className="text-metadata text-text-secondary">{action}</span> : null}
      </Link>
    </li>
  );
}

/**
 * The professional-learning home.
 *
 * It states where the learner stands and gets out of the way: the declared major and grade, one
 * course to continue, and the courses themselves. Everything that *changes* the course set lives
 * behind the single 学习设置 entry — the home no longer offers 调整专业与年级 / 调整课程 /
 * 查看完整学习框架 as three destinations for one settings surface.
 */
export function CourseIndex() {
  const catalog = useCourseCatalog();
  const onboarding = useCourseOnboarding();
  const recent = useRecentRecords(8, 'course_learning');

  const courses = readCourseList(catalog.data);
  const declared = readCourseOnboarding(onboarding.data);
  const known = new Set(courses.map((course) => course.id));
  const recentId = mostRecentCourseId(recent.data, known);
  // "Continue" is the course the learner was last active in; before there is any activity the
  // first declared course stands in for it.
  const current = courses.find((course) => course.id === recentId) ?? courses[0];
  const declaredContext = [declared.major, declared.grade].filter(Boolean).join(' · ');

  return (
    <div className="space-accent space-accent--course mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        title="专业学习"
        meta={
          declaredContext ? (
            <span className="text-body text-text-secondary">{declaredContext}</span>
          ) : undefined
        }
        actions={
          <Link to="/course/setup" search={{ returnTo: '/course' }} className={secondaryAction}>
            学习设置
          </Link>
        }
      />

      {catalog.isPending ? (
        <LoadingState label="正在读取课程…" className="mt-8" />
      ) : catalog.isError ? (
        <StatusNote tone="danger" className="mt-8">
          课程列表暂时无法加载。
        </StatusNote>
      ) : courses.length === 0 ? (
        <EmptyState className="mt-8" title="还没有课程。" />
      ) : (
        <>
          {current ? (
            <section className="mt-8" aria-labelledby="course-continue-title">
              <SectionHeading id="course-continue-title" eyebrow="继续学习" title={current.name} />
              <div className="mt-5 flex flex-wrap gap-3">
                <Link to="/course/$courseId" params={{ courseId: current.id }} className={primaryAction}>
                  进入课程
                </Link>
              </div>
            </section>
          ) : null}

          <section className="mt-10 border-t border-border-default pt-6" aria-labelledby="course-mine-title">
            <SectionHeading id="course-mine-title" title="我的课程" />
            <ul className="mt-4 border-t border-border-default">
              {courses.map((course) => (
                <CourseRow
                  key={course.id}
                  course={course}
                  action={
                    recentId ? (course.id === current?.id ? '继续学习' : '进入课程') : undefined
                  }
                />
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
