import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '@/types/api';

const { GET } = vi.hoisted(() => ({ GET: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET } }));

import { apiClient } from '@/lib/api/client';

// BC8-R1 — compile-level proof that the membership entitlement transport is concrete.
//
// `GET /membership/entitlements` used to generate as `unknown`, so reading
// `features.learning_plan.allowed` needed a hand-written DTO or an assertion — both
// forbidden. It now resolves through the generated `paths` / `components` with no cast:
// the alias below IS the generated type, and the accessors read it directly.
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

function learningPlanRequiredPlan(entitlement: EntitlementsResponse): string | undefined {
  return entitlement.features.learning_plan?.required_plan;
}

// A workspace gate expressed purely from the generated contract.
function planAccess(entitlement: EntitlementsResponse):
  { state: 'unlocked' } | { state: 'locked'; requiredPlan: string } {
  const feature = entitlement.features.learning_plan;
  if (!feature) return { state: 'locked', requiredPlan: 'unknown' };
  if (feature.allowed) return { state: 'unlocked' };
  return { state: 'locked', requiredPlan: feature.required_plan };
}

const free: EntitlementsResponse = {
  service_key: 'exam_11408',
  current_plan: 'free',
  features: {
    learning_plan: { allowed: false, required_plan: 'monthly_sprint' },
    learning_report: { allowed: true, required_plan: 'free' },
  },
};

const paid: EntitlementsResponse = {
  service_key: 'exam_11408',
  current_plan: 'monthly_sprint',
  features: {
    learning_plan: { allowed: true, required_plan: 'monthly_sprint' },
    learning_report: { allowed: true, required_plan: 'free' },
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
    expect(learningPlanRequiredPlan(data)).toBe('monthly_sprint');
    expect(data.current_plan).toBe('free');
    expect(data.service_key).toBe('exam_11408');
    expect(planAccess(data)).toEqual({ state: 'locked', requiredPlan: 'monthly_sprint' });

    const report: FeatureEntitlement | undefined = data.features.learning_report;
    expect(report?.allowed).toBe(true);
  });

  it('unlocks from the same contract when the plan is paid', () => {
    expect(planAccess(paid)).toEqual({ state: 'unlocked' });
    expect(learningPlanAllowed(paid)).toBe(true);
  });

  it('is a real type, not any or unknown', () => {
    // Each of these is a compile error only if the generated type is genuinely concrete.
    // If the response were still `unknown`/`any`, none of them would be errors and
    // `npm run typecheck` would silently pass with a broken contract.
    // @ts-expect-error `allowed` is a boolean, not a string
    const wrong: string = free.features.learning_plan?.allowed;
    void wrong;
    // @ts-expect-error the entry has exactly `allowed` and `required_plan`
    void free.features.learning_plan?.nope;
    // @ts-expect-error a feature may be absent, so the optional chain is required
    const unguarded: string = free.features.learning_plan.required_plan;
    void unguarded;
  });

  it('keeps a missing feature expressible, because `programming` answers with none', () => {
    const empty: EntitlementsResponse = {
      service_key: 'programming',
      current_plan: 'free',
      features: {},
    };
    expect(learningPlanAllowed(empty)).toBeUndefined();
    expect(planAccess(empty)).toEqual({ state: 'locked', requiredPlan: 'unknown' });
  });
});
