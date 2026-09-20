/**
 * ACCEL_PRODUCT_S9 PART G — the membership surface, and the flows it refuses to fake.
 *
 * The rule this file enforces: the page states what the BACKEND says and offers only actions
 * the backend can actually complete.
 *
 *  * `/membership/entitlements` is the same endpoint the Study Plan locked state reads, so
 *    the requirement shown on one surface cannot disagree with the requirement on the other.
 *  * Activation uses `/membership/redeem`, the path that writes the per-direction plan the
 *    feature gates actually read. `/subscription/redeem` moves a different number and opens
 *    no feature — see `backend/tests/test_s9_membership_and_status.py`.
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

// What a real code would grant. The plan's OWN name and duration, which is what the learner
// confirms against.
const PREVIEW = {
  success: true,
  preview: {
    service_key: 'exam_11408', target_plan: 'monthly_sprint',
    target_plan_name: '月度冲刺包', membership_duration_days: 30,
    code_expires_at: null, current_plan: 'free', current_expires_at: null,
    projected_expires_at: '2026-10-20T00:00:00+00:00', remaining_redemptions: 1,
  },
};

let previewData: typeof PREVIEW | undefined;
let previewError: unknown;
let redeemData: { message: string } | undefined;
let redeemError: unknown;

vi.mock('@/lib/api/client', () => ({
  apiClient: {
    GET: async (path: string) => {
      if (path === '/subscription') {
        return { data: { tier: 'standard', policy_version: 'v1' }, response: { ok: true, status: 200 } };
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
            tier: 'standard',
            periods: {
              daily: { budget: 1000, reserved: 0, settled: 180, remaining: 820 },
              weekly: { budget: 5000, reserved: 0, settled: 1820, remaining: 3180 },
            },
          },
          response: { ok: true, status: 200 },
        };
      }
      // /membership/entitlements
      return {
        data: {
          service_key: 'exam_11408',
          current_plan: 'free',
          features: { learning_plan: { allowed: false, required_plan: 'monthly_sprint' } },
        },
        response: { ok: true, status: 200 },
      };
    },
    POST: (path: string) => {
      postSpy(path);
      if (path === '/membership/redeem/preview') {
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
    postSpy.mockClear();
    previewMutate.mockClear();
    redeemMutate.mockClear();
  });

  it('states the CURRENT tier, the policy it was resolved under, and the gating plan', async () => {
    renderPage();
    expect(await screen.findByText('Standard')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
    // the two membership facts are shown as separate, equally weighted statements
    expect(screen.getByText('统一会员档位')).toBeInTheDocument();
    expect(screen.getByText('当前备考方案')).toBeInTheDocument();
  });

  it('renders an UNCAPPED period as a word, never as a zero', async () => {
    renderPage();
    // Advanced has daily_budget null in the plan ledger; the row must say 不限, not 0.
    expect(await screen.findByText('不限')).toBeInTheDocument();
  });

  it('lists the gated feature with the verdict the entitlement endpoint returned', async () => {
    renderPage();
    expect(await screen.findByText('学习计划')).toBeInTheDocument();
    expect(screen.getByText('未开通')).toBeInTheDocument();
  });

  it('shows each plan capability by its real id, so nothing is hidden behind a label', async () => {
    renderPage();
    expect(await screen.findByText('programming.debug')).toBeInTheDocument();
    expect(screen.getByText('代码调试')).toBeInTheDocument();
  });

  it('does NOT create a pending order — no checkout that cannot complete is offered', async () => {
    renderPage();
    await screen.findByText('Standard');
    expect(screen.getByText(/在线支付尚未开通/)).toBeInTheDocument();
    const unavailable = screen.getByRole('button', { name: '暂不可用' });
    expect(unavailable).toBeDisabled();
    expect(postSpy).not.toHaveBeenCalledWith('/subscription/orders');
    await userEvent.click(unavailable);
    expect(postSpy).not.toHaveBeenCalledWith('/subscription/orders');
  });

  it('previews a code before activating, showing the plan it actually grants', async () => {
    previewData = PREVIEW;
    renderPage();
    await userEvent.type(await screen.findByLabelText('兑换码'), 'ZX-2026-CS408');
    await userEvent.click(screen.getByRole('button', { name: '查询' }));
    expect(previewMutate).toHaveBeenCalledWith('ZX-2026-CS408', expect.anything());
    expect(await screen.findByText('月度冲刺包')).toBeInTheDocument();
    expect(screen.getByText(/30 天/)).toBeInTheDocument();
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

  it('reports the consumed code by the backend message, not a paraphrase', async () => {
    redeemData = { message: '兑换成功' };
    renderPage();
    expect(await screen.findByRole('status')).toHaveTextContent('兑换成功，权益已更新。');
  });
});
