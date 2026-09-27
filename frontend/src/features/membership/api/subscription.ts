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

// The endpoints behind these hooks are typed `unknown` by the OpenAPI document (they return
// plain dicts), so the response is narrowed by the caller's own declared `T` rather than by the
// generated contract. The rejection rule is unchanged: a non-2xx, or a body the server did not
// send, is an error rather than an empty success.
async function request<T>(run: () => Promise<{ data?: unknown; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await run();
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data as T;
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

// ---------------------------------------------------------------------------- orders
//
// The learner-facing upgrade path is an ORDER, and an order is not an activation.
//
// `POST /subscription/orders` writes a PENDING row and changes nothing about the learner's
// tier — the response says so itself (`activated: false`). Activation happens only after a
// verified payment callback. That distinction is the whole reason this surface can exist
// honestly: it can show a real order, a real amount and a real status without ever printing
// "支付成功" for a payment that did not happen.
//
// Payment is not open: the only provider adapter is a mock, and production refuses it. So the
// confirmation page attempts the real pay call and reports whatever the server answers —
// including the 403 — rather than faking a success. There is no code path here that marks an
// order paid on the client.

export type PendingOrder = {
  order_no?: string;
  status?: string;
  amount_cents?: number;
  currency?: string;
  target_plan?: string;
  duration_days?: number;
  created_at?: string;
  order_expires_at?: string;
};

export type OrderResponse = { order: PendingOrder; activated: boolean };

/** The paid tiers a learner can order. Free is not purchasable, so it is not offered. */
export const ORDERABLE_TIERS = ['standard', 'advanced'] as const;
export type OrderableTier = (typeof ORDERABLE_TIERS)[number];

export function isOrderableTier(value: unknown): value is OrderableTier {
  return typeof value === 'string' && (ORDERABLE_TIERS as readonly string[]).includes(value);
}

export function useCreateSubscriptionOrder() {
  return useMutation({
    mutationFn: (tier: OrderableTier) =>
      request<OrderResponse>(() =>
        apiClient.POST('/subscription/orders', { body: { tier, duration_days: null } })),
  });
}

export function usePaySubscriptionOrder() {
  return useMutation({
    mutationFn: (orderId: number) =>
      request<{ order: PendingOrder; idempotent?: boolean; subscription?: { tier: string } }>(() =>
        apiClient.POST('/subscription/orders/{order_id}/pay', {
          params: { path: { order_id: orderId } },
        })),
  });
}
