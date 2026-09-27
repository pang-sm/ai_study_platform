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

/** The thumbs are stubbed HERE; what they offer is asserted in ai-feedback.test.tsx. */
vi.mock('@/components/learning/ai-feedback', () => ({
  AiFeedback: (props: { requestId?: string; target?: string }) => (
    <span data-testid="ai-feedback" data-request={props.requestId} data-target={props.target} />
  ),
}));

/**
 * A proposal shaped exactly like the route's — machine fields included, because the point of the
 * assertions below is that the page prints the DIFF and never the API.
 */
const proposal: PlanProposal = {
  proposal_id: 'prop-1',
  capability: 'planning.adjust',
  request_id: 'req-1',
  service_namespace: 'exam_prep',
  subject_key: 'data_structure',
  plan_identity: 'bcaaf4ffb20e8081',
  summary: '把「进程调度复习」提前 5 天，并另外调整 1 项',
  rationale: '依据你当前的记录：当前有 2 项任务已逾期。',
  adjustment_types: ['RESCHEDULE', 'INSERT', 'INCREASE_LOAD'],
  evidence: [{ code: 'plan_overdue', text: '当前有 2 项任务已逾期', metric: 2 }],
  proposed_changes: [
    { op: 'update_task', task_id: 1, due_date: '2026-09-30', type: 'RESCHEDULE',
      task_title: '进程调度复习', field: 'due_date', before: '2026-10-05', after: '2026-09-30',
      direction: 'earlier' },
    { op: 'create_task', task_id: null, title: '进程调度专项练习', task_type: 'practice',
      due_date: '2026-09-30', type: 'INSERT', task_title: '进程调度专项练习', field: 'task',
      before: null, after: '2026-09-30' },
  ],
  impact: {
    inserted: 1, rescheduled: 1, moved_earlier: 1, moved_later: 0, replaced: 0,
    task_count_before: 2, task_count_after: 3, overdue_before: 2, overdue_after: 1,
    text: '本次调整，新增 1 项任务，提前 1 项。计划中的逾期任务由 2 项变为 1 项。',
  },
  can_apply: true,
  affected_tasks: [1],
  dropped_changes: [],
  plan_snapshot: { identity: 'bcaaf4ffb20e8081', total: 2, completed: 0, overdue: 2, truncated: false,
    tasks: [{ task_id: 1, title: '进程调度复习', task_type: 'knowledge', status: 'not_started', due_date: '2026-10-05' }] },
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

async function showProposal(value: PlanProposal = proposal) {
  const user = userEvent.setup();
  generate.mockImplementation((_input: unknown, options?: { onSuccess?: (v: PlanProposal) => void }) => options?.onSuccess?.(value));
  const view = renderSurface();
  await user.click(screen.getByRole('button', { name: '生成建议' }));
  return { user, view };
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
    expect(screen.queryByText('计划')).not.toBeInTheDocument();
    expect(container.textContent).not.toContain('先生成建议，看清差异后再决定是否应用');
    expect(screen.getByLabelText('目标（可选）')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '生成建议' })).toBeInTheDocument();
    expect(screen.getByText('生成后可确认是否应用')).toBeInTheDocument();
  });

  it('offers the subject to adjust only when the space holds more than one', async () => {
    const user = userEvent.setup();
    renderSurface();
    expect(screen.getByLabelText('调整科目')).toHaveValue('data_structure');
    await user.selectOptions(screen.getByLabelText('调整科目'), 'operating_system');
    expect(scopeSelect.onChange).toHaveBeenCalledWith('operating_system');
  });

  it('answers why, what, and what it costs the plan — with no API field on the page', async () => {
    const { view } = await showProposal();
    const page = view.container.textContent ?? '';

    // WHY: a reason built from the learner's own recorded numbers
    expect(screen.getByRole('heading', { name: '为什么建议这样调整' })).toBeInTheDocument();
    expect(screen.getByText('依据你当前的记录：当前有 2 项任务已逾期。')).toBeInTheDocument();

    // WHAT: the headline, then one labelled pair per change
    expect(screen.getByText('把「进程调度复习」提前 5 天，并另外调整 1 项')).toBeInTheDocument();
    expect(screen.getByText('进程调度复习')).toBeInTheDocument();
    expect(screen.getByText('原计划：')).toBeInTheDocument();
    expect(screen.getByText('2026 年 10 月 5 日')).toBeInTheDocument();
    expect(screen.getByText('2026 年 9 月 30 日')).toBeInTheDocument();

    // IMPACT: counted, not forecast
    expect(screen.getByRole('heading', { name: '调整后影响' })).toBeInTheDocument();
    expect(screen.getByText(/逾期任务由 2 项变为 1 项/)).toBeInTheDocument();

    // no arrow to misread, and no machine field in sight
    expect(page).not.toContain('→');
    for (const field of ['update_task', 'create_task', 'task_id', 'plan_identity', 'proposal_id',
                         'bcaaf4ffb20e8081', 'capability', 'planning.adjust', 'applies_to',
                         'RESCHEDULE', 'INSERT']) {
      expect(page, `leaked ${field}`).not.toContain(field);
    }
    expect(screen.getByText('这份建议还没有应用到你的计划。')).toBeInTheDocument();
  });

  it('names an inserted task by its type, and a practice task is not called knowledge', async () => {
    await showProposal();
    // `practice` is the backend's own value; the map must not fall back to 知识学习
    expect(screen.getByText('练习')).toBeInTheDocument();
    expect(screen.queryByText('知识学习')).not.toBeInTheDocument();
  });

  it('shows a REPLACE as the old title and the new one', async () => {
    await showProposal({
      ...proposal,
      summary: '把「完成章节阅读」替换为「完成对应练习」',
      adjustment_types: ['REPLACE'],
      proposed_changes: [{ op: 'update_task', task_id: 1, title: '完成对应练习', type: 'REPLACE',
                           task_title: '完成章节阅读', field: 'title', before: '完成章节阅读',
                           after: '完成对应练习' }],
    });
    expect(screen.getByText('替换')).toBeInTheDocument();
    expect(screen.getByText('原任务：')).toBeInTheDocument();
    expect(screen.getByText('完成章节阅读')).toBeInTheDocument();
    expect(screen.getByText('完成对应练习')).toBeInTheDocument();
  });

  it('never renders a REMOVE or a REORDER, because the server cannot produce one', async () => {
    const { view } = await showProposal();
    for (const word of ['移除', '删除', '重新排序', '调整顺序', 'REMOVE', 'REORDER']) {
      expect(view.container.textContent, `rendered ${word}`).not.toContain(word);
    }
  });

  it('keeps the diff short, and puts the rest behind 查看调整详情', async () => {
    const many: PlanProposal = {
      ...proposal,
      summary: '把「A」提前 1 天，并另外调整 5 项',
      proposed_changes: Array.from({ length: 6 }, (_, index) => ({
        op: 'update_task', task_id: index + 1, due_date: '2026-09-30', type: 'RESCHEDULE',
        task_title: `任务 ${index + 1}`, field: 'due_date', before: '2026-10-05',
        after: '2026-09-30', direction: 'earlier',
      })),
    };
    const { user } = await showProposal(many);

    expect(screen.getByText('任务 1')).toBeInTheDocument();
    expect(screen.getByText('任务 4')).toBeInTheDocument();
    expect(screen.queryByText('任务 5')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '查看调整详情（还有 2 项）' }));
    expect(screen.getByText('任务 5')).toBeInTheDocument();
    expect(screen.getByText('任务 6')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '收起调整详情' }));
    expect(screen.queryByText('任务 5')).not.toBeInTheDocument();
  });

  it('rates the SUGGESTION with the plan-adjustment vocabulary', async () => {
    await showProposal();
    expect(screen.getByTestId('ai-feedback')).toHaveAttribute('data-target', 'plan_adjustment');
    expect(screen.getByTestId('ai-feedback')).toHaveAttribute('data-request', 'req-1');
  });

  it('keeps the plan unless the learner applies the proposal', async () => {
    const { user } = await showProposal();
    expect(applyMutate).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '保留当前计划' }));
    expect(applyMutate).not.toHaveBeenCalled();
    expect(screen.queryByRole('heading', { name: '建议调整' })).not.toBeInTheDocument();
  });

  it('applies the proposal only when the learner says so', async () => {
    const { user } = await showProposal();
    await user.click(screen.getByRole('button', { name: '应用调整' }));
    expect(applyMutate).toHaveBeenCalledWith(proposal, expect.anything());
  });

  it('does not offer to apply a proposal the server said cannot be applied', async () => {
    await showProposal({ ...proposal, can_apply: false });
    expect(screen.getByRole('button', { name: '应用调整' })).toBeDisabled();
  });

  it('reports a partly-applied write as partial, not as success', () => {
    hooks.useApplyPlanProposal.mockReturnValue({
      mutate: applyMutate, isPending: false, isError: false, isSuccess: true,
      data: { applied_count: 1, dropped_changes: [{ reason: 'task_not_in_this_plan' }] },
    });
    renderSurface();
    expect(screen.getByText(/1 项已生效，另有 1 项未能应用/)).toBeInTheDocument();
  });

  it('states that the plan was written once it has been', () => {
    hooks.useApplyPlanProposal.mockReturnValue({
      mutate: applyMutate, isPending: false, isError: false, isSuccess: true,
      data: { applied_count: 2, dropped_changes: [] },
    });
    renderSurface();
    expect(screen.getByText('已应用到学习计划（2 项）。')).toBeInTheDocument();
    expect(screen.queryByText('这份建议还没有应用到你的计划。')).not.toBeInTheDocument();
  });

  it('discards an unapplied proposal when the plan being adjusted changes', async () => {
    const { user, view } = await showProposal();
    expect(screen.getByRole('heading', { name: '建议调整' })).toBeInTheDocument();

    view.rerender(<DynamicPlanSurface scope={{ ...scope, exam_module_id: 'operating_system' }} scopeSelect={scopeSelect} />);
    expect(screen.queryByRole('heading', { name: '建议调整' })).not.toBeInTheDocument();
    expect(applyMutate).not.toHaveBeenCalled();
    void user;
  });
});
