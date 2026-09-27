/**
 * The membership surface: one standing, a real price table, and nothing that pretends.
 *
 * The rules this file enforces:
 *
 *  * ONE membership. The tier shown is the same tier `/membership/entitlements` resolved the
 *    feature verdict from, so the page cannot describe a lock that is not the real one.
 *  * The prices on the page are the prices in the payload. Nothing here hardcodes ¥29 / ¥149 —
 *    if the payload changed, these assertions would follow it, which is the point of reading the
 *    price from the server rather than repeating it.
 *  * No redemption. The code mechanism was admin-issued; for a learner the input box was a
 *    control that could not complete anything, so it is gone from the surface entirely.
 *  * No capability id reaches the DOM.
 */
import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { GET } = vi.hoisted(() => ({ GET: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

/** The tier the whole page is rendered under. Both authorities read this one value. */
let tier = 'free';
/** A capability id this BUILD has no Chinese name for, added on demand. */
let unknownCapability: string | null = null;
function capabilities(base: string[]): string[] {
  return unknownCapability ? [...base, unknownCapability] : base;
}

function respond() {
  GET.mockImplementation(async (path: string) => {
    if (path === '/subscription') return ok({ tier, policy_version: 'v1' });
    if (path === '/subscription/plans') {
      return ok({
        policy_version: 'v1',
        plans: {
          free: { label: 'Free', daily_budget: 100, weekly_budget: 500, capabilities: capabilities(['tutor.chat']), price_cents: null, duration_days: null },
          standard: { label: 'Standard', daily_budget: 1000, weekly_budget: 5000, capabilities: ['tutor.chat', 'programming.debug'], price_cents: 2900, duration_days: 30 },
          advanced: { label: 'Advanced', daily_budget: null, weekly_budget: 20000, capabilities: ['tutor.chat', 'answer.grade'], price_cents: 14900, duration_days: 30 },
        },
      });
    }
    if (path === '/usage/summary') {
      return ok({
        tier,
        periods: {
          daily: { budget: 1000, reserved: 0, settled: 180, remaining: 820 },
          weekly: { budget: 5000, reserved: 0, settled: 1820, remaining: 3180 },
        },
      });
    }
    // `/membership/entitlements` — the same authority, so the same tier as `/subscription`.
    return ok({
      service_key: 'exam_11408',
      current_tier: tier,
      policy_version: 'v1',
      features: {
        learning_plan: { allowed: tier !== 'free', required_tier: 'standard', required_capability: 'planning.generate' },
        learning_report: { allowed: true, required_tier: 'free', required_capability: null },
      },
    });
  });
}

beforeEach(() => {
  GET.mockReset();
  tier = 'free';
  unknownCapability = null;
  respond();
});

describe('MembershipPage', () => {
  it('states ONE standing — the unified tier — and the policy it was resolved under', async () => {
    renderApp('/membership');
    // Scoped to the standing itself: the tier's name is also a column header in the price
    // table, so an unscoped lookup races the table's render and matches twice.
    expect(await screen.findByText('Free', { selector: '.membership-standing' })).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
    expect(screen.queryByText('当前备考方案')).not.toBeInTheDocument();
    expect(screen.queryByText('统一会员档位')).not.toBeInTheDocument();
  });

  it('shows the SAME tier the feature verdict was resolved from', async () => {
    tier = 'advanced';
    renderApp('/membership');
    expect(await screen.findByText('Advanced', { selector: '.membership-standing' })).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('prices each tier from the payload, and says 免费 rather than ¥0.00 for the one that cannot be bought', async () => {
    renderApp('/membership');
    const table = await screen.findByRole('region', { name: '档位价格与权益对照' });

    expect(within(table).getByText('¥29.00')).toBeInTheDocument();
    expect(within(table).getByText('¥149.00')).toBeInTheDocument();
    // Free has no `price_cents`, which is "cannot be ordered" — not "costs nothing".
    expect(within(table).getByText('免费')).toBeInTheDocument();
    expect(within(table).queryByText('¥0.00')).not.toBeInTheDocument();
  });

  it('renders an UNCAPPED period as a word, never as a zero', async () => {
    renderApp('/membership');
    const table = await screen.findByRole('region', { name: '档位价格与权益对照' });
    // Advanced has daily_budget null; the row must say 不限, not 0.
    expect(within(table).getByText('不限')).toBeInTheDocument();
  });

  it('carries no redemption control at all', async () => {
    renderApp('/membership');
    await screen.findByRole('region', { name: '档位价格与权益对照' });
    expect(screen.queryByLabelText('兑换码')).not.toBeInTheDocument();
    expect(screen.queryByText(/兑换/)).not.toBeInTheDocument();
  });

  it('does not print the Credit-to-money conversion as a learner-facing claim', async () => {
    renderApp('/membership');
    await screen.findByRole('region', { name: '档位价格与权益对照' });
    expect(document.body.textContent).not.toMatch(/≈\s*¥0\.01|平台成本/);
  });

  it('lists the gated feature with the verdict the entitlement endpoint returned', async () => {
    tier = 'standard';
    renderApp('/membership');
    expect(await screen.findByText('学习计划')).toBeInTheDocument();
    expect(screen.getAllByText('已开通')).toHaveLength(2);
    expect(screen.queryByText('未开通')).not.toBeInTheDocument();
  });

  it('states a locked feature requirement as a TIER, never as a legacy plan code', async () => {
    renderApp('/membership');
    expect(await screen.findByText('学习计划')).toBeInTheDocument();
    expect(screen.getByText('未开通')).toBeInTheDocument();
    expect(screen.getByText(/需要 Standard 及以上/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/monthly|quarterly|full_exam|sprint|boost/);
  });

  it('names each capability in Chinese, and never prints its internal id', async () => {
    renderApp('/membership');
    // `tutor.chat` is granted by all three tiers, so its name appears once per column.
    expect((await screen.findAllByText('学习对话')).length).toBe(3);
    expect(screen.queryByText('programming.debug')).not.toBeInTheDocument();
    expect(screen.queryByText('tutor.chat')).not.toBeInTheDocument();
  });

  it('renders NO dotted capability identifier anywhere on the learner surface', async () => {
    renderApp('/membership');
    await screen.findByText('Free', { selector: '.membership-standing' });
    expect(document.body.textContent).not.toMatch(/\b[a-z_]+\.[a-z_]+\b/);
  });

  it('names an unknown capability generically rather than printing its id', async () => {
    unknownCapability = 'internal.undeclared_capability';
    renderApp('/membership');
    await screen.findByText('Free', { selector: '.membership-standing' });
    expect(screen.getAllByText('高级学习能力').length).toBeGreaterThan(0);
    expect(screen.queryByText('internal.undeclared_capability')).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\b[a-z_]+\.[a-z_]+\b/);
  });

  it('offers a real route into the checkout for the tiers that can be bought', async () => {
    renderApp('/membership');
    const table = await screen.findByRole('region', { name: '档位价格与权益对照' });
    expect(within(table).getByRole('link', { name: /选择 Standard/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/membership/payment'),
    );
    expect(within(table).getByRole('link', { name: /选择 Advanced/ })).toHaveAttribute(
      'href',
      expect.stringContaining('tier=advanced'),
    );
  });
});
