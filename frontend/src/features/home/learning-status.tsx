import { Link } from '@tanstack/react-router';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { useSubscription, useSubscriptionPlans, useUsageSummary } from '@/features/profile/api/profile';

/**
 * The last thing on the page, and deliberately the smallest: the current tier and the AI 额度
 * actually left in the period that is running.
 *
 * Every figure is read from the server's own ledger, and an uncapped period prints as uncapped
 * instead of as a number — `null` there means "no cap", not "nothing left".
 */
/** `null` is the server saying the period has no cap; a missing figure is simply unknown. */
function remainingText(remaining: number | null | undefined): string | number {
  if (remaining === null) return '无上限';
  if (remaining === undefined) return '—';
  return remaining;
}

export function LearningStatus() {
  const subscription = useSubscription();
  const plans = useSubscriptionPlans();
  const usage = useUsageSummary();

  return (
    <section aria-labelledby="learning-status-title" className="border-t border-border-default pt-8">
      <SectionHeading
        id="learning-status-title"
        eyebrow="会员与用量"
        title="会员档位与可用额度"
        description="额度来自服务端账本；未使用的额度不代表学习进度。"
      />

      {subscription.isPending || usage.isPending ? (
        <StatusNote className="mt-6">正在读取会员与用量…</StatusNote>
      ) : subscription.isError || usage.isError ? (
        <StatusNote tone="warning" className="mt-6">
          会员与用量暂时无法读取，不影响继续学习。
        </StatusNote>
      ) : (
        <div className="mt-6 flex flex-wrap items-baseline gap-x-8 gap-y-3">
          <p className="text-body text-text-primary">
            当前档位：<span className="font-medium">{plans.data?.plans?.[subscription.data.tier]?.label ?? subscription.data.tier}</span>
          </p>
          <p className="text-body text-text-secondary">
            今日剩余额度：{remainingText(usage.data.periods.daily?.remaining)}
          </p>
          <Link to="/membership" className="text-body text-primary-ink hover:text-primary-hover">
            查看会员档位与用量
          </Link>
        </div>
      )}
    </section>
  );
}
