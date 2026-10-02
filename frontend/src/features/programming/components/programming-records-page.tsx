import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { FactList } from '@/components/page/fact-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { eventTypeLabel } from '@/features/records/event-labels';
import { formatDateTime } from '@/lib/format';
import type { ProgrammingLanguageSlug } from '../programming-language';
import { ProgrammingShell } from './programming-shell';
import { useProgrammingRecords, useProgrammingRecordsSummary, useProgrammingState } from '../api/programming';

const secondaryAction =
  'inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

function rows(value: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(value)) return value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null);
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    return rows(record.items ?? record.data ?? record.exercises ?? record.tasks ?? []);
  }
  return [];
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

/**
 * 成长记录 — what actually happened, and what has been recorded about it.
 *
 * Three reads that were three tabs, in one place: the counts, the recorded state, and the events
 * themselves. They answer one question — how have I been doing — and splitting them forced a
 * learner to open three pages to read one answer. The counts and the state are summaries of the
 * same events, so they sit above the events rather than beside them.
 *
 * 错误与待处理 was folded in here. It read no endpoint and held only an explanation of the three
 * help layers, which is a paragraph about the product and not a record of anything; what it was
 * reaching for — reviewing a run's real failure — happens where the failure happened, in the
 * workbench's own output panel. The explanation is kept, at the foot, because it is still the
 * honest thing to say when a learner asks where errors are dealt with.
 *
 * The facts here are the whole space's, not one language's: the records endpoint is not scoped by
 * language and does not pretend to be. The language in the strip above is the context the other
 * three tools are read in, and switching it does not filter these figures.
 */
export function ProgrammingRecordsPage({ language }: { language: ProgrammingLanguageSlug | undefined }) {
  const records = useProgrammingRecords();
  const summary = useProgrammingRecordsSummary();
  const state = useProgrammingState();
  const events = rows(records.data);

  return (
    <ProgrammingShell language={language} active="records">
      <PageHeader
        eyebrow="成长记录"
        title="成长记录"
        description="运行、测试、提交与 Debug Agent 都记为真实事件；下面是已记下的统计与学习状态。"
        actions={
          <Link
            to="/reports"
            search={{ space: 'programming', courseId: undefined, module: undefined, language }}
            className={secondaryAction}
          >
            查看学习报告
          </Link>
        }
      />

      <section className="mt-8" aria-labelledby="programming-records-summary-title">
        <SectionHeading
          id="programming-records-summary-title"
          title="记录统计"
          as="h2"
          description="缺失的指标显示为「—」。"
        />
        {summary.isPending ? <LoadingState label="正在读取记录统计…" className="mt-4" rows={2} /> : null}
        {summary.isError ? (
          <StatusNote tone="danger" className="mt-4">
            记录统计暂时无法加载。
          </StatusNote>
        ) : null}
        {summary.data !== undefined ? <FactList className="mt-4" value={summary.data} /> : null}
      </section>

      <section className="mt-10" aria-labelledby="programming-records-state-title">
        <SectionHeading
          id="programming-records-state-title"
          title="学习状态"
          as="h2"
          description="只呈现已经记录的事实与计数；不含熟练度或能力评分。"
        />
        {state.isPending ? <LoadingState label="正在读取状态…" className="mt-4" rows={2} /> : null}
        {state.isError ? (
          <StatusNote tone="danger" className="mt-4">
            学习状态暂时无法加载。
          </StatusNote>
        ) : null}
        {state.data !== undefined ? <FactList className="mt-4" value={state.data} /> : null}
      </section>

      <section className="mt-10" aria-labelledby="programming-records-detail-title">
        <SectionHeading id="programming-records-detail-title" title="记录明细" as="h2" />
        {records.isPending ? (
          <LoadingState label="正在读取记录…" className="mt-4" />
        ) : records.isError ? (
          <StatusNote tone="danger" className="mt-4">
            记录暂时无法加载。
          </StatusNote>
        ) : events.length ? (
          <ol className="mt-4 space-y-4">
            {events.map((event, index) => (
              <li key={String(event.event_id ?? index)} className="border-l-2 border-border-default pl-4">
                <p className="text-body text-text-primary">
                  {eventTypeLabel(text(event.event_type) ?? '')}
                </p>
                <p className="mt-1 text-metadata text-text-secondary">
                  {formatDateTime(text(event.occurred_at))}
                </p>
                <FactList
                  className="mt-2"
                  columns={2}
                  value={event.summary}
                  allow={['correct', 'score', 'passed_count', 'total_count', 'exit_code', 'timed_out']}
                />
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState
            className="mt-4"
            title="还没有编程学习记录。"
            description="运行、测试或提交一次练习后，这里会出现真实事件。"
            action={
              <Button asChild variant="secondary">
                <Link to="/programming/practice" search={language ? { language } : {}}>
                  进入练习中心
                </Link>
              </Button>
            }
          />
        )}
      </section>

      <section className="mt-10 border-t border-border-default pt-6" aria-labelledby="programming-help-title">
        <SectionHeading
          id="programming-help-title"
          title="错误与求助"
          as="h2"
          description="出问题时，三个辅助层的差别：编译器、单次 AI 调用、多步工作流。"
        />
        <ul className="mt-4 space-y-3">
          <li className="text-body text-text-secondary">
            <span className="text-text-primary">代码诊断</span>：由编译器等确定性工具完成，不调用模型、不消耗额度；失败的 stderr 与测试结果就在 Workbench 的执行反馈里。
          </li>
          <li className="text-body text-text-secondary">
            <span className="text-text-primary">AI Debug</span>：一次真实 AI 调用，会消耗额度，回答下方可以评价这次分析是否有帮助。
          </li>
          <li className="text-body text-text-secondary">
            <span className="text-text-primary">Debug Agent</span>：有边界的多步工作流，每步单独结算；结果只作用于编辑器缓冲区。
          </li>
        </ul>
      </section>
    </ProgrammingShell>
  );
}
