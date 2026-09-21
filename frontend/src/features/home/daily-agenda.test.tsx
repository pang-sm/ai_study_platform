import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DailyAgenda } from './daily-agenda';

const hooks = vi.hoisted(() => ({ useDailyAgenda: vi.fn(), useAgendaExplain: vi.fn() }));
vi.mock('./agenda-api', () => hooks);

function renderAgenda() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <DailyAgenda />
    </QueryClientProvider>,
  );
}

const twoItems = {
  isPending: false,
  isError: false,
  data: {
    items: [
      {
        action_type: 'review',
        service_namespace: 'programming',
        domain_context: { language: 'python' },
        source_type: 'review',
        source_id: 'late',
        title: '先处理到期复习',
        summary: '后端的第一项',
        priority_reason: 'due_review',
        deep_link: '/review',
        due_at: null,
        facts: { interval_days: 2 },
        status: 'open',
        resolved_by: '完成复习',
      },
      {
        action_type: 'practice',
        service_namespace: 'course_learning',
        domain_context: { course_id: 'os' },
        source_type: 'adaptive',
        source_id: 'next',
        title: '后处理练习',
        summary: '后端的第二项',
        priority_reason: 'repeated_wrong',
        deep_link: '/course/os/practice',
        due_at: null,
        facts: {},
        status: 'open',
        resolved_by: '提交作答',
      },
    ],
  },
};

describe('DailyAgenda', () => {
  beforeEach(() => {
    hooks.useDailyAgenda.mockReset();
    hooks.useAgendaExplain.mockReset();
  });

  it('keeps the server order and renders the server’s own rule text for each reason code', () => {
    hooks.useDailyAgenda.mockReturnValue(twoItems);
    // The backend answers `/learning/agenda/explain` with `priority_rules`; the UI reads its
    // reason text from there instead of repeating a label list that could drift.
    hooks.useAgendaExplain.mockReturnValue({
      data: {
        priority_rules: {
          due_review: '复习项已到期（存储或策略计算的到期日）',
          repeated_wrong: '反复做错的错题状态（wrong_count >= 2）',
        },
      },
    });
    renderAgenda();

    expect(screen.getAllByRole('listitem').map((node) => node.textContent)).toEqual([
      expect.stringContaining('先处理到期复习'),
      expect.stringContaining('后处理练习'),
    ]);
    expect(screen.getByText(/复习项已到期/)).toBeInTheDocument();
    expect(screen.getByText(/反复做错的错题状态/)).toBeInTheDocument();
    expect(screen.getByText(/完成什么动作后它会改变：完成复习/)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: '打开并完成这项学习' })[0]).toHaveAttribute(
      'href',
      '/review',
    );
  });

  it('says the basis is unavailable when the server sends no rule for the reason', () => {
    hooks.useDailyAgenda.mockReturnValue(twoItems);
    hooks.useAgendaExplain.mockReturnValue({ data: { priority_rules: {} } });
    renderAgenda();

    expect(screen.getAllByText('推荐依据暂不可显示').length).toBeGreaterThan(0);
    // The server's own reason code is not an explanation, and is not offered as one.
    expect(screen.queryByText(/due_review/)).not.toBeInTheDocument();
  });

  it('states the real empty condition instead of showing placeholder tasks', () => {
    hooks.useDailyAgenda.mockReturnValue({ isPending: false, isError: false, data: { items: [] } });
    hooks.useAgendaExplain.mockReturnValue({ data: undefined });
    renderAgenda();

    expect(screen.getByText('当前没有需要优先处理的学习任务。')).toBeInTheDocument();
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });
});
