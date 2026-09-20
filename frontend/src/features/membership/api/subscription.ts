import { useMutation, useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

export type SubscriptionSummary = components['schemas']['UsageSummaryResponse'];
export type SubscriptionPlans = components['schemas']['PlanCatalogResponse'];
export type PlanDefinition = components['schemas']['PlanDefinition'];
export type SubscriptionState = components['schemas']['SubscriptionStateResponse'];
export type ServiceEntitlements = components['schemas']['MembershipEntitlementsResponse'];
export type RedeemPreview = components['schemas']['RedeemPreviewResponse'];
export type RedeemResult = components['schemas']['RedeemResultResponse'];

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
//
// ACCEL_PRODUCT_S10: this endpoint resolves from the UNIFIED subscription tier. There is one
// membership, so there is nothing here to reconcile against a second one.
export function useExamEntitlements(serviceKey = 'exam_11408') {
  return useQuery({
    queryKey: membershipEntitlementKey(serviceKey),
    queryFn: () => request<ServiceEntitlements>(() => apiClient.GET('/membership/entitlements', { params: { query: { service_key: serviceKey } } })),
    retry: false,
  });
}

// ---------------------------------------------------------------------------- activation
//
// ONE REDEEM FLOW. `POST /subscription/redeem` consumes a real code and activates the
// unified subscription; every capability gate resolves from that tier, so a success here
// leaves the features it grants open by the time the response is written. There is no
// second membership to move, and therefore no "tier changed but feature still locked" state
// for the UI to explain away.
//
// `POST /membership/redeem` still exists for old clients and performs the same activation,
// but this surface does not use it — offering two activation buttons is what made the
// membership page read as two parallel memberships.
//
// Online payment is still NOT offered: `POST /subscription/orders` creates a PENDING order
// whose only payment method is a mock that production refuses (403), so an order created
// here could never be settled.

export function usePreviewRedemption() {
  return useMutation({
    mutationFn: (code: string) => request<RedeemPreview>(
      () => apiClient.POST('/subscription/redeem/preview', { body: { code } })),
  });
}

export function useRedeem() {
  return useMutation({
    mutationFn: (code: string) => request<RedeemResult>(
      () => apiClient.POST('/subscription/redeem', { body: { code } })),
  });
}
