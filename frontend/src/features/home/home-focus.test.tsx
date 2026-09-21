import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

function agendaItem(id: string, title: string, reason: string, deepLink: string) {
  return {
    action_type: 'review',
    service_namespace: 'exam_prep',
    domain_context: {},
    source_type: 'review',
    source_id: id,
    title,
    summary: `${title}的说明`,
    priority_reason: reason,
    deep_link: deepLink,
    due_at: null,
    facts: {},
    status: 'open',
    resolved_by: '完成这项动作',
  };
}

const AGENDA = {
  policy_version: 'v1',
  generated_at: '2026-09-20T10:00:00+00:00',
  items: [
    agendaItem('first', '先处理到期复习', 'due_review', '/review'),
    agendaItem('second', '后处理练习', 'repeated_wrong', '/course/os/practice'),
  ],
  total_items: 2,
};

const RECORDS = { records: [], has_more: false, next_cursor: null };

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async (url: string) => {
    // The three space-context reads: this learner has a course, so the page is in daily learning.
    if (url === '/course-learning/courses') return ok([{ id: 'data-structure', name: '数据结构' }]);
    if (url === '/exam/prep/profile') return ok({ configured: false, subjects: [] });
    if (url === '/programming/onboarding') return ok({ main_language: '', selected_languages: [] });
    if (url === '/learning/agenda') return ok(AGENDA);
    if (url === '/learning/agenda/explain') {
      return ok({
        priority_rules: {
          due_review: '复习项已到期（存储或策略计算的到期日）',
          repeated_wrong: '反复做错的错题状态（wrong_count >= 2）',
        },
      });
    }
    if (url === '/review/summary') return ok({ total: 2, has_stored_due_dates: true });
    if (url === '/learning-records') return ok(RECORDS);
    if (url === '/subscription') return ok({ tier: 'free', policy_version: 'v1' });
    if (url === '/subscription/plans') {
      return ok({ policy_version: 'v1', plans: { free: { label: '免费版', daily_budget: 5, weekly_budget: 25, capabilities: [] } } });
    }
    if (url === '/usage/summary') {
      return ok({
        tier: 'free',
        periods: {
          daily: { budget: 5, reserved: 0, settled: 1, remaining: 4 },
          weekly: { budget: 25, reserved: 0, settled: 6, remaining: 19 },
        },
      });
    }
    throw new Error(`unexpected GET ${url}`);
  });
});

function precedes(first: Node, second: Node) {
  return Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('home hierarchy', () => {
  it("gives the server's first agenda item the focal treatment, once, before the agenda list", async () => {
    renderApp('/');

    // The focus panel is named by the task it holds — the server's own first item.
    const focus = await screen.findByRole('region', { name: '先处理到期复习' });
    expect(within(focus).getByText(/复习项已到期/)).toBeInTheDocument();
    expect(within(focus).getByRole('link', { name: '打开并完成这项学习' })).toHaveAttribute(
      'href',
      '/review',
    );

    const agenda = screen.getByRole('region', { name: '今天接下来学什么' });
    expect(precedes(focus, agenda)).toBe(true);

    // Promoted, not duplicated: the same task must not read as two.
    expect(screen.getAllByText('先处理到期复习')).toHaveLength(1);
    // And the remaining list keeps the order the server returned.
    const remaining = within(agenda).getAllByRole('listitem').map((node) => node.textContent);
    expect(remaining).toHaveLength(1);
    expect(remaining[0]).toContain('后处理练习');
  });

  it('keeps the learning spaces below the learner’s own work and the membership strip last', async () => {
    renderApp('/');

    const agenda = await screen.findByRole('region', { name: '今天接下来学什么' });
    const recent = screen.getByRole('region', { name: '最近学习' });
    const spaces = screen.getByRole('region', { name: '选择你的学习方向' });
    const membership = screen.getByRole('region', { name: '会员档位与可用额度' });

    expect(precedes(agenda, recent)).toBe(true);
    expect(precedes(recent, spaces)).toBe(true);
    expect(precedes(spaces, membership)).toBe(true);
  });

  it('sends each space to its own route rather than presenting a decorative index', async () => {
    renderApp('/');
    const spaces = await screen.findByRole('region', { name: '选择你的学习方向' });

    const targets = within(spaces)
      .getAllByRole('link')
      .map((link) => link.getAttribute('href'));
    expect(targets).toEqual(['/exam', '/course', '/programming']);
  });

  it('leaves the agenda section to state the empty case when the server ranks nothing first', async () => {
    get.mockImplementation(async (url: string) => {
      if (url === '/course-learning/courses') return ok([{ id: 'data-structure', name: '数据结构' }]);
      if (url === '/exam/prep/profile') return ok({ configured: false, subjects: [] });
      if (url === '/programming/onboarding') return ok({ main_language: '', selected_languages: [] });
      if (url === '/learning/agenda') return ok({ ...AGENDA, items: [], total_items: 0 });
      if (url === '/learning/agenda/explain') return ok({ priority_rules: {} });
      if (url === '/review/summary') return ok({ total: 0, has_stored_due_dates: false });
      if (url === '/learning-records') return ok(RECORDS);
      if (url === '/subscription') return ok({ tier: 'free', policy_version: 'v1' });
      if (url === '/subscription/plans') return ok({ policy_version: 'v1', plans: {} });
      if (url === '/usage/summary') return ok({ tier: 'free', periods: {} });
      throw new Error(`unexpected GET ${url}`);
    });

    renderApp('/');

    expect(await screen.findByText('当前没有需要优先处理的学习任务。')).toBeInTheDocument();
    // Nothing to promote, so no empty focus panel is invented to hold the slot.
    expect(screen.queryByText('当前重点')).not.toBeInTheDocument();
  });
});
