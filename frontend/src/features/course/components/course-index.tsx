import { Link } from '@tanstack/react-router';
import { EmptyState } from '@/components/ui/empty-state';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { StatusNote } from '@/components/ui/status-note';
import { toCourseIdentity, useCourseCatalog } from '@/features/course/api/course';

function values(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'object' && value !== null) {
    const row = value as Record<string, unknown>;
    for (const key of ['courses', 'items', 'data']) {
      if (Array.isArray(row[key])) return row[key] as unknown[];
    }
  }
  return [];
}

/**
 * The courses this learner is studying.
 *
 * The set is the courses they declared, so an empty list is not an error and not a loading
 * state: it is a statement that no course has been declared yet, with the one real place to
 * change that — the setup flow, which writes the declarations this list reads.
 */
export function CourseIndex() {
  const catalog = useCourseCatalog();
  const courses = values(catalog.data);

  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="课程学习"
        title="我的课程"
        description="课程学习空间按课程组织：资料、知识点、练习、错题与计划都挂在具体一门课程下。"
        actions={
          <Link
            to="/course/setup"
            search={{ returnTo: '/course' }}
            className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-4 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            {courses.length ? '管理课程' : '设置课程'}
          </Link>
        }
      />

      {catalog.isPending ? (
        <LoadingState label="正在读取课程…" className="mt-8" />
      ) : catalog.isError ? (
        <StatusNote tone="danger" className="mt-8">
          课程列表暂时无法加载。
        </StatusNote>
      ) : courses.length ? (
        <ul className="mt-8 border-t border-border-default">
          {courses.map((course, index) => {
            const identity = toCourseIdentity(course);
            const label = identity.name ?? identity.id;
            return (
              <li key={identity.id ?? index} className="border-b border-border-default">
                {identity.id ? (
                  <Link
                    to="/course/$courseId"
                    params={{ courseId: identity.id }}
                    className="block py-5 text-body font-medium text-text-primary hover:bg-primary-soft"
                  >
                    {label ?? '未命名课程'}
                  </Link>
                ) : (
                  <p className="py-5 text-body text-text-secondary">
                    后端返回了没有标识的课程，无法安全进入。
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState
          className="mt-8"
          title="还没有已声明的课程。"
          description="课程由你在课程设置里声明：填写课程名称并保存后，它们会出现在这里，课程空间里也才有内容可以做。"
          action={
            <Link
              to="/course/setup"
              search={{ returnTo: '/course' }}
              className="inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover"
            >
              设置课程
            </Link>
          }
        />
      )}
    </div>
  );
}
