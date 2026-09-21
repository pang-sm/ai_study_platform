import type { ReactNode } from 'react';
import { Link, useNavigate, useRouterState } from '@tanstack/react-router';
import { Breadcrumb } from '@/components/page/breadcrumb';
import { ContextHeader, type ContextFact } from '@/components/page/context-header';
import { ContextNav, type ContextNavItem } from '@/components/page/context-nav';
import { useCourseCatalog, useCourseDashboard } from '@/features/course/api/course';
import { AdaptivePractice } from '@/components/learning/adaptive-practice';
import { displayMetric } from '@/features/learning-intelligence/presentation';
import { routePath } from '@/lib/router';
import { readCourseList } from '../course-context';

/**
 * The tabs of the course space, in the order a learner moves through it: what the course
 * contains, then learning it, then being tested on it, then dealing with what went wrong, then
 * looking back at what happened. The AI question surface sits last because it is a tool used
 * while doing those things, not a step in the sequence.
 */
export function courseNavItems(courseId: string): readonly ContextNavItem[] {
  const params = { courseId };
  return [
    { id: 'overview', label: '概览', to: '/course/$courseId', params },
    { id: 'materials', label: '资料', to: '/course/$courseId/materials', params },
    { id: 'knowledge', label: '知识结构', to: '/course/$courseId/knowledge', params },
    { id: 'study', label: '学习', to: '/course/$courseId/study', params },
    { id: 'practice', label: '练习', to: '/course/$courseId/practice', params },
    { id: 'wrong', label: '错题与复习', to: '/course/$courseId/wrong', params },
    { id: 'plan', label: '计划', to: '/course/$courseId/plan', params },
    { id: 'records', label: '记录', to: '/course/$courseId/records', params },
    { id: 'state', label: '学习状态', to: '/course/$courseId/state', params },
    { id: 'ask', label: '课程问答', to: '/course/$courseId/ask', params },
  ];
}

/** The dashboard names the course; every course page must be able to say which course it is. */
export function courseNameFrom(value: unknown): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined;
  const row = value as Record<string, unknown>;
  for (const key of ['course_name', 'name', 'display_name', 'course']) {
    const candidate = row[key];
    if (typeof candidate === 'string' && candidate.trim()) return candidate;
    if (typeof candidate === 'object' && candidate !== null) {
      const nested = (candidate as Record<string, unknown>).display_name ?? (candidate as Record<string, unknown>).name;
      if (typeof nested === 'string' && nested.trim()) return nested;
    }
  }
  return undefined;
}

/**
 * Moving between the courses a learner actually has, from inside one of them.
 *
 * The stored context is a *set* of courses with one of them being read at a time, so "the current
 * course" is a property of what is open right now — there is no separate current-course pointer
 * in the API, and this control does not invent one. Switching therefore navigates the same tab
 * onto the other course rather than writing a preference: the learner lands on `/course/<other>`
 * with the section they were reading still selected.
 *
 * A native `<select>` is used rather than a custom menu: it is operable by keyboard and screen
 * reader on every device without this component implementing any of that.
 */
function CourseSwitcher({ courseId, active }: { courseId: string; active: string }) {
  const catalog = useCourseCatalog();
  const navigate = useNavigate();
  const currentHref = useRouterState({ select: (state) => state.location.href });
  const courses = readCourseList(catalog.data);
  const items = courseNavItems(courseId);
  const target = items.find((item) => item.id === active) ?? items[0];
  const inList = courses.some((course) => course.id === courseId);

  return (
    <div className="flex flex-wrap items-end gap-3">
      {courses.length > 1 || (courses.length === 1 && !inList) ? (
        <div>
          <label htmlFor="course-switcher" className="block text-metadata text-text-secondary">
            切换课程
          </label>
          <select
            id="course-switcher"
            value={inList ? courseId : ''}
            onChange={(event) => {
              const next = event.target.value;
              if (!next || !target) return;
              void navigate({ to: routePath(target.to), params: { courseId: next } });
            }}
            className="mt-1 h-11 max-w-56 rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            {inList ? null : <option value="">当前课程不在课程列表中</option>}
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.name}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <Link
        to="/course/setup"
        search={{ returnTo: currentHref }}
        className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-4 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        管理课程
      </Link>
    </div>
  );
}

export function CoursePageShell({
  courseId,
  active,
  facts,
  children,
}: {
  courseId: string;
  active: string;
  /** Facts that belong to this page — the course itself is added here, never by the caller. */
  facts?: readonly ContextFact[];
  children: ReactNode;
}) {
  const dashboard = useCourseDashboard(courseId);
  const courseName = courseNameFrom(dashboard.data);
  const items = courseNavItems(courseId);
  const activeLabel = items.find((item) => item.id === active)?.label;

  const courseFacts: ContextFact[] = [
    { label: '当前课程', value: courseName ?? (dashboard.isPending ? '正在读取课程…' : displayMetric(undefined)) },
    ...(facts ?? []),
  ];

  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <Breadcrumb
        items={[
          { label: '课程学习', to: '/course' },
          { label: courseName ?? '本课程', to: active === 'overview' ? undefined : '/course/$courseId', params: { courseId } },
          ...(activeLabel ? [{ label: activeLabel }] : []),
        ]}
      />
      <ContextNav ariaLabel="课程学习导航" items={items} activeId={active} className="mt-4" />
      <ContextHeader
        facts={courseFacts}
        actions={<CourseSwitcher courseId={courseId} active={active} />}
        className="mt-6"
      />
      {active === 'practice' ? (
        <AdaptivePractice
          serviceKey="course_learning"
          courseId={courseId}
          entryHref={`/course/${encodeURIComponent(courseId)}/practice`}
        />
      ) : null}
      <div className="pb-12 pt-8">{children}</div>
    </div>
  );
}
