/**
 * The transport-level proof of the ONE upgrade path.
 *
 * The membership pages' own tests replace the mutations so they can drive result states
 * directly, which means they cannot see which endpoint the real mutation calls. This file
 * uses the REAL hooks against a mocked transport, so the endpoint and the request body are
 * asserted where they are actually decided.
 *
 * The rule being pinned: upgrading is an ORDER, and an order is not an activation. The order
 * endpoint writes a pending row; only a verified payment settles it. There is no redemption
 * path on this surface any more — the code mechanism was admin-issued, so for a learner the
 * input box was a control that could not complete anything.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const { GET, POST } = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, POST } }));

import {
  isOrderableTier, useCreateSubscriptionOrder, useExamEntitlements, usePaySubscriptionOrder,
} from './subscription';

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

function ok<T>(data: T) {
  return { data, error: undefined, response: { ok: true, status: 200 } as Response };
}

describe('membership upgrade transport', () => {
  it('creates the order through the unified order endpoint, and asks for no legacy service key', async () => {
    POST.mockResolvedValue(ok({
      activated: false,
      order: { order_no: 'U20260921AB12', status: 'pending', amount_cents: 2900, currency: 'CNY' },
    }));
    const { result } = renderHook(() => useCreateSubscriptionOrder(), { wrapper });
    result.current.mutate('standard');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(POST).toHaveBeenCalledWith('/subscription/orders', {
      body: { tier: 'standard', duration_days: null },
    });
    // Creating an order must not report an activation — the endpoint answers `activated: false`
    // and the hook hands that answer through rather than interpreting it.
    expect(result.current.data?.activated).toBe(false);
  });

  it('pays through the order’s own endpoint, which is the only thing that can activate a tier', async () => {
    POST.mockResolvedValue(ok({ order: { status: 'paid' }, idempotent: false, subscription: { tier: 'standard' } }));
    const { result } = renderHook(() => usePaySubscriptionOrder(), { wrapper });
    result.current.mutate(42);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(POST).toHaveBeenCalledWith('/subscription/orders/{order_id}/pay', {
      params: { path: { order_id: 42 } },
    });
    // No redemption endpoint is on this path any more.
    expect(POST).not.toHaveBeenCalledWith('/subscription/redeem', expect.anything());
    expect(POST).not.toHaveBeenCalledWith('/membership/redeem', expect.anything());
  });

  it('only treats a paid tier as orderable', () => {
    expect(isOrderableTier('standard')).toBe(true);
    expect(isOrderableTier('advanced')).toBe(true);
    // Free cannot be bought, so it is not a tier a checkout can be opened for.
    expect(isOrderableTier('free')).toBe(false);
    expect(isOrderableTier(null)).toBe(false);
  });

  it('reads the feature verdicts from the endpoint that resolves them from the tier', async () => {
    GET.mockResolvedValue(ok({
      service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1',
      features: { learning_plan: { allowed: false, required_tier: 'standard', required_capability: 'planning.generate' } },
    }));
    const { result } = renderHook(() => useExamEntitlements(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(GET).toHaveBeenCalledWith('/membership/entitlements', { params: { query: { service_key: 'exam_11408' } } });
    expect(result.current.data?.current_tier).toBe('free');
  });
});
