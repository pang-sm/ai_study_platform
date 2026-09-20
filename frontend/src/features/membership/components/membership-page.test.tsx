/**
 * ACCEL_PRODUCT_S10 PART C — the membership surface, and the flows it refuses to fake.
 *
 * The rules this file enforces:
 *
 *  * ONE membership. The page states the unified tier once, and the tier it shows is the same
 *    tier `/membership/entitlements` resolved the feature verdict from — so the page cannot
 *    describe a lock that is not the real one. There is no second "备考方案" standing.
 *  * Activation uses `/subscription/redeem`, the ONE redeem flow, and a success is rendered
 *    as the tier the backend reports AFTER activation — not as a promise that a feature
 *    opened. (The backend guarantee that it did open is pinned server-side.)
 *  * No legacy plan code reaches the DOM. The code's stored target is an internal alias; the
 *    learner sees the TIER.
 *  * No order is created: `/subscription/orders` makes a PENDING order whose only payment
 *    method is a mock that production refuses, so it could never be settled.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError } from '@/features/exam/api/content-status';

const previewMutate = vi.fn();
const redeemMutate = vi.fn();
const postSpy = vi.fn();

// What a real code would grant, in unified-tier terms only.
const PREVIEW = {
  tier: 'standard',
  tier_label: 'Standard',
  duration_days: 30,
  current_tier: 'free',
  projected_expires_at: '2026-10-20T00:00:00+00:00',
  code_expires_at: null,
};

const REDEEMED = {
  tier: 'standard',
  tier_label: 'Standard',
  status: 'active',
  end_at: '2026-10-20 00:00:00',
  duration_days: 30,
  current_tier: 'standard',
};

let previewData: typeof PREVIEW | undefined;
let previewError: unknown;
let redeemData: typeof REDEEMED | undefined;
let redeemError: unknown;

// The tier the whole page is rendered under. Both authorities read this one value, which is
// the point: they are one authority, so a fixture that made them disagree would be testing a
// state the backend cannot produce.
let tier = 'free';
const entitlementsFor = (t: string) => ({
  service_key: 'exam_11408',
  current_tier: t,
  policy_version: 'v1',
  features: {
    learning_plan: { allowed: t !== 'free', required_tier: 'standard', required_capability: 'planning.generate' },
    learning_report: { allowed: true, required_tier: 'free', required_capability: null },
  },
});

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    GET: async (path: string) => {
      if (path === '/subscription') {
        return { data: { tier, policy_version: 'v1' }, response: { ok: true, status: 200 } };
      }
      if (path === '/subscription/plans') {
        return {
          data: {
            policy_version: 'v1',
            plans: {
              free: { label: 'Free', daily_budget: 100, weekly_budget: 500, capabilities: ['tutor.chat', 'question.explain'] },
              standard: { label: 'Standard', daily_budget: 1000, weekly_budget: 5000, capabilities: ['tutor.chat', 'programming.debug'] },
              advanced: { label: 'Advanced', daily_budget: null, weekly_budget: 20000, capabilities: ['tutor.chat', 'answer.grade'] },
            },
          },
          response: { ok: true, status: 200 },
        };
      }
      if (path === '/usage/summary') {
        return {
          data: {
            tier,
            periods: {
              daily: { budget: 1000, reserved: 0, settled: 180, remaining: 820 },
              weekly: { budget: 5000, reserved: 0, settled: 1820, remaining: 3180 },
            },
          },
          response: { ok: true, status: 200 },
        };
      }
      // /membership/entitlements — same authority, so the same tier as /subscription.
      return { data: entitlementsFor(tier), response: { ok: true, status: 200 } };
    },
    POST: (path: string) => {
      postSpy(path);
      if (path === '/subscription/redeem/preview') {
        return Promise.resolve({ data: previewData, error: previewError, response: { ok: !previewError, status: previewError ? 400 : 200 } });
      }
      return Promise.resolve({ data: redeemData, error: redeemError, response: { ok: !redeemError, status: redeemError ? 400 : 200 } });
    },
  },
}));

// Only the two MUTATIONS are overridden, and only so their result and error states can be
// driven directly. Every QUERY keeps its real implementation and reads through the mocked
// transport above, so the page's data path is the real one.
vi.mock('../api/subscription', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('../api/subscription');
  return {
    ...actual,
    usePreviewRedemption: () => ({ mutate: previewMutate, isPending: false, isError: Boolean(previewError), error: previewError, data: previewData }),
    useRedeem: () => ({ mutate: redeemMutate, isPending: false, isError: Boolean(redeemError), error: redeemError, data: redeemData }),
  };
});

import { MembershipPage } from './membership-page';

function renderPage() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MembershipPage /></QueryClientProvider>);
}

describe('MembershipPage', () => {
  beforeEach(() => {
    previewData = undefined;
    previewError = undefined;
    redeemData = undefined;
    redeemError = undefined;
    tier = 'free';
    postSpy.mockClear();
    redeemMutate.mockClear();
    // The real mutation invokes its `onSuccess` callback; the page records the previewed code
    // there and refuses to confirm until it has one. A mock that never fires it would leave
    // the confirm path permanently unreachable and silently pass a test of nothing.
    previewMutate.mockReset();
    previewMutate.mockImplementation((_code: string, options?: { onSuccess?: () => void }) => {
      options?.onSuccess?.();
    });
  });

  it('states ONE standing — the unified tier — and the policy it was resolved under', async () => {
    renderPage();
    expect(await screen.findByText('Free')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
    // The dual standing is GONE: no second membership is described anywhere on the page.
    expect(screen.queryByText('当前备考方案')).not.toBeInTheDocument();
    expect(screen.queryByText('统一会员档位')).not.toBeInTheDocument();
  });

  it('shows the SAME tier the feature verdict was resolved from', async () => {
    tier = 'advanced';
    renderPage();
    expect(await screen.findByText('Advanced')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('renders an UNCAPPED period as a word, never as a zero', async () => {
    renderPage();
    // Advanced has daily_budget null in the plan ledger; the row must say 不限, not 0.
    expect(await screen.findByText('不限')).toBeInTheDocument();
  });

  it('lists the gated feature with the verdict the entitlement endpoint returned', async () => {
    tier = 'standard';
    renderPage();
    expect(await screen.findByText('学习计划')).toBeInTheDocument();
    // learning_plan and learning_report are both open at Standard, so both say 已开通.
    expect(screen.getAllByText('已开通')).toHaveLength(2);
    expect(screen.queryByText('未开通')).not.toBeInTheDocument();
  });

  it('states a locked feature requirement as a TIER, never as a legacy plan code', async () => {
    renderPage();
    expect(await screen.findByText('学习计划')).toBeInTheDocument();
    expect(screen.getByText('未开通')).toBeInTheDocument();
    // The requirement vocabulary is the same one the tier table uses.
    expect(screen.getByText(/需要 Standard 及以上/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/monthly|quarterly|full_exam|sprint|boost/);
  });

  it('shows each plan capability by its real id, so nothing is hidden behind a label', async () => {
    renderPage();
    expect(await screen.findByText('programming.debug')).toBeInTheDocument();
    expect(screen.getByText('代码调试')).toBeInTheDocument();
  });

  it('does NOT create a pending order — no checkout that cannot complete is offered', async () => {
    renderPage();
    await screen.findByText('Free');
    expect(screen.getByText(/在线支付尚未开通/)).toBeInTheDocument();
    const unavailable = screen.getByRole('button', { name: '暂不可用' });
    expect(unavailable).toBeDisabled();
    expect(postSpy).not.toHaveBeenCalledWith('/subscription/orders');
    await userEvent.click(unavailable);
    expect(postSpy).not.toHaveBeenCalledWith('/subscription/orders');
  });

  it('previews a code before activating, showing the TIER it actually grants', async () => {
    previewData = PREVIEW;
    renderPage();
    await userEvent.type(await screen.findByLabelText('兑换码'), 'ZX-2026-CS408');
    await userEvent.click(screen.getByRole('button', { name: '查询' }));
    expect(previewMutate).toHaveBeenCalledWith('ZX-2026-CS408', expect.anything());
    expect(await screen.findByText(/可开通/)).toBeInTheDocument();
    expect(screen.getByText(/30 天/)).toBeInTheDocument();
    expect(screen.getByText(/当前 Free/)).toBeInTheDocument();
    // typing a code activates nothing; confirmation is a separate, explicit act
    expect(redeemMutate).not.toHaveBeenCalled();
  });

  it('surfaces the backend refusal instead of a generic failure', async () => {
    // A real `ApiRequestError`, which is what the transport throws — the page reads its
    // `detail` so the backend's own message reaches the learner.
    previewError = new ApiRequestError(400, { detail: '兑换码不存在' });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('兑换码不存在');
  });

  it('reports a successful redemption as the tier the backend now holds', async () => {
    redeemData = REDEEMED;
    renderPage();
    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent('兑换成功');
    expect(status).toHaveTextContent('Standard');
  });

  it('confirms activation only on the second, explicit act', async () => {
    // Which ENDPOINT the real mutation posts to is asserted in ../api/subscription.test.tsx;
    // here the mutation is replaced, so this pins the page's behaviour around it.
    previewData = PREVIEW;
    renderPage();
    await userEvent.type(await screen.findByLabelText('兑换码'), 'ZX-2026-CS408');
    await userEvent.click(screen.getByRole('button', { name: '查询' }));
    expect(redeemMutate).not.toHaveBeenCalled();
    await userEvent.click(await screen.findByRole('button', { name: '确认激活' }));
    expect(redeemMutate).toHaveBeenCalledWith('ZX-2026-CS408', expect.anything());
    expect(postSpy).not.toHaveBeenCalledWith('/subscription/orders');
    expect(postSpy).not.toHaveBeenCalledWith('/membership/redeem');
  });
});
