import type { PlanDefinition, ServiceEntitlements, SubscriptionSummary } from '../api/subscription';

// Tier labels. These are the tier IDENTIFIERS the backend stores (`free` / `standard` /
// `advanced`), rendered — not marketing names invented for a page. An unknown tier falls
// through to its own id so nothing is silently relabelled.
const TIER_LABELS: Record<string, string> = { free: 'Free', standard: 'Standard', advanced: 'Advanced' };

export function tierLabel(tier?: string | null): string {
  const value = (tier ?? '').trim();
  if (!value) return '—';
  return TIER_LABELS[value] ?? value;
}

export function tierInkClass(tier?: string | null): string {
  // The strength levels the design system already defines: Free is the resting state,
  // Standard the working one, Advanced the emphasised one. No new colours.
  if (tier === 'advanced') return 'membership-standing--emphasis';
  if (tier === 'standard') return 'membership-standing--strong';
  return 'membership-standing--resting';
}

// Capability ids are the product's own vocabulary (`tutor.chat`, `programming.debug`, ...).
// The gloss is a display label ONLY; the id is always shown beside it, so a reader can see
// exactly which capability a plan grants and no capability is hidden behind a paraphrase.
const CAPABILITY_GLOSSES: Record<string, string> = {
  'tutor.chat': '学习对话',
  'question.explain': '题目讲解',
  'material.qa': '资料问答',
  'question.generate': '生成练习',
  'programming.debug': '代码调试',
  'programming.explain': '代码讲解',
  'planning.generate': '生成学习计划',
  'knowledge.structure': '知识结构整理',
  'answer.grade': '主观题批改',
};

export function capabilityGloss(capability: string): string {
  return CAPABILITY_GLOSSES[capability] ?? capability;
}

export interface UsageMeter {
  period: 'daily' | 'weekly';
  label: string;
  /** null = this tier has no cap for the period. Never rendered as 0. */
  budget: number | null;
  remaining: number | null;
  used: number | null;
  percentUsed: number | null;
}

export function usageMeters(summary?: SubscriptionSummary): UsageMeter[] {
  const periods = summary?.periods ?? {};
  return (['daily', 'weekly'] as const).map((period) => {
    const entry = periods[period];
    const budget = entry?.budget ?? null;
    const remaining = entry?.remaining ?? null;
    // "used" is reserved + settled, the two columns the ledger actually holds — not
    // budget - remaining, which would fold in a reservation twice if the two ever diverged.
    const used = entry ? (entry.reserved ?? 0) + (entry.settled ?? 0) : null;
    return {
      period,
      label: period === 'daily' ? '今日额度' : '本周额度',
      budget,
      remaining,
      used,
      percentUsed: budget && used !== null ? Math.min(100, Math.round((used / budget) * 100)) : null,
    };
  });
}

export interface EntitlementRow {
  featureKey: string;
  label: string;
  allowed: boolean;
  /** The unified tier that first grants it. A TIER, not a legacy plan code. */
  requiredTier: string;
  /** The capability whose permission decides it; null for a base feature open to all tiers. */
  requiredCapability: string | null;
}

// Feature keys the product actually gates. A key with no gloss is shown as its own id.
const FEATURE_LABELS: Record<string, string> = { learning_plan: '学习计划' };

export function entitlementRows(entitlements?: ServiceEntitlements): EntitlementRow[] {
  const features = entitlements?.features ?? {};
  return Object.entries(features).map(([featureKey, feature]) => ({
    featureKey,
    label: FEATURE_LABELS[featureKey] ?? featureKey,
    allowed: feature.allowed === true,
    requiredTier: feature.required_tier,
    requiredCapability: feature.required_capability ?? null,
  }));
}

// The requirement stated the way the learner will act on it: the tier they need, in the same
// vocabulary as the plan table below it. `Standard` is a tier the backend really stores and
// really gates on — this is a read of the contract, not a translation invented for the page.
export function requirementLabel(row: EntitlementRow): string {
  return row.requiredCapability ? `${tierLabel(row.requiredTier)} 及以上` : '所有档位';
}

export interface PlanRow {
  tier: string;
  label: string;
  dailyBudget: number | null;
  weeklyBudget: number | null;
  capabilities: string[];
  isCurrent: boolean;
}

export function planRows(
  plans: Record<string, PlanDefinition> | undefined,
  currentTier?: string | null,
): PlanRow[] {
  // A fixed, factual order — the tiers are ranked, so the page lists them ranked rather
  // than in whatever order the payload happened to use.
  const order = ['free', 'standard', 'advanced'];
  const keys = Object.keys(plans ?? {});
  const sorted = [...order.filter((tier) => keys.includes(tier)), ...keys.filter((key) => !order.includes(key))];
  return sorted.map((tier) => {
    const definition = (plans ?? {})[tier];
    return {
      tier,
      label: definition?.label ?? tierLabel(tier),
      dailyBudget: definition?.daily_budget ?? null,
      weeklyBudget: definition?.weekly_budget ?? null,
      capabilities: definition?.capabilities ?? [],
      isCurrent: tier === (currentTier ?? 'free'),
    };
  });
}

// A cap of `null` is an UNCAPPED period (Advanced has no daily cap), which is a different
// statement from a cap of 0 — so it renders as a word, never as a number.
export function formatCap(value: number | null): string {
  return value === null || value === undefined ? '不限' : String(value);
}
