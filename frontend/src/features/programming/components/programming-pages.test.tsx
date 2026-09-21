import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
const feedbackProps = vi.fn();

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
vi.mock('@/components/learning/advanced-learning-surfaces', () => ({ DebugAgentSurface: () => null }));
vi.mock('@/components/learning/ai-feedback', () => ({
  AiFeedback: (props: unknown) => {
    feedbackProps(props);
    return null;
  },
}));

/** A mutation stub whose `mutate` resolves synchronously through the caller's `onSuccess`. */
function mutationStub(onRun: (variables: unknown) => unknown) {
  return () => ({
    isPending: false,
    isError: false,
    mutate: vi.fn((variables: unknown, options?: { onSuccess?: (data: unknown) => void }) =>
      options?.onSuccess?.(onRun(variables)),
    ),
  });
}

describe('programming learning aids', () => {
  beforeEach(() => {
    feedbackProps.mockClear();
    mockAction.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
    mockExercise.mockReturnValue({ isPending: false, isError: false, data: { id: 1 } });
  });

  it('presents 代码诊断 as a compiler check and never as AI feedback', async () => {
    // The payload deliberately carries a `request_id` to prove the UI does not treat a compiler
    // verdict as a ratable AI answer, whatever the object happens to contain.
    mockDiagnose.mockImplementation(
      mutationStub(() => ({
        language: 'Python',
        status: 'error',
        errors: [{ line: 4, column: 7, message: 'invalid syntax', severity: 'error', source: 'python' }],
        warnings: [],
        request_id: 'must-not-be-used',
      })),
    );
    mockAnalyze.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });

    await renderWorkbench();
    await userEvent.type(screen.getByLabelText('代码'), 'print(');
    await userEvent.click(screen.getByRole('button', { name: '运行代码诊断' }));

    const result = await screen.findByLabelText('代码诊断结果');
    expect(result).toHaveTextContent('4:7');
    expect(result).toHaveTextContent('invalid syntax');
    expect(result).toHaveTextContent('来源：python');
    expect(feedbackProps).not.toHaveBeenCalled();
  });

  it('requires a question before calling the AI endpoint, then rates the real request', async () => {
    mockDiagnose.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
    mockAnalyze.mockImplementation(
      mutationStub(() => ({ success: true, answer: '变量在使用前没有赋值。', request_id: 'ai-request-1' })),
    );

    await renderWorkbench();
    await userEvent.type(screen.getByLabelText('代码'), 'print(x)');

    const aiDebug = screen.getByRole('button', { name: 'AI Debug' });
    expect(aiDebug).toBeDisabled();
    expect(screen.getByText(/请输入要分析的问题/)).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('要分析的问题'), '这段代码为什么报错？');
    expect(aiDebug).toBeEnabled();
    await userEvent.click(aiDebug);

    const answer = await screen.findByLabelText('AI 代码分析回答');
    expect(answer).toHaveTextContent('变量在使用前没有赋值。');
    expect(feedbackProps).toHaveBeenCalledWith({
      requestId: 'ai-request-1',
      workflowId: 'programming_ai_explain',
    });
  });

  it('routes the failed-test shortcut to the AI endpoint with the run output as the question', async () => {
    const actionMutate = vi.fn(
      (_variables: unknown, options?: { onSuccess?: (data: unknown) => void }) =>
        options?.onSuccess?.({ passed: false, stderr: 'AssertionError: expected 3' }),
    );
    mockAction.mockReturnValue({ isPending: false, isError: false, mutate: actionMutate });
    mockDiagnose.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
    const analyzeMutate = vi.fn(
      (_variables: unknown, options?: { onSuccess?: (data: unknown) => void }) =>
        options?.onSuccess?.({ success: true, answer: '边界条件没有处理。', request_id: 'ai-request-2' }),
    );
    mockAnalyze.mockReturnValue({ isPending: false, isError: false, mutate: analyzeMutate });

    await renderWorkbench();
    await userEvent.type(screen.getByLabelText('代码'), 'def f(): pass');
    // The toolbar's labels are the product's own action words (运行 / 运行测试 / 提交); only the
    // button's visible label changed, the endpoint it calls is asserted below.
    await userEvent.click(screen.getByRole('button', { name: '运行测试' }));

    await userEvent.click(await screen.findByRole('button', { name: '用 AI Debug 分析这次失败' }));

    expect(analyzeMutate).toHaveBeenCalledTimes(1);
    const variables = analyzeMutate.mock.calls[0]?.[0] as { language: string; question: string };
    expect(variables.language).toBe('Python');
    expect(variables.question).toContain('测试未通过');
    expect(variables.question).toContain('AssertionError: expected 3');
  });
});
