import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { StatusNote } from '@/components/ui/status-note';
import { FactList } from '@/components/page/fact-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { useReview, useReviewSummary } from '@/features/advanced/api/workflows';
import { toReviewItem } from '@/features/advanced/workflow-adapters';
import { useCompleteReview, useScheduleReviews } from '@/components/learning/p4-api';
import { namespaceLabel, reviewStatusLabel, sourceLabel } from '@/lib/fact-labels';
import { cn } from '@/lib/utils';

type ReviewFilter = 'all' | 'course_learning' | 'exam_11408' | 'programming';
const filters: Array<[ReviewFilter, string]> = [
  ['all', '全部'],
  ['course_learning', '专业学习'],
  ['exam_11408', '11408'],
  ['programming', '编程'],
];

/**
 * The review queue across every learning space.
 *
 * Each row states three things in the product's own words: which space the item belongs to, how
 * it is scheduled, and what the server's reason is for putting it in front of the learner today.
 * A namespace or source is rendered through its label, never as the code the backend keys on —
 * a learner should not have to read `wrong_answer` to know they are looking at a wrong answer.
 */
export function ReviewPage() {
  const [filter, setFilter] = useState<ReviewFilter>('all');
  const review = useReview(filter === 'all' ? undefined : filter);
  const summary = useReviewSummary();
  const schedule = useScheduleReviews();
  const complete = useCompleteReview();
  const items = (review.data?.items ?? []).map(toReviewItem);

  return (
    <div className="mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
      <PageHeader
        title="统一复习"
        description="三个方向的待复习与待处理项目都在这里；复习日期与弱项判断只看已经记录下来的学习情况。"
        meta={
          summary.data ? (
            <>
              <Badge tone="brand">待处理 {summary.data.total}</Badge>
              <span className="text-metadata text-text-secondary">
                {summary.data.has_stored_due_dates ? '这些复习项已经安排了日期' : '这些复习项还没有安排日期'}
              </span>
            </>
          ) : null
        }
      />

      <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label="复习范围">
        {filters.map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={filter === value}
            className={cn(
              'inline-flex min-h-11 items-center rounded-control border px-4 text-body',
              filter === value
                ? 'border-primary bg-primary-soft font-medium text-primary-ink'
                : 'border-border-default bg-surface text-text-secondary hover:text-text-primary',
            )}
            onClick={() => setFilter(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {review.isPending ? (
        <LoadingState label="正在读取统一复习…" className="mt-8" rows={4} />
      ) : review.isError || summary.isError ? (
        <StatusNote tone="danger" className="mt-8">
          统一复习暂时无法加载。
        </StatusNote>
      ) : items.length ? (
        <ol className="mt-8 space-y-6">
          {items.map((item) => (
            <li key={item.id}>
              <Panel tone="plain">
                <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
                  <Link
                    to={item.deep_link as '/review'}
                    className="text-card-title font-medium text-primary-ink underline hover:text-primary-hover"
                  >
                    {item.title}
                  </Link>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone="neutral">{namespaceLabel(item.service_namespace) ?? '学习'}</Badge>
                    {item.source_type ? (
                      <Badge tone="neutral">{sourceLabel(item.source_type) ?? '学习项'}</Badge>
                    ) : null}
                    <Badge tone="brand">{item.dueLabel}</Badge>
                    <Badge tone={item.due_at ? 'success' : 'warning'}>
                      {item.review_status ? reviewStatusLabel(item.review_status) ?? '状态未知' : '状态未知'}
                    </Badge>
                  </div>
                </div>

                <FactList
                  className="mt-4"
                  columns={2}
                  value={{
                    due_at: item.due_at,
                    due_source: item.due_source,
                  }}
                />

                <details className="mt-4">
                  <summary className="text-body text-text-secondary">为什么今天复习</summary>
                  <p className="mt-2 text-body text-text-primary">{item.reason}</p>
                  <FactList
                    className="mt-3"
                    value={item.metrics}
                    allow={['wrong_count', 'attempts', 'factual_correct', 'factual_incorrect', 'active_wrong_count', 'last_attempt_at']}
                  />
                </details>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  {!item.due_at ? (
                    <Button
                      variant="secondary"
                      disabled={schedule.isPending}
                      onClick={() => schedule.mutate({ item_ids: [item.id], include_all: false })}
                    >
                      安排复习
                    </Button>
                  ) : null}
                  <span className="text-body text-text-secondary">按真实复习结果记录：</span>
                  <Button
                    variant="secondary"
                    disabled={complete.isPending}
                    onClick={() => complete.mutate({ itemId: item.id, result: 'correct' })}
                  >
                    完成：正确
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={complete.isPending}
                    onClick={() => complete.mutate({ itemId: item.id, result: 'incorrect' })}
                  >
                    完成：错误
                  </Button>
                </div>
              </Panel>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState
          className="mt-8"
          title="暂无待处理复习"
          description="这个范围里现在没有要复习的内容。换个范围看看，或者先去完成一次练习。"
        />
      )}

      {schedule.isSuccess ? (
        <StatusNote tone="success" className="mt-6">
          已安排复习；日期与间隔来自复习策略。
        </StatusNote>
      ) : null}
      {complete.isSuccess ? (
        <StatusNote tone="success" className="mt-6">
          结果已记录；复习、学习状态与记录正在刷新。
        </StatusNote>
      ) : null}
    </div>
  );
}
