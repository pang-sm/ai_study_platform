import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { StatusNote } from '@/components/ui/status-note';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { useReviewRecommendations, useSnoozeReviewRecommendation } from './recommendations-api';
import { cn } from '@/lib/utils';

type ReviewFilter = 'all' | 'course_learning' | 'exam_11408' | 'programming';
const filters: Array<[ReviewFilter, string]> = [
  ['all', '全部'],
  ['course_learning', '专业学习'],
  ['exam_11408', '11408'],
  ['programming', '编程'],
];

export function ReviewPage() {
  const [filter, setFilter] = useState<ReviewFilter>('all');
  const review = useReviewRecommendations(filter === 'all' ? undefined : filter);
  const snooze = useSnoozeReviewRecommendation();
  const items = review.data?.items ?? [];
  const total = review.data?.total ?? 0;

  return (
    <div className="mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
      <PageHeader title="统一复习" />
      <div className="mt-4 flex items-center gap-2" aria-live="polite">
        <Badge tone="brand">今日建议 {total} 项</Badge>
      </div>

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

      {snooze.isError ? (
        <StatusNote tone="danger" className="mt-4">暂缓未成功，建议仍在列表中。</StatusNote>
      ) : null}

      {review.isPending ? (
        <LoadingState label="正在读取复习建议…" className="mt-8" rows={3} />
      ) : review.isError ? (
        <StatusNote tone="danger" className="mt-8">复习建议暂时无法加载。</StatusNote>
      ) : items.length ? (
        <ol className="mt-8 space-y-4">
          {items.map((item) => (
            <li key={item.recommendation_key}>
              <Panel tone="plain" className="p-5 sm:p-6">
                <h2 className="text-card-title font-semibold text-text-primary">{item.title}</h2>
                <p className="mt-1 text-metadata text-text-secondary">{item.direction}</p>
                <p className="mt-4 text-body text-text-primary">{item.reason}</p>
                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <Link
                    to={item.action.deep_link as '/review'}
                    className="inline-flex min-h-11 items-center justify-center rounded-control bg-primary px-4 text-body font-medium text-white hover:bg-primary-hover"
                  >
                    开始复习
                  </Link>
                  <Button
                    variant="ghost"
                    disabled={snooze.isPending}
                    onClick={() => snooze.mutate(item.recommendation_key)}
                  >
                    暂缓
                  </Button>
                </div>
              </Panel>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState className="mt-8" title="暂无建议" />
      )}
    </div>
  );
}
