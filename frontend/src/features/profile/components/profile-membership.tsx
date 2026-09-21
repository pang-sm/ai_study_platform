import { Link } from '@tanstack/react-router';
import { useSubscription, useSubscriptionPlans, useUsageSummary } from '../api/profile';

const PERIOD_LABELS: Record<string, string> = { daily: '今日', weekly: '本周' };

/**
 * A budget of `null` is the backend stating that the tier has no cap for that period — a real
 * absence, not a zero. It is printed as such rather than as `0`, which would read as "nothing
 * left".
 */
function BudgetValue({ value }: { value: number | null | undefined }) {
  if (value === null) return <span>无上限</span>;
  if (value === undefined) return <span className="text-text-muted">—</span>;
  return <span>{value}</span>;
}

export function SubscriptionSection() {
  const subscription = useSubscription();
  const plans = useSubscriptionPlans();

  if (subscription.isPending) {
    return <p className="text-body text-text-secondary">正在读取会员状态…</p>;
  }
  if (subscription.isError) {
    return (
      <p role="alert" className="text-body text-danger-ink">
        会员状态暂时无法加载。
      </p>
    );
  }

  const tier = subscription.data.tier;
  const plan = plans.data?.plans?.[tier];

  return (
    <div className="space-y-4">
      <p className="text-body text-text-primary">
        当前档位：
        <span className="ml-1 font-medium">{plan?.label ?? tier}</span>
      </p>
      {plan ? (
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-metadata text-text-muted">每日额度</dt>
            <dd className="text-body text-text-primary">
              <BudgetValue value={plan.daily_budget} />
            </dd>
          </div>
          <div>
            <dt className="text-metadata text-text-muted">每周额度</dt>
            <dd className="text-body text-text-primary">
              <BudgetValue value={plan.weekly_budget} />
            </dd>
          </div>
        </dl>
      ) : null}
      <Link to="/membership" className="inline-block text-body text-primary hover:text-primary-hover">
        查看会员与升级
      </Link>
    </div>
  );
}

export function UsageSection() {
  const usage = useUsageSummary();

  if (usage.isPending) {
    return <p className="text-body text-text-secondary">正在读取用量…</p>;
  }
  if (usage.isError) {
    return (
      <p role="alert" className="text-body text-danger-ink">
        用量暂时无法加载。
      </p>
    );
  }

  const periods = Object.entries(usage.data.periods);

  return (
    <div className="space-y-5">
      {periods.map(([period, value]) => (
        <div key={period}>
          <h3 className="text-body font-medium text-text-primary">
            {PERIOD_LABELS[period] ?? period}
          </h3>
          <dl className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <dt className="text-metadata text-text-muted">额度</dt>
              <dd className="text-body text-text-primary">
                <BudgetValue value={value.budget} />
              </dd>
            </div>
            <div>
              <dt className="text-metadata text-text-muted">已用</dt>
              <dd className="text-body text-text-primary">
                <BudgetValue value={value.settled} />
              </dd>
            </div>
            <div>
              <dt className="text-metadata text-text-muted">预留</dt>
              <dd className="text-body text-text-primary">
                <BudgetValue value={value.reserved} />
              </dd>
            </div>
            <div>
              <dt className="text-metadata text-text-muted">剩余</dt>
              <dd className="text-body text-text-primary">
                <BudgetValue value={value.remaining} />
              </dd>
            </div>
          </dl>
        </div>
      ))}
      <p className="text-metadata text-text-muted">
        用量来自服务端账本，随每次真实 AI 调用结算后更新。
      </p>
    </div>
  );
}
