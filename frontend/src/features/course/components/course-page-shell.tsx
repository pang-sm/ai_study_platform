import type { ReactNode } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ContextHeader, type ContextFact } from '@/components/page/context-header';
import { ContextNav, type ContextNavItem } from '@/components/page/context-nav';
import { useCourseCatalog, useCourseDashboard } from '@/features/course/api/course';
import { routePath } from '@/lib/router';
import { readCourseList } from '../course-context';

/**
 * The tabs of the course space, in the order a learner moves through it: asking about the
 * course, then what it contains, then being tested on it, then dealing with what went wrong,
 * then looking back at what happened.
 *
 * There is no 概览 tab. The course's overview was a page of prose describing what the tabs
 * already do, and a first tab whose content is an explanation of the other tabs is not a
 * surface — 课程问答 is what a learner opens a course to actually do, so it leads the strip.
 *
 * There is no 学习 tab either. Reading a knowledge point is not a PLACE in the course, it is
 * what opening one of its points does — so 知识结构 is the single entry to it and the workspace
 * at `/course/<id>/study` is reached from there, never from a tab of its own. 学习状态 is gone
 * from the strip for the same reason in reverse: the course's own figures are already stated by
 * 记录, and a tab that restates them is a second surface over one answer. Both routes still
 * exist, so a link that already points at them keeps working.
 */
export function courseNavItems(courseId: string): readonly ContextNavItem[] {
  const params = { courseId };
  return [
    { id: 'ask', label: '课程问答', to: '/course/$courseId/ask', params },
    { id: 'materials', label: '资料', to: '/course/$courseId/materials', params },
    { id: 'knowledge', label: '知识结构', to: '/course/$courseId/knowledge', params },
    { id: 'practice', label: '练习', to: '/course/$courseId/practice', params },
    { id: 'wrong', label: '错题与复习', to: '/course/$courseId/wrong', params },
    { id: 'plan', label: '计划', to: '/course/$courseId/plan', params },
    { id: 'records', label: '记录', to: '/course/$courseId/records', params },
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
 * This control IS how the page names the course it is in — there is no second title beside it,
 * because the same name twice on one line says nothing the selector does not already say. It is
 * therefore always rendered, including for a learner with a single course: the open course is
 * what the select shows.
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
function CourseSwitcher({
  courseId,
  active,
  name,
}: {
  courseId: string;
  active: string;
  /** The course's own name when the dashboard already reported it, for the not-in-list case. */
  name?: string;
}) {
  const catalog = useCourseCatalog();
  const navigate = useNavigate();
  const courses = readCourseList(catalog.data);
  const items = courseNavItems(courseId);
  const target = items.find((item) => item.id === active) ?? items[0];
  const inList = courses.some((course) => course.id === courseId);

  return (
    <select
      aria-label="切换课程"
      value={inList ? courseId : ''}
      // Nothing to switch to and an id that is not in the list yet — the identity is still worth
      // showing, it just cannot be changed from here.
      disabled={!inList && !courses.length}
      onChange={(event) => {
        const next = event.target.value;
        if (!next || !target) return;
        void navigate({ to: routePath(target.to), params: { courseId: next } });
      }}
      className="h-9 max-w-56 rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
    >
      {/* A course the list does not hold (an older link, a renamed id) still gets named here:
          the select is the page's only statement of which course is open. */}
      {inList ? null : <option value="">{name ?? courseId}</option>}
      {courses.map((course) => (
        <option key={course.id} value={course.id}>
          {course.name}
        </option>
      ))}
    </select>
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
  return (
    <div className="space-accent space-accent--course mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <ContextNav ariaLabel="专业学习导航" items={items} activeId={active} />
      <div className="mt-6 flex flex-wrap items-center gap-3 border-b border-border-default pb-4">
        <CourseSwitcher courseId={courseId} active={active} name={courseName} />
      </div>
      {facts?.length ? <ContextHeader facts={facts} className="mt-5" /> : null}
      <div className="pb-12 pt-8">{children}</div>
    </div>
  );
}
