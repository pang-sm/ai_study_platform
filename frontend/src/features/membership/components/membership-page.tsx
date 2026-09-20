import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Ticket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Container } from '@/components/ui/container';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiRequestError } from '@/features/exam/api/content-status';
import {
  membershipEntitlementKey, subscriptionKey, usageSummaryKey,
  useExamEntitlements, usePreviewRedemption, useRedeem,
  useSubscriptionPlans, useSubscriptionState, useUsageSummary,
} from '../api/subscription';
import {
  capabilityGloss, entitlementRows, formatCap, planRows, tierInkClass, tierLabel,
  usageMeters,
} from '../view-models/membership';
import './membership-page.css';

// ─────────────────────────────────────────────────────────────────────────────
// VISUAL CONCEPT — 会员 · 学习账户
//
// Primary user task: 确认我现在是哪一档会员、还剩多少额度、以及被锁住的功能需要哪一档。
// This is NOT a pricing page and NOT a SaaS plan grid. It is a LEDGER: the learner's own
// standing, in real numbers the backend stores, with the tiers listed beneath it as rows of
// factual limits.
//
// Focal element: the current tier, as the largest type on the page, with the policy version
// and the entitlement verdict beside it. Composition is asymmetric — a wide editorial column
// for standing + usage, a narrow rail for the ONE activation path that really completes.
//
// No card grid: a tier is a ROW (ranked, tabular numbers, capability list), and the usage
// meters are a ledger strip, because three identical rounded rectangles would describe a
// marketing page rather than this learner's account.
// ─────────────────────────────────────────────────────────────────────────────

function errorDetail(error: unknown): string | undefined {
  if (!(error instanceof ApiRequestError)) return undefined;
  const detail = error.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'detail' in detail) {
    const inner = (detail as { detail?: unknown }).detail;
    if (typeof inner === 'string') return inner;
  }
  return undefined;
}

function Standing({ tier, loading, failed }: { tier?: string; loading: boolean; failed: boolean }) {
  if (loading) return <Skeleton className="h-16 w-64" />;
  if (failed) return <p className="membership-standing membership-standing--unknown">暂时无法读取会员状态</p>;
  return (
    <p className={`membership-standing ${tierInkClass(tier)}`} data-tier={tier ?? 'free'}>
      {tierLabel(tier)}
    </p>
  );
}

function UsageLedger({ summary, loading }: { summary?: ReturnType<typeof useUsageSummary>['data']; loading: boolean }) {
  if (loading) return <div className="membership-usage__loading"><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></div>;
  const meters = usageMeters(summary);
  return (
    <ul className="membership-usage">
      {meters.map((meter) => (
        <li key={meter.period}>
          <div className="membership-usage__figures">
            <span>{meter.label}</span>
            <strong>
              {meter.budget === null
                // An uncapped period says so in words. Rendering 0, or a full bar, would
                // claim a measurement the tier does not have.
                ? '不限'
                : <>{meter.remaining ?? 0} <small>/ {meter.budget}</small></>}
            </strong>
          </div>
          {meter.percentUsed === null
            ? <p className="membership-usage__note">该档位此周期不设额度上限</p>
            : (
              <div className="membership-usage__track" aria-hidden="true">
                <span style={{ width: `${meter.percentUsed}%` }} />
              </div>
            )}
          {meter.percentUsed !== null
            ? <p className="membership-usage__note">已用 {meter.used}（预留 + 已结算）· 剩余 {meter.remaining}</p>
            : null}
        </li>
      ))}
    </ul>
  );
}

function Entitlements({ rows, loading, failed }: { rows: ReturnType<typeof entitlementRows>; loading: boolean; failed: boolean }) {
  if (loading) return <Skeleton className="h-24 w-full" />;
  if (failed) return <p className="membership-note">暂时无法读取权益状态</p>;
  if (!rows.length) return <p className="membership-note">当前方向没有需要开通的受限功能。</p>;
  return (
    <ul className="membership-entitlements">
      {rows.map((row) => (
        <li key={row.featureKey}>
          <span className="membership-entitlements__name">{row.label}</span>
          <span className={`membership-entitlements__state ${row.allowed ? 'is-open' : 'is-locked'}`}>
            {row.allowed ? '已开通' : '未开通'}
          </span>
          {/* `required_plan` is a LEGACY service-plan code (`monthly_sprint`), not a unified
              tier — translating it into `Standard` / `Advanced` here would invent a mapping
              the backend does not make. So the requirement is stated in words and the tier
              table below carries the comparison. The feature key is still shown when the
              feature IS open, so the learner can see which capability they hold. */}
          <small>{row.allowed ? row.featureKey : '需要开通对应的备考方案'}</small>
        </li>
      ))}
    </ul>
  );
}

function RedemptionRail({ onActivated }: { onActivated: () => void }) {
  const [code, setCode] = useState('');
  const [previewed, setPreviewed] = useState<string>();
  const preview = usePreviewRedemption();
  const redeem = useRedeem();

  const submitPreview = () => {
    const value = code.trim();
    if (!value) return;
    setPreviewed(undefined);
    preview.mutate(value, { onSuccess: () => setPreviewed(value) });
  };

  const confirm = () => {
    if (!previewed) return;
    redeem.mutate(previewed, {
      onSuccess: () => { setPreviewed(undefined); setCode(''); onActivated(); },
    });
  };

  const error = errorDetail(preview.error) ?? errorDetail(redeem.error);

  return (
    <section className="membership-rail" aria-labelledby="membership-redeem-title">
      <h2 id="membership-redeem-title"><Ticket aria-hidden="true" className="size-4" />兑换码激活</h2>
      <p>持有 CS408 备考方案兑换码，可在此直接开通对应方向的学习权益。</p>
      <label htmlFor="redeem-code">兑换码</label>
      <div className="membership-rail__row">
        <input
          id="redeem-code" name="redeem-code" type="text" autoComplete="off"
          value={code} onChange={(event) => { setCode(event.target.value); setPreviewed(undefined); }}
          placeholder="输入兑换码"
        />
        <Button variant="secondary" disabled={preview.isPending || !code.trim()} onClick={submitPreview}>
          {preview.isPending ? '查询中' : '查询'}
        </Button>
      </div>
      {preview.data ? (
        <div className="membership-rail__preview" role="status">
          {/* The plan's own NAME and duration come from the code, so the learner confirms
              what the code actually grants rather than a paraphrase of it. */}
          <p>可开通 <strong>{preview.data.preview.target_plan_name}</strong> · {preview.data.preview.membership_duration_days} 天</p>
          <p className="membership-note">
            {preview.data.preview.service_key} · 到期 {preview.data.preview.projected_expires_at.slice(0, 10)}
          </p>
          <Button disabled={redeem.isPending} onClick={confirm}>{redeem.isPending ? '正在激活' : '确认激活'}</Button>
        </div>
      ) : null}
      {redeem.data ? <p className="membership-rail__ok" role="status">{redeem.data.message}，权益已更新。</p> : null}
      {error ? <p className="membership-rail__error" role="alert">{error}</p> : null}

      <h2 className="membership-rail__payment-title">在线支付</h2>
      {/* Bounded and honest. The order endpoint exists but its only payment method is a
          MOCK that production refuses, so an order created here could never be settled.
          Saying that plainly is the honest surface; a checkout that always fails is not. */}
      <p>在线支付尚未开通。当前可通过兑换码开通备考方案。</p>
      <Button variant="secondary" disabled aria-describedby="membership-payment-reason">暂不可用</Button>
      <p id="membership-payment-reason" className="membership-note">线上支付通道仍在接入中，暂不提供下单。</p>
    </section>
  );
}

function PlanLedger({ currentTier }: { currentTier?: string }) {
  const plans = useSubscriptionPlans();
  if (plans.isPending) return <div className="membership-plans__loading"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>;
  if (plans.isError || !plans.data) return <p className="membership-note">暂时无法读取档位信息</p>;
  const rows = planRows(plans.data.plans, currentTier);
  return (
    <div className="membership-plans__scroll">
      <table className="membership-plans">
        <caption>各档位额度以平台 Credits 计（1 Credit ≈ ¥0.01 平台成本）。</caption>
        <thead>
          <tr><th scope="col">档位</th><th scope="col">每日额度</th><th scope="col">每周额度</th><th scope="col">可用的智能能力</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.tier} className={row.isCurrent ? 'is-current' : undefined}>
              <th scope="row">
                {row.label}
                {row.isCurrent ? <span className="membership-plans__current">当前</span> : null}
              </th>
              <td>{formatCap(row.dailyBudget)}</td>
              <td>{formatCap(row.weeklyBudget)}</td>
              <td>
                <ul className="membership-plans__capabilities">
                  {row.capabilities.map((capability) => (
                    <li key={capability}>
                      {/* The capability ID is always shown: the gloss is a label, and the
                          id is what the product actually gates on. */}
                      <span>{capabilityGloss(capability)}</span><code>{capability}</code>
                    </li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MembershipPage() {
  const subscription = useSubscriptionState();
  const usage = useUsageSummary();
  const entitlements = useExamEntitlements();
  const queryClient = useQueryClient();

  const currentTier = subscription.data?.tier ?? entitlements.data?.current_plan;
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: subscriptionKey });
    void queryClient.invalidateQueries({ queryKey: usageSummaryKey });
    void queryClient.invalidateQueries({ queryKey: membershipEntitlementKey('exam_11408') });
  };

  return (
    <div className="membership">
      <Container className="membership__inner">
        <header className="membership__header">
          <p>会员 / STUDY ACCOUNT</p>
          <Standing tier={currentTier} loading={subscription.isPending} failed={subscription.isError && entitlements.isError} />
          <dl className="membership__facts">
            <div>
              <dt>统一会员档位</dt>
              <dd>{subscription.isPending ? '读取中' : tierLabel(subscription.data?.tier)}</dd>
            </div>
            <div>
              <dt>当前备考方案</dt>
              <dd>{entitlements.isPending ? '读取中' : (entitlements.data?.current_plan ?? '—')}</dd>
            </div>
            {subscription.data?.policy_version ? <div><dt>政策版本</dt><dd>{subscription.data.policy_version}</dd></div> : null}
          </dl>
          {/* Two systems are in force at once (SSOT §41: CURRENT is still the per-direction
              membership; the unified tier is the TARGET). The page states both rather than
              picking one, because they genuinely differ and a learner holding a paid plan
              must not be shown a "Free" tier with no explanation. */}
          <p className="membership-note">
            统一会员档位与各学习方向的备考方案当前分别生效；学习计划等功能的开通以「当前备考方案」为准。
          </p>
        </header>

        <div className="membership__grid">
          <div className="membership__main">
            <section aria-labelledby="membership-entitlements-title">
              <h2 id="membership-entitlements-title">当前权益</h2>
              <Entitlements rows={entitlementRows(entitlements.data)} loading={entitlements.isPending} failed={entitlements.isError} />
            </section>

            <section aria-labelledby="membership-usage-title">
              <h2 id="membership-usage-title">本期额度</h2>
              {usage.isError
                ? <p className="membership-note">暂时无法读取额度</p>
                : <UsageLedger summary={usage.data} loading={usage.isPending} />}
            </section>

            <section aria-labelledby="membership-plans-title">
              <h2 id="membership-plans-title">档位对照</h2>
              <PlanLedger currentTier={currentTier} />
            </section>
          </div>

          <RedemptionRail onActivated={refresh} />
        </div>
      </Container>
    </div>
  );
}
