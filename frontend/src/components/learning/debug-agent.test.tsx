import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DebugAgentSurface } from './advanced-learning-surfaces';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { POST: post, GET: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const AGENT_RESULT = {
  agent_run_id: 'run-1',
  status: 'completed',
  language: 'Python',
  iterations_used: 2,
  executions_used: 1,
  tests_before: { total: 2, passed: 1 },
  tests_after: { total: 2, passed: 2 },
  proposed_patch: '- return x\n+ return x + 1',
  final_code: 'def f(x):\n    return x + 1',
  diagnosis: '缺少边界处理。',
  patch_summary: '补上边界处理',
  explanation: '边界条件补齐后测试通过。',
  usage: { model_steps: 2, execution_steps: 1, actual_credits: 4, estimated_credits: 5 },
  steps: [
    { step_index: 1, action: 'diagnose', status: 'ok', ai_request_id: 'ai-step-1', capability: 'programming.debug' },
    { step_index: 2, action: 'run_tests', status: 'ok', tests: { total: 2, passed: 2 } },
  ],
};

function renderAgent(onApply = vi.fn()) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DebugAgentSurface exerciseId={7} code="def f(x): return x" onApply={onApply} />
    </QueryClientProvider>,
  );
  return onApply;
}

beforeEach(() => {
  post.mockReset();
  post.mockImplementation(async () => ({
    data: AGENT_RESULT,
    error: undefined,
    response: { ok: true, status: 200 },
  }));
});

describe('Debug Agent', () => {
  it('runs the bounded multi-step workflow on its own endpoint, not the single-shot ones', async () => {
    renderAgent();

    await userEvent.click(screen.getByRole('button', { name: '启动 Debug Agent' }));

    expect(post).toHaveBeenCalledTimes(1);
    const [url, options] = post.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(url).toBe('/programming/agent/debug');
    expect(options.body).toMatchObject({
      exercise_id: 7,
      files: [{ filename: 'editor-buffer', content: 'def f(x): return x' }],
    });
    // Deliberately NOT the deterministic compiler check and NOT the single AI analysis call.
    expect(url).not.toBe('/code/diagnose');
    expect(url).not.toBe('/code/analyze');
  });

  it('shows the whole trace, both test measurements and what the run cost', async () => {
    renderAgent();

    await userEvent.click(screen.getByRole('button', { name: '启动 Debug Agent' }));

    // The workflow's own status word, in the product's language: `completed` is not something a
    // learner should ever have to read.
    expect(await screen.findByText(/状态：已完成 · 迭代：2 · 执行：1/)).toBeInTheDocument();
    // Each step is named in the product's words, and the agent's own action codes stay internal.
    const steps = screen.getByRole('region', { name: '工作流步骤' }).textContent ?? '';
    expect(steps).toContain('诊断');
    expect(steps).toContain('运行测试');
    expect(steps).not.toContain('diagnose');
    expect(steps).not.toContain('run_tests');
    // The measurements are rendered as the facts they are, not as the JSON they arrived in.
    const result = screen.getByRole('region', { name: '本次运行的结果' }).textContent ?? '';
    expect(result).toContain('诊断');
    expect(result).toContain('缺少边界处理。');
    expect(result).toContain('测试前');
    expect(result).toContain('测试后');
    // What the run cost, in the product's words and from the settled figure only.
    expect(screen.getByText('本次使用 4 点 AI 额度')).toBeInTheDocument();
    expect(result).not.toContain('estimated_credits');
  });

  it('keeps the agent advisory: the patch is reviewed and only the editor buffer changes', async () => {
    const onApply = renderAgent();

    await userEvent.click(screen.getByRole('button', { name: '启动 Debug Agent' }));
    expect(await screen.findByText(/这是 advisory 工作流：不会自动或永久覆盖项目文件/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '应用到编辑器' }));
    expect(onApply).toHaveBeenCalledWith('def f(x):\n    return x + 1');
  });
});
