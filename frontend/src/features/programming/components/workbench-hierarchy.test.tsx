import { render, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkbenchPage } from './programming-pages';

/** The workbench carries a breadcrumb, so it needs a router the way the real page has one. */
async function renderWorkbench() {
  const router = createRouter({
    routeTree: createRootRoute({ component: () => <WorkbenchPage language="python" exerciseId={1} /> }),
    history: createMemoryHistory(),
  });
  const result = render(<RouterProvider router={router} />);
  // The router renders on a tick, so every case waits for the page before asserting on it.
  await screen.findByRole('heading', { level: 1 });
  return result;
}

const mockAction = vi.fn();
const mockExercise = vi.fn();
const mockDiagnose = vi.fn();
const mockAnalyze = vi.fn();

vi.mock('../api/programming', () => ({
  useProgrammingAction: () => mockAction(),
  useProgrammingExercise: () => mockExercise(),
  useCodeDiagnose: () => mockDiagnose(),
  useCodeAnalysis: () => mockAnalyze(),
  useProgrammingHome: vi.fn(),
  useProgrammingExercises: vi.fn(),
  useProgrammingPlan: vi.fn(),
  useProgrammingRecords: vi.fn(),
  useProgrammingRecordsSummary: vi.fn(),
  useProgrammingState: vi.fn(),
}));
vi.mock('@/components/learning/advanced-learning-surfaces', () => ({
  DebugAgentSurface: () => <p>debug-agent-surface</p>,
}));
vi.mock('@/components/learning/ai-feedback', () => ({ AiFeedback: () => null }));

const EXERCISE = {
  exercise: {
    id: 1,
    language: 'Python',
    title: '两数之和',
    statement: '读入两个整数，输出它们的和。',
    input_format: '一行，两个整数。',
    output_format: '一个整数。',
    constraints: '|a| ≤ 100',
    hints: '注意输入可能为负数。',
    difficulty: '入门',
    source_label: '原创题目',
    public_samples: [{ input: '1 2', output: '3' }],
  },
};

beforeEach(() => {
  mockAction.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
  mockDiagnose.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
  mockAnalyze.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
  mockExercise.mockReturnValue({ isPending: false, isError: false, data: EXERCISE });
});

// The filled action of the Button component is the only thing on the page wearing `bg-primary`
// as its own background; `hover:bg-primary-soft` etc. must not count.
const FILLED = /(?:^|\s)bg-primary(?:\s|$)/;
const DETERMINISTIC = '确定性工具（不调用模型、不消耗额度）';

describe('workbench tool hierarchy', () => {
  it('keeps the deterministic tools in one tier with a single primary action', async () => {
    await renderWorkbench();

    const tier = screen.getByRole('group', { name: DETERMINISTIC });
    // All the deterministic actions live together, and exactly one of them is the filled action.
    for (const name of ['运行', '运行测试', '运行代码诊断', '开始练习']) {
      expect(within(tier).getByRole('button', { name }).className).not.toMatch(FILLED);
    }
    expect(within(tier).getByRole('button', { name: '提交' }).className).toMatch(FILLED);
    expect(
      within(tier)
        .getAllByRole('button')
        .filter((button) => FILLED.test(button.className)),
    ).toHaveLength(1);
  });

  it('puts the single AI call in its own tier rather than beside the deterministic tools', async () => {
    await renderWorkbench();

    const tier = screen.getByRole('group', { name: DETERMINISTIC });
    expect(within(tier).queryByRole('button', { name: 'AI Debug' })).toBeNull();

    const aiTier = screen.getByRole('region', { name: 'AI Debug（AI 代码分析）' });
    expect(within(aiTier).getByRole('button', { name: 'AI Debug' })).toBeInTheDocument();
    // The AI surface is the one that spends credits, and it says so.
    expect(within(aiTier).getByText(/会消耗额度/)).toBeInTheDocument();
  });

  it('keeps the multi-step agent workflow folded until it is asked for', async () => {
    await renderWorkbench();

    const summary = screen.getByText(/高级工作流：Debug Agent/);
    const details = summary.closest('details');
    expect(details).not.toBeNull();
    expect(details).not.toHaveAttribute('open');
    expect(within(details as HTMLElement).getByText('debug-agent-surface')).toBeInTheDocument();
  });

  it('renders the statement as the fields the backend sends, with hints held back', async () => {
    await renderWorkbench();

    expect(screen.getByRole('heading', { name: '两数之和' })).toBeInTheDocument();
    expect(screen.getByText('读入两个整数，输出它们的和。')).toBeInTheDocument();
    expect(screen.getByText('一行，两个整数。')).toBeInTheDocument();
    expect(screen.getByText('一个整数。')).toBeInTheDocument();
    expect(screen.getByText('|a| ≤ 100')).toBeInTheDocument();
    expect(screen.getByText('1 2')).toBeInTheDocument();

    // Support a learner asks for stays folded rather than answering the exercise on arrival.
    const hints = screen.getByText('提示（先自己尝试再看）');
    expect(hints.closest('details')).not.toHaveAttribute('open');
    expect(screen.queryByText(/后端原文|原始返回数据/)).not.toBeInTheDocument();
  });
});
