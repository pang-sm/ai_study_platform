import { useEffect, useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Check, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Container } from '@/components/ui/container';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import {
  entitlementRows, formatCap, formatPeriod, formatPrice, planRows, requirementLabel,
  capabilityGloss, tierInkClass, tierLabel, usageMeters,
} from '../view-models/membership';
import {
  isOrderableTier,
  membershipEntitlementKey,
  subscriptionKey,
  usageSummaryKey,
  useExamEntitlements, useSubscriptionPlans, useSubscriptionState, useUsageSummary,
} from '../api/subscription';
import { useQueryClient } from '@tanstack/react-query';
import './membership-page.css';

// ─────────────────────────────────────────────────────────────────────────────
// VISUAL CONCEPT — 会员 · 学习账户
//
// Primary user task: 弄清我现在是哪一档、这一档包含什么、升到下一档要多少钱。
// Visual concept: 一张价目表压在一份账单上 —— 上面是三个档位横向对照（价格、额度、能力逐项对齐），
// 下面是这位学习者自己的账。不是营销页：没有推荐标签、没有"最受欢迎"、没有倒计时。
// Focal element: 当前档位，以及它右侧的下一档。
// Composition: 三列共用同一套横线，逐行对齐；当前档位用一条边线标出，而不是变成一张浮起来的卡片。
//
// 兑换码已经从这里移除。它曾是这个页面唯一的开通方式，而它有一个只能由管理员生成、由管理员交付的
// 码 —— 对一个学习者来说那不是一条路径，是一个看起来能输东西的框。开通路径现在只有一条：下单。
// ─────────────────────────────────────────────────────────────────────────────

function Standing({ tier, loading, failed }: { tier?: string; loading: boolean; failed: boolean }) {
  if (loading) return <Skeleton className="h-16 w-64" />;
  if (failed) return <p className="membership-standing membership-standing--unknown">暂时无法读取会员状态</p>;
  return (
    <h1 className={`membership-standing ${tierInkClass(tier)}`} data-tier={tier ?? 'free'}>
      {tierLabel(tier)}
    </h1>
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

/**
 * Whether the three tiers should be stacked instead of tabulated.
 *
 * Chosen in JS rather than by a CSS media query so that only ONE of the two structures is in the
 * document. Both in the DOM means two landmarks with the same accessible name, every price
 * rendered twice, and a screen reader reading the whole table twice on a phone — `display:none`
 * hides it from sight, but the duplicate landmark is a real smell, and the unit environment
 * applies no CSS at all so a CSS-only switch is untestable.
 *
 * The default when `matchMedia` is absent (a test environment, or any host without it) is the
 * WIDE layout: with no viewport to consult, the neutral assumption is the one that shows the
 * comparison in full.
 */
const NARROW_QUERY = '(max-width: 47.99rem)';

function useStackedLayout(): boolean {
  const read = () => (typeof window === 'undefined' ? false : Boolean(window.matchMedia?.(NARROW_QUERY).matches));
  const [stacked, setStacked] = useState(read);

  useEffect(() => {
    const query = typeof window === 'undefined' ? undefined : window.matchMedia?.(NARROW_QUERY);
    if (!query) return;
    const onChange = () => setStacked(query.matches);
    onChange();
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  return stacked;
}

/** The one action a tier offers: it is the current one, it is orderable, or it is free. */
function TierAction({ row }: { row: ReturnType<typeof planRows>[number] }) {
  if (row.isCurrent) return <span className="membership-note">当前档位</span>;
  if (isOrderableTier(row.tier)) {
    return (
      <Button asChild>
        <Link to="/membership/payment" search={{ tier: row.tier }}>
          选择 {row.label}
        </Link>
      </Button>
    );
  }
  return <span className="membership-note">无需付费</span>;
}

function CapabilityList({ capabilities }: { capabilities: readonly string[] }) {
  return (
    <ul className="membership-compare__capabilities">
      {capabilities.map((capability) => (
        <li key={capability}>
          <Check className="size-3.5 shrink-0 text-success-ink" aria-hidden="true" />
          {capabilityGloss(capability)}
        </li>
      ))}
    </ul>
  );
}

/**
 * The three tiers, stacked, for widths where three columns do not fit.
 *
 * A comparison table is read ACROSS, which is exactly what a 390px screen cannot do: the three
 * columns needed 44rem, so the third tier sat off-screen behind a horizontal scroll nobody was
 * told about and the second tier's own header was cut mid-word. Stacking keeps the COMPARISON by
 * keeping the field ORDER identical in every block — 价格 / 每日额度 / 每周额度 / 包含的智能能力 /
 * 行动 — so a reader compares down the page instead of across it.
 *
 * It is not a card wall: the blocks are separated by the same rules the table uses, with no
 * border, radius or shadow around them.
 */
function PlanStack({ rows }: { rows: ReturnType<typeof planRows> }) {
  return (
    <div className="membership-stack">
      <p className="membership-compare__caption">
        每个档位按 {formatPeriod(rows.find((row) => row.durationDays)?.durationDays ?? null) || '30 天'} 计费；
        额度以平台 Credits 计，用完当周期不会续。Free 无需付费，也不能下单。
      </p>
      {rows.map((row) => (
        <section key={row.tier} className="membership-stack__tier" aria-labelledby={`plan-${row.tier}`}>
          <h3 id={`plan-${row.tier}`} className="membership-stack__name">
            {row.label}
            {row.isCurrent ? <span className="membership-compare__current">当前</span> : null}
          </h3>
          <dl className="membership-stack__fields">
            <div>
              <dt>价格</dt>
              <dd className="membership-compare__price">
                <strong>{formatPrice(row.priceCents)}</strong>
                {row.durationDays ? <small> / {formatPeriod(row.durationDays)}</small> : null}
              </dd>
            </div>
            <div><dt>每日额度</dt><dd>{formatCap(row.dailyBudget)}</dd></div>
            <div><dt>每周额度</dt><dd>{formatCap(row.weeklyBudget)}</dd></div>
            <div>
              <dt>包含的智能能力</dt>
              <dd><CapabilityList capabilities={row.capabilities} /></dd>
            </div>
          </dl>
          <div className="membership-stack__action"><TierAction row={row} /></div>
        </section>
      ))}
    </div>
  );
}

/**
 * The three tiers side by side: what each costs, what each allows, what each opens.
 *
 * The columns share one grid so the rows line up and a reader can compare across them — the
 * whole point of a price table, and the thing a stack of independent cards destroys. Prices come
 * from the same constant the order is priced from, so the number here is the number charged.
 */
function PlanComparison({ currentTier }: { currentTier?: string }) {
  const plans = useSubscriptionPlans();
  const stacked = useStackedLayout();
  if (plans.isPending) {
    return (
      <div className="membership-compare__loading">
        <Skeleton className="h-12 w-full" /><Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (plans.isError || !plans.data) {
    return <p className="membership-note">暂时无法读取档位信息，稍后重试。</p>;
  }

  const rows = planRows(plans.data.plans, currentTier);

  return (
    <div className="membership-compare" role="region" aria-label="档位价格与权益对照" tabIndex={0}>
      {stacked ? <PlanStack rows={rows} /> : (
      <div className="membership-compare__wide">
      <table>
        <caption className="membership-compare__caption">
          每个档位按 {formatPeriod(rows.find((row) => row.durationDays)?.durationDays ?? null) || '30 天'} 计费；
          额度以平台 Credits 计，用完当周期不会续。Free 无需付费，也不能下单。
        </caption>
        <thead>
          <tr>
            <th scope="col">档位</th>
            {rows.map((row) => (
              <th key={row.tier} scope="col" className={row.isCurrent ? 'is-current' : undefined}>
                {row.label}
                {row.isCurrent ? <span className="membership-compare__current">当前</span> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">价格</th>
            {rows.map((row) => (
              <td key={row.tier} className="membership-compare__price">
                <strong>{formatPrice(row.priceCents)}</strong>
                {row.durationDays ? <small> / {formatPeriod(row.durationDays)}</small> : null}
              </td>
            ))}
          </tr>
          <tr>
            <th scope="row">每日额度</th>
            {rows.map((row) => <td key={row.tier}>{formatCap(row.dailyBudget)}</td>)}
          </tr>
          <tr>
            <th scope="row">每周额度</th>
            {rows.map((row) => <td key={row.tier}>{formatCap(row.weeklyBudget)}</td>)}
          </tr>
          <tr>
            <th scope="row">包含的智能能力</th>
            {rows.map((row) => (
              <td key={row.tier}><CapabilityList capabilities={row.capabilities} /></td>
            ))}
          </tr>
          <tr>
            <th scope="row">&nbsp;</th>
            {rows.map((row) => (
              <td key={row.tier}><TierAction row={row} /></td>
            ))}
          </tr>
        </tbody>
      </table>
      </div>
      )}
    </div>
  );
}

function Entitlements({ rows, loading, failed }: { rows: ReturnType<typeof entitlementRows>; loading: boolean; failed: boolean }) {
  if (loading) return <Skeleton className="h-24 w-full" />;
  if (failed) return <p className="membership-note">暂时无法读取权益状态。</p>;
  if (!rows.length) return <p className="membership-note">当前方向没有需要开通的受限功能。</p>;
  return (
    <ul className="membership-entitlements">
      {rows.map((row) => (
        <li key={row.featureKey}>
          <span className="membership-entitlements__name">{row.label}</span>
          <span className={`membership-entitlements__state ${row.allowed ? 'is-open' : 'is-locked'}`}>
            {row.allowed ? '已开通' : '未开通'}
          </span>
          <small>
            {row.allowed
              ? '当前档位已包含'
              : `需要 ${requirementLabel(row)}${
                  row.requiredCapability ? ` · ${capabilityGloss(row.requiredCapability)}` : ''
                }`}
          </small>
        </li>
      ))}
    </ul>
  );
}

export function MembershipPage() {
  const subscription = useSubscriptionState();
  const usage = useUsageSummary();
  const entitlements = useExamEntitlements();
  const queryClient = useQueryClient();

  // ONE standing, read from ONE authority. The entitlement endpoint is asked the same
  // question because it is the gate the Study Plan actually reads — if it ever disagreed
  // with the tier shown here, the page would be describing a lock that is not the real one.
  const currentTier = subscription.data?.tier ?? entitlements.data?.current_tier;
  const tierDisagrees = Boolean(
    subscription.data && entitlements.data && subscription.data.tier !== entitlements.data.current_tier,
  );
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: subscriptionKey });
    void queryClient.invalidateQueries({ queryKey: usageSummaryKey });
    void queryClient.invalidateQueries({ queryKey: membershipEntitlementKey('exam_11408') });
  };

  return (
    <div className="membership">
      <Container className="membership__inner">
        <header className="membership__header">
          <p>会员</p>
          <Standing tier={currentTier} loading={subscription.isPending} failed={subscription.isError && entitlements.isError} />
          {entitlements.data?.policy_version ? (
            <dl className="membership__facts">
              <div><dt>政策版本</dt><dd>{entitlements.data.policy_version}</dd></div>
            </dl>
          ) : null}
          {tierDisagrees ? (
            <p className="membership-rail__error" role="alert">
              会员档位与权益判定不一致，请刷新后重试。
            </p>
          ) : null}
          <p className="membership-note">
            一个账号一个档位。所有学习方向的功能开通都由当前档位决定。
          </p>
        </header>

        <section aria-labelledby="membership-compare-title">
          <h2 id="membership-compare-title">档位对照</h2>
          <PlanComparison currentTier={currentTier} />
        </section>

        <section aria-labelledby="membership-entitlements-title">
          <h2 id="membership-entitlements-title">当前权益</h2>
          <Entitlements rows={entitlementRows(entitlements.data)} loading={entitlements.isPending} failed={entitlements.isError} />
        </section>

        <section aria-labelledby="membership-usage-title">
          <h2 id="membership-usage-title">本期额度</h2>
          {usage.isError
            ? <p className="membership-note">暂时无法读取额度。</p>
            : <UsageLedger summary={usage.data} loading={usage.isPending} />}
        </section>

        <StatusNote className="membership__footnote">
          <Sparkles className="mr-2 inline size-4" aria-hidden="true" />
          额度会在每个周期开始时重置；未用完的部分不会累积到下一个周期。
          <button type="button" className="ml-3 underline" onClick={refresh}>
            刷新
          </button>
        </StatusNote>
      </Container>
    </div>
  );
}
