/**
 * ACCEL_PRODUCT_S10 PART B5 / C — the transport-level proof that there is ONE redeem flow.
 *
 * The membership page's own tests replace the mutations so they can drive result states
 * directly, which means they cannot see which endpoint the real mutation calls. This file
 * uses the REAL hooks against a mocked transport, so the endpoint and the request body are
 * asserted where they are actually decided.
 *
 * The rule being pinned: activation posts to the unified subscription endpoint and NOT to the
 * legacy per-direction one. Two activation endpoints on one surface is what made the
 * membership page read as two parallel memberships.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

const { GET, POST } = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, POST } }));

import { useExamEntitlements, usePreviewRedemption, useRedeem } from './subscription';

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

describe('membership activation transport', () => {
  it('previews a code through the unified preview endpoint, with no service_key', async () => {
    POST.mockResolvedValue(ok({
      tier: 'standard', tier_label: 'Standard', duration_days: 30, current_tier: 'free',
      projected_expires_at: '2026-10-20T00:00:00+00:00', code_expires_at: null,
    }));
    const { result } = renderHook(() => usePreviewRedemption(), { wrapper });
    result.current.mutate('ZX-2026-CS408');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(POST).toHaveBeenCalledWith('/subscription/redeem/preview', { body: { code: 'ZX-2026-CS408' } });
    // The legacy body carried `service_key` to pick a direction. A unified tier has no
    // direction, so the field is gone rather than defaulted.
    expect(POST.mock.calls[0]?.[1]).not.toHaveProperty('body.service_key');
  });

  it('activates through the ONE unified redeem endpoint', async () => {
    POST.mockResolvedValue(ok({
      tier: 'standard', tier_label: 'Standard', status: 'active', end_at: null,
      duration_days: 30, current_tier: 'standard',
    }));
    const { result } = renderHook(() => useRedeem(), { wrapper });
    result.current.mutate('ZX-2026-CS408');
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(POST).toHaveBeenCalledWith('/subscription/redeem', { body: { code: 'ZX-2026-CS408' } });
    expect(POST).not.toHaveBeenCalledWith('/membership/redeem', expect.anything());
    expect(POST).not.toHaveBeenCalledWith('/subscription/orders', expect.anything());
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
