import { Link } from '@tanstack/react-router';
import { Panel } from '@/components/ui/panel';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { StatusNote } from '@/components/ui/status-note';
import { useCourseDashboard, useCourseKnowledge, useCourseMaterials, useCoursePracticeHistory, useCourseTodayPlan } from '@/features/course/api/course';
import { CoursePageShell, courseNameFrom } from './course-page-shell';

/**
 * The five steps of the course loop, in the order they actually happen.
 *
 * These were separate pages reached from a tab bar, which made the course read as a set of tools.
 * They are one sequence — read the material, learn the knowledge point, practise it, deal with
 * what went wrong, then look at the plan and the record — so the home page states that sequence
 * with the real counts behind each step.
 */
const CHAIN = [
  { id: 'materials', label: '资料', purpose: '课程内容与可引用材料', href: 'materials', countNoun: '项资料' },
  { id: 'knowledge', label: '学习', purpose: '知识点与脉络', href: 'knowledge', countNoun: '个知识点' },
  { id: 'practice', label: '练习', purpose: '按知识点做题并记录结果', href: 'practice', countNoun: '条练习记录' },
  { id: 'wrong', label: '错题与复习', purpose: '订正做错的题并安排复习', href: 'wrong' },
  { id: 'plan', label: '计划', purpose: '今天要做的事', href: 'plan', countNoun: '项今日任务' },
  { id: 'records', label: '记录', purpose: '发生过的事件与学习报告', href: 'records' },
] as const;

function records(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (typeof value === 'object' && value !== null) {
    const row = value as Record<string, unknown>;
    const candidate = row.items ?? row.data ?? row.records;
    return Array.isArray(candidate) ? candidate : [];
  }
  return [];
}

function text(value: unknown, keys: readonly string[]): string | undefined {
  if (typeof value !== 'object' || value === null) return undefined;
  const row = value as Record<string, unknown>;
  for (const key of keys) {
    if (typeof row[key] === 'string' && (row[key] as string).trim()) return row[key] as string;
  }
  return undefined;
}

export function CourseWorkspace({ courseId }: { courseId: string }) {
  const dashboard = useCourseDashboard(courseId);
  const materials = useCourseMaterials(courseId);
  const knowledge = useCourseKnowledge(courseId);
  const history = useCoursePracticeHistory(courseId);
  const todayPlan = useCourseTodayPlan(courseId);
  const name = courseNameFrom(dashboard.data) ?? text(dashboard.data, ['course']) ?? courseId;

  const counts: Record<string, number | undefined> = {
    materials: materials.isSuccess ? records(materials.data).length : undefined,
    knowledge: knowledge.isSuccess ? records(knowledge.data).length : undefined,
    practice: history.isSuccess ? records(history.data).length : undefined,
    plan: todayPlan.isSuccess ? records(todayPlan.data).length : undefined,
  };
  const nextAction = text(dashboard.data, ['next_action', 'next_step', 'suggested_action']);

  return (
    <CoursePageShell courseId={courseId} active="overview">
      <PageHeader
        eyebrow="课程学习"
        title="课程概览"
        description={`${name}：资料、知识点、练习、错题与计划构成一门课程的完整学习闭环。`}
      />

      {dashboard.isError ? (
        <StatusNote tone="danger" className="mt-6">
          课程概览暂时无法加载；下面的每一步仍可以单独打开。
        </StatusNote>
      ) : null}

      {dashboard.isPending ? <LoadingState label="正在读取课程概览…" className="mt-8" rows={2} /> : null}

      {nextAction ? (
        <Panel tone="focus" labelledBy="course-next-title" className="mt-8">
          <p className="text-metadata font-medium tracking-eyebrow text-primary-ink">下一步</p>
          <h2 id="course-next-title" className="mt-2 text-section-title font-semibold text-text-primary">
            {nextAction}
          </h2>
          <p className="mt-3 text-body text-text-secondary">这是后端根据当前课程记录给出的下一步。</p>
          <Link
            to="/course/$courseId/practice"
            params={{ courseId }}
            className="mt-5 inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover"
          >
            开始本节课练习
          </Link>
        </Panel>
      ) : null}

      <section className="mt-10" aria-labelledby="course-chain-title">
        <p className="text-metadata font-medium tracking-eyebrow text-text-muted">学习闭环</p>
        <h2 id="course-chain-title" className="mt-1 text-section-title font-semibold text-text-primary">
          这门课程是怎么学的
        </h2>
        <ol className="mt-6 border-t border-border-default">
          {CHAIN.map((step, index) => {
            const count = counts[step.id];
            return (
              <li key={step.id} className="border-b border-border-default">
                <Link
                  to={`/course/$courseId/${step.href}` as '/course/$courseId'}
                  params={{ courseId }}
                  className="group flex flex-wrap items-center gap-x-6 gap-y-2 py-4 hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                >
                  <span className="w-6 text-metadata tabular-nums text-text-muted">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-body font-medium text-text-primary">{step.label}</span>
                    <span className="mt-0.5 block text-metadata text-text-secondary">{step.purpose}</span>
                  </span>
                  <span className="text-metadata tabular-nums text-text-secondary">
                    {count === undefined
                      ? 'countNoun' in step && step.countNoun
                        ? '正在读取…'
                        : ''
                      : `${count} ${'countNoun' in step ? step.countNoun : ''}`.trim()}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      </section>
    </CoursePageShell>
  );
}
