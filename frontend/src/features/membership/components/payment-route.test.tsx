/**
 * Route-level proof that the checkout is REACHABLE.
 *
 * The previous round's membership test asserted the upgrade link's `href` and stopped there. It
 * passed while `/membership/payment` rendered nothing at all: `routes/membership.tsx` rendered
 * the membership page directly instead of an `<Outlet />`, so the child route existed in the
 * generated tree, matched the URL, and was never mounted. The learner clicked 选择 Advanced and
 * the page did not change.
 *
 * So this file drives the real router: it CLICKS the upgrade, and then asserts what is on screen
 * and where the address bar went. An `href` assertion cannot see a missing Outlet; only a
 * navigation can.
 */
import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { GET } = vi.hoisted(() => ({ GET: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

/** The learner is on Standard, so the upgrade path is the one that has a link. */
const TIER = 'standard';

beforeEach(() => {
  GET.mockReset();
  GET.mockImplementation(async (path: string) => {
    if (path === '/subscription') return ok({ tier: TIER, policy_version: 'v1' });
    if (path === '/subscription/plans') {
      return ok({
        policy_version: 'v1',
        plans: {
          free: { label: 'Free', daily_budget: 100, weekly_budget: 500, capabilities: [], price_cents: null, duration_days: null },
          standard: { label: 'Standard', daily_budget: 1000, weekly_budget: 5000, capabilities: ['tutor.chat'], price_cents: 2900, duration_days: 30 },
          advanced: { label: 'Advanced', daily_budget: null, weekly_budget: 20000, capabilities: ['tutor.chat'], price_cents: 14900, duration_days: 30 },
        },
      });
    }
    if (path === '/usage/summary') {
      return ok({ tier: TIER, periods: { daily: { budget: 1000, reserved: 0, settled: 1, remaining: 999 }, weekly: { budget: 5000, reserved: 0, settled: 1, remaining: 4999 } } });
    }
    return ok({ service_key: 'exam_11408', current_tier: TIER, policy_version: 'v1', features: {} });
  });
});

describe('membership → payment route', () => {
  it('renders the membership page itself at /membership', async () => {
    renderApp('/membership');
    expect(await screen.findByRole('region', { name: '档位价格与权益对照' })).toBeInTheDocument();
  });

  it('mounts the checkout when the learner clicks the upgrade, and says where it went', async () => {
    const { router } = renderApp('/membership');
    await screen.findByRole('region', { name: '档位价格与权益对照' });

    // Only a non-current, orderable tier has a 选择 link — the current tier says 当前档位.
    await userEvent.click(screen.getByRole('link', { name: '选择 Advanced' }));

    // The page actually changed: the checkout's own heading is on screen.
    expect(await screen.findByRole('heading', { name: /订单确认|Advanced/ })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: '创建订单' })).toBeInTheDocument();

    expect(router.state.location.pathname).toBe('/membership/payment');
    expect(router.state.location.search).toMatchObject({ tier: 'advanced' });
  });

  it('opens the checkout for an explicitly named tier, from a cold URL', async () => {
    // A refresh (or a shared link) must render the checkout, not bounce to the membership page.
    const { router } = renderApp('/membership/payment?tier=standard');
    expect(await screen.findByRole('button', { name: '创建订单' })).toBeInTheDocument();
    expect(router.state.location.search).toMatchObject({ tier: 'standard' });
  });

  it('shows the tier, its price and its period on the order summary', async () => {
    renderApp('/membership/payment?tier=advanced');
    // `创建订单` exists before the plan catalogue resolves, so the price is read with a waiting
    // query: asserting synchronously here would read the not-yet-loaded state and pass or fail
    // on timing rather than on what the page shows.
    const summary = (await screen.findByRole('button', { name: '创建订单' })).closest('section') as HTMLElement;
    expect(await within(summary).findByText('¥149.00')).toBeInTheDocument();
    expect(await within(summary).findByText('30 天')).toBeInTheDocument();
  });

  it('never claims a payment succeeded while no provider is connected', async () => {
    renderApp('/membership/payment?tier=advanced');
    await screen.findByRole('button', { name: '创建订单' });
    // Nothing has been ordered, so nothing can claim to have been paid.
    expect(screen.queryByText(/支付成功|已开通|开通成功/)).not.toBeInTheDocument();
  });
});
