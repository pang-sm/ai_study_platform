import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '@/types/api';

const { GET } = vi.hoisted(() => ({ GET: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET } }));

import { apiClient } from '@/lib/api/client';

// BC8-R1 / ACCEL_PRODUCT_S10 — compile-level proof that the membership entitlement transport
// is concrete AND that it speaks in unified tiers.
//
// `GET /membership/entitlements` used to generate as `unknown`, so reading
// `features.learning_plan.allowed` needed a hand-written DTO or an assertion — both
// forbidden. It now resolves through the generated `paths` / `components` with no cast:
// the alias below IS the generated type, and the accessors read it directly.
//
// S10 changed what the entry CARRIES. It used to answer with a per-direction plan code
// (`monthly_sprint`), which named no tier the learner could act on and forced every consumer
// to invent a plan→tier translation. The verdict is now stated in the tier the backend
// actually gates on, so the lock and the membership page use one vocabulary.
//
// The index signature is deliberate. `features` is a mapping whose key set depends on the
// direction (exam_11408 and course_learning answer with two features, `programming`
// answers with none), so `features.learning_plan` is `… | undefined` under
// `noUncheckedIndexedAccess` and the optional chain is the honest read, not a workaround.

type EntitlementsResponse = paths['/membership/entitlements']['get']['responses'][200]['content']['application/json'];
type EntitlementsQuery = NonNullable<paths['/membership/entitlements']['get']['parameters']['query']>;
type FeatureEntitlement = components['schemas']['MembershipFeatureEntitlement'];

// The access F1C5 needs, with no assertion anywhere.
function learningPlanAllowed(entitlement: EntitlementsResponse): boolean | undefined {
  return entitlement.features.learning_plan?.allowed;
}

function learningPlanRequiredTier(entitlement: EntitlementsResponse): string | undefined {
  return entitlement.features.learning_plan?.required_tier;
}

// A workspace gate expressed purely from the generated contract.
function planAccess(entitlement: EntitlementsResponse):
  { state: 'unlocked' } | { state: 'locked'; requiredTier: string } {
  const feature = entitlement.features.learning_plan;
  if (!feature) return { state: 'locked', requiredTier: 'unknown' };
  if (feature.allowed) return { state: 'unlocked' };
  return { state: 'locked', requiredTier: feature.required_tier };
}

const free: EntitlementsResponse = {
  service_key: 'exam_11408',
  current_tier: 'free',
  policy_version: 'v1',
  features: {
    learning_plan: { allowed: false, required_tier: 'standard', required_capability: 'planning.generate' },
    learning_report: { allowed: true, required_tier: 'free', required_capability: null },
  },
};

const standard: EntitlementsResponse = {
  service_key: 'exam_11408',
  current_tier: 'standard',
  policy_version: 'v1',
  features: {
    learning_plan: { allowed: true, required_tier: 'standard', required_capability: 'planning.generate' },
    learning_report: { allowed: true, required_tier: 'free', required_capability: null },
  },
};

describe('BC8-R1 membership entitlement generated contract', () => {
  it('reads the learning_plan entitlement straight off the generated type', async () => {
    const query: EntitlementsQuery = { service_key: 'exam_11408' };
    GET.mockResolvedValue({
      data: free,
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });

    const { data } = await apiClient.GET('/membership/entitlements', { params: { query } });
    if (!data) throw new Error('unreachable');

    expect(learningPlanAllowed(data)).toBe(false);
    expect(learningPlanRequiredTier(data)).toBe('standard');
    expect(data.current_tier).toBe('free');
    expect(data.service_key).toBe('exam_11408');
    expect(planAccess(data)).toEqual({ state: 'locked', requiredTier: 'standard' });

    const report: FeatureEntitlement | undefined = data.features.learning_report;
    expect(report?.allowed).toBe(true);
    expect(report?.required_capability).toBeNull();
  });

  it('unlocks from the same contract when the tier is standard', () => {
    expect(planAccess(standard)).toEqual({ state: 'unlocked' });
    expect(learningPlanAllowed(standard)).toBe(true);
  });

  it('is a real type, not any or unknown', () => {
    // Each of these is a compile error only if the generated type is genuinely concrete.
    // If the response were still `unknown`/`any`, none of them would be errors and
    // `npm run typecheck` would silently pass with a broken contract.
    // @ts-expect-error `allowed` is a boolean, not a string
    const wrong: string = free.features.learning_plan?.allowed;
    void wrong;
    // @ts-expect-error the entry has exactly allowed / required_tier / required_capability
    void free.features.learning_plan?.nope;
    // @ts-expect-error a feature may be absent, so the optional chain is required
    const unguarded: string = free.features.learning_plan.required_tier;
    void unguarded;
    // @ts-expect-error the legacy plan-code field is gone, not merely deprecated
    void free.features.learning_plan.required_plan;
  });

  it('no longer exposes any legacy plan code', () => {
    // A string scan of the whole payload: S10's contract has no legacy plan vocabulary left
    // in it, so a re-introduced `monthly_sprint`-style field would fail here rather than
    // quietly reaching a rendered page.
    expect(JSON.stringify(free)).not.toMatch(/monthly|quarterly|full_exam|sprint|boost/);
  });

  it('keeps a missing feature expressible, because `programming` answers with none', () => {
    const empty: EntitlementsResponse = {
      service_key: 'programming',
      current_tier: 'free',
      policy_version: 'v1',
      features: {},
    };
    expect(learningPlanAllowed(empty)).toBeUndefined();
    expect(planAccess(empty)).toEqual({ state: 'locked', requiredTier: 'unknown' });
  });
});
