import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { DebugAgentSurface, StrongReasoningSurface } from './advanced-learning-surfaces';

const mockUseDeepStudy = vi.fn();
const mockUseDebugAgent = vi.fn();
vi.mock('@/features/advanced/api/workflows', () => ({ useDeepStudy: () => mockUseDeepStudy(), useDebugAgent: () => mockUseDebugAgent() }));
const feedbackProps = vi.fn();
vi.mock('./ai-feedback', () => ({ AiFeedback: (props: unknown) => { feedbackProps(props); return null; } }));

const deepResponse = { capability: 'tutor.strong_reasoning', request_id: 'r1', status: 'completed', answer: '真实回答', citations: [{ material_id: 2, filename: 'os.pdf', subject: 'OS', file_type: 'pdf', snippet: '页表证据' }], material_refs: [], materials: {}, context: { service_namespace: 'course_learning' }, model: { display_name: '自动', selection: 'auto', tier: 'standard' }, usage: {}, evidence: { chunk_count: 1, material_count: 1, retrieval: 'fts_bm25' } };
const agentResponse = { agent_run_id: 'a1', status: 'completed', language: 'python', steps: [{ step_index: 2, action: 'run_tests', status: 'completed', file_type: 'test', snippet: 'after', ai_request_id: 'step-request' }, { step_index: 1, action: 'diagnose', status: 'completed', file_type: 'analysis', snippet: 'before' }], iterations_used: 1, executions_used: 2, diagnosis: 'off by one', patch_summary: 'fix', explanation: '已修复', proposed_patch: '- 1\n+ 0', final_code: 'print(0)', usage: { model_steps: 1, execution_steps: 2, actual_credits: 3, estimated_credits: 3 } };

describe('advanced evidence surfaces', () => {
  beforeEach(() => feedbackProps.mockClear());
  it('renders only the backend citation reference', () => {
    mockUseDeepStudy.mockReturnValue({ isPending: false, isError: false, data: deepResponse, error: null, mutate: vi.fn() });
    render(<StrongReasoningSurface context="课程" courseId="os" />);
    expect(screen.getByText('os.pdf')).toHaveAttribute('href', expect.stringContaining('/materials/2/preview'));
    expect(screen.queryByText(/\[1\]/)).not.toBeInTheDocument();
  });

  it.each([[403, '该高级能力需要升级后使用。'], [429, '本次额度不足，未启动深度思考。']])('shows the shared deep-study denial for %s', (status, copy) => {
    mockUseDeepStudy.mockReturnValue({ isPending: false, isError: true, data: undefined, error: new ApiRequestError(status, {}), mutate: vi.fn() });
    render(<StrongReasoningSurface context="课程" courseId="os" />);
    expect(screen.getByRole('alert')).toHaveTextContent(copy);
  });

  it('shows ordered agent evidence and changes only the editor buffer after explicit apply', async () => {
    const apply = vi.fn();
    mockUseDebugAgent.mockReturnValue({ isPending: false, isError: false, data: agentResponse, error: null, mutate: vi.fn() });
    render(<DebugAgentSurface exerciseId={7} code="print(1)" onApply={apply} />);
    // The steps read in the product's words, in step_index order — not as the codes the agent
    // logs its own actions under.
    const timeline = screen.getByRole('list').textContent ?? '';
    expect(timeline.indexOf('诊断')).toBeLessThan(timeline.indexOf('运行测试'));
    expect(timeline).not.toContain('run_tests');
    expect(timeline).not.toContain('diagnose');
    expect(apply).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: '应用到编辑器' }));
    expect(apply).toHaveBeenCalledWith('print(0)');
  });

  it('offers feedback only for the backend-identified AI Debug Agent step', () => {
    mockUseDebugAgent.mockReturnValue({ isPending: false, isError: false, data: agentResponse, error: null, mutate: vi.fn() });
    render(<DebugAgentSurface exerciseId={7} code="print(1)" onApply={vi.fn()} />);
    expect(feedbackProps).toHaveBeenCalledTimes(1);
    expect(feedbackProps).toHaveBeenCalledWith({ requestId: 'step-request', workflowId: 'a1:2' });
  });

  it('presents agent workflow failure without a fabricated result', () => {
    mockUseDebugAgent.mockReturnValue({ isPending: false, isError: true, data: undefined, error: new ApiRequestError(504, {}), mutate: vi.fn() });
    render(<DebugAgentSurface exerciseId={7} code="print(1)" onApply={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('工作流失败或超时');
  });
});
