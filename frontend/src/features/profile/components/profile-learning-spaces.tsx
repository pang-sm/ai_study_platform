import { Link } from '@tanstack/react-router';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { useCourseCatalog } from '@/features/course/api/course';
import { readCourseList } from '@/features/course/course-context';
import { useExamProfile } from '@/features/exam/api/profile';
import { useProgrammingOnboarding } from '@/features/programming/api/programming';
import { readProgrammingOnboarding } from '@/features/programming/programming-onboarding';
import { routePath } from '@/lib/router';

/**
 * The three learning spaces, read from the spaces themselves.
 *
 * This section deliberately keeps no copy of any setting: every number and every name below is
 * the server's current answer, fetched through the same query keys the spaces use, so a change
 * made in a setup flow is what this section shows the next time it renders. Editing happens in
 * one place per space — the header states that, and the rows only report and link.
 *
 * A space whose state cannot be read says so rather than showing "未设置", because the two are
 * different facts and only one of them is the learner's to fix.
 */
function Row({
  title,
  configured,
  pending,
  failed,
  missing,
  state,
  to,
  search,
  action,
}: {
  title: string;
  configured: boolean;
  pending: boolean;
  failed: boolean;
  missing: string;
  state: string;
  to: string;
  search: Record<string, unknown>;
  action: string;
}) {
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-border-default py-5">
      <div className="min-w-0">
        <p className="text-body font-medium text-text-primary">{title}</p>
        {pending ? (
          <Skeleton className="mt-2 h-4 w-52" />
        ) : (
          <p className="mt-1 max-w-prose text-body text-text-secondary">
            {failed ? '暂时无法读取这个学习空间的状态。' : configured ? state : missing}
          </p>
        )}
      </div>
      <Link
        to={routePath(to)}
        search={search}
        className="inline-flex h-11 shrink-0 items-center rounded-control border border-border-default bg-surface px-4 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        {action}
      </Link>
    </li>
  );
}

export function LearningSpacesSection() {
  const courses = useCourseCatalog();
  const exam = useExamProfile();
  const programming = useProgrammingOnboarding();

  const courseList = readCourseList(courses.data);
  const programmingState = readProgrammingOnboarding(programming.data);
  const examSubjects = exam.data?.subjects?.length ?? 0;
  const examConfigured = Boolean(exam.data?.configured) || examSubjects > 0;

  return (
    <div>
      <ul className="border-t border-border-default">
        <Row
          title="课程学习"
          configured={courseList.length > 0}
          pending={courses.isPending}
          failed={courses.isError}
          missing="还没有课程。课程学习按课组织资料、知识点、练习与错题，先声明一门课。"
          state={`已声明 ${courseList.length} 门课程：${courseList.map((course) => course.name).join('、')}`}
          to="/course/setup"
          search={{ returnTo: '/profile' }}
          action={courseList.length ? '管理课程' : '设置课程'}
        />
        <Row
          title="11408 考研学习"
          configured={examConfigured}
          pending={exam.isPending}
          failed={exam.isError}
          missing="还没有选择备考方向与科目。"
          state={`已确认 ${examSubjects} 个科目${
            exam.data?.target_exam_year ? ` · 目标 ${exam.data.target_exam_year} 年` : ''
          }`}
          to="/exam/setup"
          search={{ returnTo: '/profile' }}
          action={examConfigured ? '编辑备考设置' : '设置备考'}
        />
        <Row
          title="编程学习"
          configured={programmingState.languages.length > 0 || programmingState.completed}
          pending={programming.isPending}
          failed={programming.isError}
          missing="还没有声明编程语言。编程学习按语言组织练习、运行与提交。"
          state={`练习语言：${
            programmingState.languages.length ? programmingState.languages.join('、') : '未声明'
          }`}
          to="/programming/setup"
          search={{ returnTo: '/profile' }}
          action={programmingState.completed ? '编辑编程设置' : '设置编程学习'}
        />
      </ul>

      {courses.isError || exam.isError || programming.isError ? (
        <StatusNote tone="warning" className="mt-5">
          有学习空间的状态没有读到，因此这里没有显示它的当前设置；这不影响你进入对应页面。
        </StatusNote>
      ) : null}
    </div>
  );
}
