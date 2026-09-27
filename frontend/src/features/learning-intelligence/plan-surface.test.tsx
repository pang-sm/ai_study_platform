import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import type { LearningScope } from './presentation';
import { DynamicPlanSurface } from './learning-intelligence-surfaces';

type PlanProposal = components['schemas']['PlanAdjustmentProposal'];

const hooks = vi.hoisted(() => ({ usePlanProposal: vi.fn(), useApplyPlanProposal: vi.fn() }));
vi.mock('./api', () => ({
  usePlanProposal: hooks.usePlanProposal,
  useApplyPlanProposal: hooks.useApplyPlanProposal,
  useLearningReport: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useWrongAnalysis: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));
vi.mock('@/components/learning/ai-feedback', () => ({ AiFeedback: () => null }));

/**
 * A proposal shaped exactly like the route's: the machine fields are all present, because the
 * point of the assertions below is that the page does NOT print them.
 */
const proposal: PlanProposal = {
  proposal_id: 'prop-1',
  capability: 'planning.generate',
  request_id: 'req-1',
  service_namespace: 'exam_prep',
  subject_key: 'data_structure',
  plan_identity: 'bcaaf4ffb20e8081',
  reason: '按「这周复习完数据结构」调整当前计划',
  proposed_changes: [
    { op: 'update_task', task_id: 1, title: null, task_type: null, due_date: '2026-09-30', status: null, reason: '按本次目标把这一项提前' },
    { op: 'create_task', task_id: null, title: '这周复习完数据结构', task_type: 'knowledge', due_date: '2026-10-04', status: null, reason: '来自本次目标' },
  ],
  affected_tasks: [1],
  dropped_changes: [],
  plan_snapshot: { identity: 'bcaaf4ffb20e8081', total: 2, completed: 0, overdue: 0, truncated: false,
    tasks: [{ task_id: 1, title: '理解数据结构的基本概念', task_type: 'knowledge', status: 'not_started', due_date: '2026-10-02' }] },
  usage: { estimated_credits: 1, actual_credits: 1, input_tokens: 300, output_tokens: 90, usage_source: 'PROVIDER_REPORTED' },
  applies_to: 'POST /ai/plan-adjustment/apply',
  generated_at: '2026-09-27T03:31:49+00:00',
};

const scope: LearningScope = { service_key: 'exam_11408', course_id: '', exam_module_id: 'data_structure', language: '' };
const scopeSelect = { label: '调整科目', value: 'data_structure', options: [{ value: 'data_structure', label: '数据结构' }, { value: 'operating_system', label: '操作系统' }], onChange: vi.fn() };

const generate = vi.fn();
const applyMutate = vi.fn();

function renderSurface() {
  return render(<DynamicPlanSurface scope={scope} scopeSelect={scopeSelect} />);
}

describe('DynamicPlanSurface', () => {
  beforeEach(() => {
    generate.mockReset();
    applyMutate.mockReset();
    scopeSelect.onChange.mockReset();
    hooks.usePlanProposal.mockReturnValue({ mutate: generate, isPending: false, isError: false });
    hooks.useApplyPlanProposal.mockReturnValue({ mutate: applyMutate, isPending: false, isError: false, isSuccess: false });
  });

  it('opens on the action, not on an explanation of the action', () => {
    const { container } = renderSurface();
    expect(screen.getByRole('heading', { name: '调整计划' })).toBeInTheDocument();
    // The three-layer restatement the round removed: an eyebrow naming the tab, a headline, and a
    // paragraph explaining what generating does.
    expect(screen.queryByText('计划')).not.toBeInTheDocument();
    expect(container.textContent).not.toContain('先生成建议，看清差异后再决定是否应用');
    expect(screen.getByLabelText('目标（可选）')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '生成建议' })).toBeInTheDocument();
    // What the paragraph used to say, said once and lightly, next to the button that does it.
    expect(screen.getByText('生成后可确认是否应用')).toBeInTheDocument();
  });

  it('offers the subject to adjust only when the space holds more than one', () => {
    renderSurface();
    expect(screen.getByLabelText('调整科目')).toHaveValue('data_structure');
    return userEvent.setup().selectOptions(screen.getByLabelText('调整科目'), 'operating_system')
      .then(() => expect(scopeSelect.onChange).toHaveBeenCalledWith('operating_system'));
  });

  it('asks for a proposal and shows a diff a learner can read, with no API field in it', async () => {
    const user = userEvent.setup();
    generate.mockImplementation((_input: unknown, options?: { onSuccess?: (value: PlanProposal) => void }) => options?.onSuccess?.(proposal));
    const { container } = renderSurface();

    await user.type(screen.getByLabelText('目标（可选）'), '这周复习完数据结构');
    await user.click(screen.getByRole('button', { name: '生成建议' }));
    expect(generate).toHaveBeenCalledWith(
      { scope, goal: '这周复习完数据结构' }, expect.anything());

    expect(screen.getByRole('heading', { name: '建议调整' })).toBeInTheDocument();
    expect(screen.getByText('按「这周复习完数据结构」调整当前计划')).toBeInTheDocument();
    // A change is "a task is added" or "a task moves", written in the learner's words, and the
    // task is named by the title the plan actually holds.
    expect(screen.getByText('新增')).toBeInTheDocument();
    expect(screen.getByText('调整')).toBeInTheDocument();
    expect(screen.getByText('理解数据结构的基本概念')).toBeInTheDocument();
    expect(screen.getByText(/计划日期：2026-10-02 → 2026-09-30/)).toBeInTheDocument();
    expect(screen.getByText('这周复习完数据结构')).toBeInTheDocument();

    // Not one machine field reaches the page.
    for (const field of ['create_task', 'update_task', 'task_id', 'plan_identity', 'proposal_id', 'bcaaf4ffb20e8081', 'capability', 'planning.generate', 'applies_to']) {
      expect(container.textContent, `leaked ${field}`).not.toContain(field);
    }
    expect(container.textContent).not.toMatch(/[{"[]/);
    expect(screen.getByText('这份建议还没有应用到你的计划。')).toBeInTheDocument();
  });

  it('keeps the plan unless the learner applies the proposal', async () => {
    const user = userEvent.setup();
    generate.mockImplementation((_input: unknown, options?: { onSuccess?: (value: PlanProposal) => void }) => options?.onSuccess?.(proposal));
    renderSurface();
    await user.click(screen.getByRole('button', { name: '生成建议' }));

    // Generating is not applying: nothing has been written yet.
    expect(applyMutate).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '保留当前计划' }));
    expect(applyMutate).not.toHaveBeenCalled();
    expect(screen.queryByRole('heading', { name: '建议调整' })).not.toBeInTheDocument();
  });

  it('applies the proposal only when the learner says so', async () => {
    const user = userEvent.setup();
    generate.mockImplementation((_input: unknown, options?: { onSuccess?: (value: PlanProposal) => void }) => options?.onSuccess?.(proposal));
    renderSurface();
    await user.click(screen.getByRole('button', { name: '生成建议' }));

    await user.click(screen.getByRole('button', { name: '应用调整' }));
    expect(applyMutate).toHaveBeenCalledWith(proposal, expect.anything());
  });

  it('discards an unapplied proposal when the plan being adjusted changes', async () => {
    const user = userEvent.setup();
    generate.mockImplementation((_input: unknown, options?: { onSuccess?: (value: PlanProposal) => void }) => options?.onSuccess?.(proposal));
    const { rerender } = render(<DynamicPlanSurface scope={scope} scopeSelect={scopeSelect} />);
    await user.click(screen.getByRole('button', { name: '生成建议' }));
    expect(screen.getByRole('heading', { name: '建议调整' })).toBeInTheDocument();

    // The learner switches from 数据结构 to 操作系统. A 数据结构 diff must not stay on screen
    // under a 操作系统 selector, where "应用调整" would read as applying it to that paper.
    rerender(<DynamicPlanSurface scope={{ ...scope, exam_module_id: 'operating_system' }} scopeSelect={scopeSelect} />);
    expect(screen.queryByRole('heading', { name: '建议调整' })).not.toBeInTheDocument();
    expect(applyMutate).not.toHaveBeenCalled();
  });
});
