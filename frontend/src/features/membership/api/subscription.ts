import { useMutation, useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

export type SubscriptionSummary = components['schemas']['UsageSummaryResponse'];
export type SubscriptionPlans = components['schemas']['PlanCatalogResponse'];
export type PlanDefinition = components['schemas']['PlanDefinition'];
export type SubscriptionState = components['schemas']['SubscriptionStateResponse'];
export type ServiceEntitlements = components['schemas']['MembershipEntitlementsResponse'];
// The per-direction redemption contract: `POST /membership/redeem[/preview]`. These are the
// endpoints that write `user_service_memberships`, which is what the feature gates read.
export type RedemptionPreview = components['schemas']['RedemptionPreviewResponse'];
export type RedemptionResult = components['schemas']['RedemptionResultResponse'];

export const subscriptionKey = ['membership', 'subscription'] as const;
export const subscriptionPlansKey = ['membership', 'plans'] as const;
export const usageSummaryKey = ['membership', 'usage'] as const;
export const membershipEntitlementKey = (serviceKey: string) => ['membership', 'entitlements', serviceKey] as const;

async function request<T>(run: () => Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await run();
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useSubscriptionState() {
  return useQuery({
    queryKey: subscriptionKey,
    queryFn: () => request<SubscriptionState>(() => apiClient.GET('/subscription')),
    retry: false,
  });
}

export function useSubscriptionPlans() {
  return useQuery({
    queryKey: subscriptionPlansKey,
    queryFn: () => request<SubscriptionPlans>(() => apiClient.GET('/subscription/plans')),
    retry: false,
  });
}

export function useUsageSummary() {
  return useQuery({
    queryKey: usageSummaryKey,
    queryFn: () => request<SubscriptionSummary>(() => apiClient.GET('/usage/summary')),
    retry: false,
  });
}

// The SAME entitlement endpoint the Study Plan locked state reads. Rendering the membership
// page from it is what makes the page a real explanation of the gate: the learner sees the
// exact feature verdict that blocks them, not a paraphrase of it.
export function useExamEntitlements(serviceKey = 'exam_11408') {
  return useQuery({
    queryKey: membershipEntitlementKey(serviceKey),
    queryFn: () => request<ServiceEntitlements>(() => apiClient.GET('/membership/entitlements', { params: { query: { service_key: serviceKey } } })),
    retry: false,
  });
}

// ---------------------------------------------------------------------------- activation
//
// TWO MEMBERSHIP SYSTEMS EXIST AT ONCE, AND THEY DO NOT MOVE TOGETHER (SSOT §41: CURRENT is
// still the three-service membership; the unified tier is the frozen TARGET). Measured, not
// assumed — `backend/tests/test_s9_membership_and_status.py` pins both halves:
//
//   POST /membership/redeem       writes `user_service_memberships`. The per-direction
//                                 `learning_plan` / `learning_report` gates READ that row,
//                                 so this is the path that OPENS a locked feature.
//   POST /subscription/redeem     activates the unified `subscriptions` tier. It is a real,
//                                 atomic path — and it opens no product feature today.
//
// The surface therefore offers the path that RESOLVES THE LOCK. Offering the unified one
// would change a number on the page and leave the feature locked behind it, which is a fake
// success flow.
//
// `service_key` is sent so the code is validated against the direction it is being redeemed
// for: the backend refuses a code that belongs to another direction rather than quietly
// applying it here.
//
// Online payment is a third path and is NOT offered: `POST /subscription/orders` creates a
// PENDING order whose only payment method is a mock that production refuses (403), so an
// order created here could never be settled.

const MEMBERSHIP_SERVICE_KEY = 'exam_11408';

export function usePreviewRedemption() {
  return useMutation({
    mutationFn: (code: string) => request<RedemptionPreview>(
      () => apiClient.POST('/membership/redeem/preview', {
        body: { code, service_key: MEMBERSHIP_SERVICE_KEY },
      })),
  });
}

export function useRedeem() {
  return useMutation({
    mutationFn: (code: string) => request<RedemptionResult>(
      () => apiClient.POST('/membership/redeem', {
        body: { code, service_key: MEMBERSHIP_SERVICE_KEY },
      })),
  });
}
