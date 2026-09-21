import { Link } from '@tanstack/react-router';
import { EmptyState } from '@/components/ui/empty-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { useRecentRecords, type LearningRecord } from '@/features/records/api/learning-records';
import { eventTypeLabel, serviceNamespaceLabel } from '@/features/records/event-labels';

function formatOccurredAt(value: string | null | undefined): string {
  if (!value) return '时间未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '时间未记录';
  return date.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' });
}

/** The real outcome a record carries, when it carries one. Nothing is inferred. */
function outcomeOf(record: LearningRecord): string | null {
  const summary = record.summary;
  if (!summary) return null;
  if (typeof summary.correct === 'boolean') return summary.correct ? '正确' : '错误';
  if (typeof summary.passed_count === 'number' && typeof summary.total_count === 'number') {
    return `通过 ${summary.passed_count} / ${summary.total_count}`;
  }
  if (typeof summary.status === 'string') return summary.status;
  return null;
}

export function RecentLearning() {
  const records = useRecentRecords(8);

  return (
    <section aria-labelledby="recent-learning-title" className="border-t border-border-default pt-8">
      <SectionHeading
        id="recent-learning-title"
        eyebrow="学习连续性"
        title="最近学习"
        action={
          <Link
            to="/reports"
            search={{ space: undefined, courseId: undefined, module: undefined, language: undefined }}
            className="text-body text-primary-ink hover:text-primary-hover"
          >
            查看全部学习记录
          </Link>
        }
      />

      {records.isPending ? (
        <div className="mt-6 space-y-3" aria-hidden="true">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-40" />
        </div>
      ) : records.isError ? (
        <StatusNote tone="danger" className="mt-6">
          最近学习记录暂时无法加载。
        </StatusNote>
      ) : records.data.length === 0 ? (
        <EmptyState
          className="mt-6"
          title="还没有学习记录。完成一次练习、复习或编程提交后，这里会显示真实发生过的事件。"
        />
      ) : (
        <ol className="mt-6 space-y-4">
          {records.data.map((record) => {
            const outcome = outcomeOf(record);
            return (
              <li key={record.event_id} className="border-l-2 border-border-default pl-4">
                <p className="text-body text-text-primary">{eventTypeLabel(record.event_type)}</p>
                <p className="mt-1 text-metadata text-text-secondary">
                  {serviceNamespaceLabel(record.service_namespace)} · {formatOccurredAt(record.occurred_at)}
                  {outcome ? ` · ${outcome}` : ''}
                </p>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
