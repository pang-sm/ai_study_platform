import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408StudyPlanWorkspace } from './cs408-study-plan-workspace';

type Plan = components['schemas']['ExamStudyPlanResponse'];

const plan = (subject_key: string, subject_name: string, tasks: Plan['tasks']): Plan => ({
  course_id: `${subject_key}_11408`, course_name: subject_name, subject_key, subject_name,
  settings: { learning_goal: '', start_date: null, daily_hours: null, weekly_days: null, review_strategy: 'sequential', show_completed: true },
  stats: { total_knowledge_points: 12, mastered: 0, total_sections: 2, sections_completed: 0, sections_learning: 0, sections_not_started: 2, overall_progress: 0, overall_status: 'not_started' },
  review_interval_days: 7, chapters: [], tasks,
});

const task: Plan['tasks'][number] = {
  id: 7, username: 'learner', subject_key: 'operating_system', subject_name: '操作系统', title: '理解虚拟内存', knowledge_point_name: '虚拟内存', scope_type: 'single', task_type: 'knowledge', computed_status: 'in_progress', completion_reason: '已有学习记录', action_target: 'knowledge_map', due_date: '2026-10-01', note: '', created_at: null, updated_at: null, status: 'in_progress', primary_knowledge: '', secondary_knowledge: '',
};

const refetch = vi.fn();
let entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1', features: {} }, refetch };
let plans: Array<{ isPending: boolean; isError: boolean; data?: Plan; refetch: typeof refetch }> = [];
const hooks = vi.hoisted(() => ({ useCs408StudyPlans: vi.fn() }));
/** Mutable so one case can hold a mutation "in flight" and check the submit is locked out. */
const writes = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn(), remove: vi.fn(), pending: false, failed: false }));
/** The AI surfaces are stubbed — their own behaviour is asserted in plan-surface.test.tsx. */
const initialPlan = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false, isError: false, error: undefined as unknown }));

vi.mock('@/features/exam/api/cs408-study-plan', () => ({
  useExamPlanEntitlement: () => entitlement,
  useCs408StudyPlans: hooks.useCs408StudyPlans,
  useCreateCs408PlanTask: () => ({ mutateAsync: writes.create, isPending: writes.pending, isError: writes.failed }),
  useUpdateCs408PlanTask: () => ({ mutateAsync: writes.update, isPending: writes.pending, isError: writes.failed }),
  useDeleteCs408PlanTask: () => ({ mutateAsync: writes.remove, isPending: writes.pending, isError: writes.failed }),
}));
vi.mock('@/features/learning-intelligence/api', () => ({
  useInitialPlanProposal: () => initialPlan,
}));
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: Record<string, string | number | undefined> }) => {
  const parameters = new URLSearchParams(); Object.entries(search ?? {}).forEach(([key, value]) => { if (value !== undefined) parameters.set(key, String(value)); });
  return <a href={`${to}${parameters.size ? `?${parameters}` : ''}`}>{children}</a>;
} }));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));
// This suite isolates the plan page's information architecture. The assistant's surfaces have
// their own query-client integration tests; mounting them here would make a layout test depend on
// mutation infrastructure. They still RECORD the props they were handed, so the scope and the
// callbacks the page passes down are asserted here.
const surfaces = vi.hoisted(() => ({ adjust: [] as Array<Record<string, unknown>>, draft: [] as Array<Record<string, unknown>> }));
vi.mock('@/features/learning-intelligence/learning-intelligence-surfaces', () => ({
  DynamicPlanSurface: (props: Record<string, unknown>) => { surfaces.adjust.push(props); return null; },
  InitialPlanDraftSurface: (props: Record<string, unknown>) => { surfaces.draft.push(props); return null; },
}));

/** The LAST field with this label — the existing row is also editable, so index 0 is not it. */
function lastField(label: string): HTMLElement {
  const fields = screen.getAllByLabelText(label);
  const field = fields[fields.length - 1];
  if (!field) throw new Error(`no field labelled ${label}`);
  return field;
}

function unlocked(tasks: Plan['tasks'] = [task], moduleKey = 'operating_system') {
  entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'standard', policy_version: 'v1', features: { learning_plan: { allowed: true, required_tier: 'standard', required_capability: 'planning.generate' } } }, refetch };
  plans = [{ isPending: false, isError: false, data: plan(moduleKey, '操作系统', tasks), refetch }];
}

/** An account with an EMPTY plan — the state that used to be offered an "adjust" it could not have. */
function unlockedAndEmpty() {
  entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'standard', policy_version: 'v1', features: { learning_plan: { allowed: true, required_tier: 'standard', required_capability: 'planning.generate' } } }, refetch };
  plans = [{ isPending: false, isError: false, data: plan('operating_system', '操作系统', []), refetch }];
}

describe('Cs408StudyPlanWorkspace', () => {
  hooks.useCs408StudyPlans.mockImplementation(() => plans);
  beforeEach(() => {
    writes.create.mockReset().mockResolvedValue({});
    writes.update.mockReset().mockResolvedValue({});
    writes.remove.mockReset().mockResolvedValue(undefined);
    writes.pending = false;
    writes.failed = false;
    initialPlan.mutate.mockReset();
    initialPlan.isPending = false;
    initialPlan.isError = false;
    initialPlan.error = undefined;
    surfaces.adjust.length = 0;
    surfaces.draft.length = 0;
    // Back to the locked default every case starts from; a case opts into access with unlocked().
    entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1', features: {} }, refetch };
    plans = [];
  });

  /* ── the empty plan: two things you can do, and no "adjust" ───────────────────────── */

  it('offers an empty plan only the two ways to make one', () => {
    unlockedAndEmpty();
    render(<Cs408StudyPlanWorkspace />);

    expect(screen.getByRole('heading', { name: '当前计划' })).toBeInTheDocument();
    expect(screen.getByText('暂无学习计划')).toBeInTheDocument();
    expect(screen.getByText('可以自己添加任务，也可以生成一个初始计划。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '添加任务' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '生成初始计划' })).toBeInTheDocument();

    // REGRESSION: with nothing to adjust, "adjust" must not be offered at all — not as a button,
    // not as a panel, and not as an assistant that answers about a plan that does not exist.
    expect(screen.queryByRole('button', { name: '调整计划' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '编辑计划' })).not.toBeInTheDocument();
    expect(surfaces.adjust).toHaveLength(0);
  });

  it('opens the initial-plan panel on click and hides the empty-state actions while it is open', async () => {
    unlockedAndEmpty();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);

    expect(surfaces.draft).toHaveLength(0);
    await user.click(screen.getByRole('button', { name: '生成初始计划' }));

    expect(surfaces.draft).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '生成初始计划' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '添加任务' })).not.toBeInTheDocument();
  });

  it('draws the first plan for the paper the learner is looking at, from their own goal', async () => {
    unlockedAndEmpty();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace moduleKey="data_structure" />);
    await user.click(screen.getByRole('button', { name: '生成初始计划' }));

    const props = surfaces.draft.at(-1) as { scopeLabel: string; onGenerate: () => void };
    // The DRAFT is asked for the paper in view, and its own generation is what the panel runs.
    expect(props.scopeLabel).toBe('数据结构');
    expect(initialPlan.mutate).not.toHaveBeenCalled();
    act(() => props.onGenerate());
    expect(initialPlan.mutate).toHaveBeenCalledWith(
      expect.objectContaining({ scope: expect.objectContaining({ exam_module_id: 'data_structure' }) }),
      expect.anything(),
    );
  });

  it('saves the draft through the ordinary task endpoint, and only when it has days', async () => {
    unlockedAndEmpty();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '生成初始计划' }));

    // The panel holds the draft; the page holds the save. A task the model could not date has no
    // day, and the page writes nothing until it does.
    const props = surfaces.draft.at(-1) as { onSave: () => void; draft?: unknown };
    initialPlan.mutate.mockImplementation((_input: unknown, options?: { onSuccess?: (v: unknown) => void }) =>
      options?.onSuccess?.({ tasks: [
        { title: '第 1 章 总览', task_type: 'knowledge', due_date: null, needs_due_date: true },
      ] }));
    act(() => (surfaces.draft.at(-1) as { onGenerate: () => void }).onGenerate());
    await act(async () => { props.onSave(); });
    expect(writes.create).not.toHaveBeenCalled();
  });

  it('writes every dated row, and nothing else, when the draft is saved', async () => {
    unlockedAndEmpty();
    const user = userEvent.setup();
    // The tab carries `?module=`, so the draft is drawn for — and saved into — the paper in view.
    render(<Cs408StudyPlanWorkspace moduleKey="operating_system" />);
    await user.click(screen.getByRole('button', { name: '生成初始计划' }));

    initialPlan.mutate.mockImplementation((_input: unknown, options?: { onSuccess?: (v: unknown) => void }) =>
      options?.onSuccess?.({ tasks: [
        { title: '第 1 章 总览', task_type: 'knowledge', due_date: '2026-10-01', needs_due_date: false },
        { title: '第 2 章 线性表', task_type: 'chapter_practice', due_date: '2026-10-03', needs_due_date: false },
      ] }));
    act(() => (surfaces.draft.at(-1) as { onGenerate: () => void }).onGenerate());
    await act(async () => { (surfaces.draft.at(-1) as { onSave: () => void }).onSave(); });

    expect(writes.create).toHaveBeenCalledTimes(2);
    expect(writes.create).toHaveBeenNthCalledWith(1, expect.objectContaining({
      subject_key: 'operating_system', title: '第 1 章 总览', due_date: '2026-10-01', task_type: 'knowledge',
    }));
    expect(writes.create).toHaveBeenNthCalledWith(2, expect.objectContaining({
      title: '第 2 章 线性表', task_type: 'chapter_practice',
    }));
    // Proposing wrote nothing; only the save did.
    expect(writes.update).not.toHaveBeenCalled();
    expect(writes.remove).not.toHaveBeenCalled();
  });

  it('keeps only the rows that did NOT land, so a retry cannot write a second copy', async () => {
    unlockedAndEmpty();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '生成初始计划' }));

    initialPlan.mutate.mockImplementation((_input: unknown, options?: { onSuccess?: (v: unknown) => void }) =>
      options?.onSuccess?.({ tasks: [
        { title: '先写入的', task_type: 'knowledge', due_date: '2026-10-01', needs_due_date: false },
        { title: '没写成的', task_type: 'knowledge', due_date: '2026-10-02', needs_due_date: false },
      ] }));
    writes.create.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error('offline'));
    act(() => (surfaces.draft.at(-1) as { onGenerate: () => void }).onGenerate());
    await act(async () => { (surfaces.draft.at(-1) as { onSave: () => void }).onSave(); });

    const after = surfaces.draft.at(-1) as { draft?: Array<{ title: string }> };
    expect(after.draft?.map((row) => row.title)).toEqual(['没写成的']);
  });

  /* ── an existing plan: edit it, or adjust it ─────────────────────────────────────── */

  it('offers a plan that exists its own actions, and no first-plan action', () => {
    unlocked();
    render(<Cs408StudyPlanWorkspace />);

    expect(screen.getByRole('button', { name: '添加任务' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '编辑计划' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '调整计划' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '生成初始计划' })).not.toBeInTheDocument();
    expect(screen.queryByText('暂无学习计划')).not.toBeInTheDocument();
    // the adjust panel is folded: it is rendered, but closed, and its trigger is the toolbar's
    const props = surfaces.adjust.at(-1) as { open: boolean };
    expect(props.open).toBe(false);
  });

  it('unfolds the adjust panel from the toolbar, carrying the paper in view', async () => {
    unlocked();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace moduleKey="data_structure" />);
    await user.click(screen.getByRole('button', { name: '调整计划' }));

    const props = surfaces.adjust.at(-1) as { open: boolean; scope: { service_key: string; exam_module_id: string }; scopeSelect: { value: string; label: string; options: Array<{ value: string }> } };
    expect(props.open).toBe(true);
    expect(props.scope.service_key).toBe('exam_11408');
    expect(props.scope.exam_module_id).toBe('data_structure');
    expect(props.scopeSelect.label).toBe('调整科目');
    expect(props.scopeSelect.options.map((option) => option.value)).toEqual(['data_structure', 'computer_organization', 'operating_system', 'computer_network']);
  });

  it('saves a manual edit through the real task endpoint', async () => {
    unlocked();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);

    // The current plan is read-only until the learner says they are editing it.
    expect(screen.queryByLabelText('任务名称')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '编辑计划' }));
    const title = screen.getByLabelText('任务名称');
    await user.clear(title);
    await user.type(title, '理解虚拟内存（重做）');
    await user.clear(screen.getByLabelText('计划日期'));
    await user.type(screen.getByLabelText('计划日期'), '2026-10-09');
    await user.click(screen.getByRole('button', { name: '保存计划' }));

    expect(writes.update).toHaveBeenCalledTimes(1);
    expect(writes.update).toHaveBeenCalledWith(expect.objectContaining({
      subject_key: 'operating_system', task_id: 7, title: '理解虚拟内存（重做）', due_date: '2026-10-09',
    }));
    // A save that writes nothing else is not a save.
    expect(writes.create).not.toHaveBeenCalled();
    expect(writes.remove).not.toHaveBeenCalled();
  });

  it('adds a task with the day it is planned for', async () => {
    unlocked();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '编辑计划' }));
    await user.click(screen.getByRole('button', { name: '添加一条任务' }));
    // the existing row is also editable now, so the NEW task is the last set of fields
    await user.type(lastField('任务名称'), '复习进程调度');
    await user.clear(lastField('计划日期'));
    await user.type(lastField('计划日期'), '2026-10-02');
    await user.click(screen.getByRole('button', { name: '保存计划' }));

    expect(writes.create).toHaveBeenCalledWith(expect.objectContaining({
      subject_key: 'operating_system', title: '复习进程调度', due_date: '2026-10-02',
    }));
  });

  it('opens the manual editor straight from 添加任务 on a plan that exists', async () => {
    unlocked();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '添加任务' }));
    // It authors a row; it does not write one.
    expect(writes.create).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '保存计划' })).toBeInTheDocument();
    expect(screen.getAllByLabelText('任务名称')).toHaveLength(2);
  });

  it('refuses to save a task with no day, and says why', async () => {
    unlocked();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '编辑计划' }));
    await user.click(screen.getByRole('button', { name: '添加一条任务' }));
    await user.type(lastField('任务名称'), '没有日期的任务');
    await user.clear(lastField('计划日期'));

    expect(screen.getByText('请先为每个任务选择计划日期。')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '保存计划' }));
    expect(writes.create).not.toHaveBeenCalled();
    expect(writes.update).not.toHaveBeenCalled();
  });

  it('deletes a task only when the save is confirmed', async () => {
    unlocked();
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '编辑计划' }));
    await user.click(screen.getByRole('button', { name: '删除任务' }));
    expect(writes.remove).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '放弃修改' }));
    expect(writes.remove).not.toHaveBeenCalled();
    expect(screen.getByText('理解虚拟内存')).toBeInTheDocument();
  });

  it('does not accept a second submit while the first is in flight', async () => {
    unlocked();
    writes.pending = true;
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '编辑计划' }));
    const save = screen.getByRole('button', { name: '正在保存…' });
    expect(save).toBeDisabled();
    await user.click(save);
    expect(writes.update).not.toHaveBeenCalled();
  });

  it('reports a failed save and stays in the editor instead of pretending it worked', async () => {
    unlocked();
    writes.failed = true;
    const user = userEvent.setup();
    render(<Cs408StudyPlanWorkspace />);
    await user.click(screen.getByRole('button', { name: '编辑计划' }));
    expect(screen.getByText('保存失败，计划未改变。请检查网络后重试。')).toBeInTheDocument();
    // still editing — the learner's unsaved work is not thrown away by a network error
    expect(screen.getByRole('button', { name: '保存计划' })).toBeInTheDocument();
  });

  /* ── the locked / unreadable states are unchanged ────────────────────────────────── */

  it('treats a missing learning_plan feature as locked and does not mount plan content', () => {
    plans = [];
    render(<Cs408StudyPlanWorkspace />);
    // 学习计划 is the tab above, so it survives only as the region's accessible name.
    expect(screen.getByRole('heading', { name: '学习计划' })).toHaveClass('sr-only');
    expect(screen.getByText('当前档位暂未开放学习计划')).toBeInTheDocument();
    expect(screen.queryByText('理解虚拟内存')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '生成初始计划' })).not.toBeInTheDocument();
    expect(hooks.useCs408StudyPlans).toHaveBeenLastCalledWith(false);
  });

  it('names the unified tier the lock requires, not a legacy plan code', () => {
    // ACCEL_PRODUCT_S10 PART D: the locked state has to tell the learner what to change, in
    // the vocabulary the membership page actually offers. `monthly_sprint` named no tier.
    entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1', features: { learning_plan: { allowed: false, required_tier: 'standard', required_capability: 'planning.generate' } } }, refetch };
    plans = [];
    render(<Cs408StudyPlanWorkspace />);
    expect(screen.getByText(/需要 Standard 及以上档位/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看会员档位与权益' })).toHaveAttribute('href', '/membership');
    expect(screen.queryByText(/monthly_sprint|备考方案/)).not.toBeInTheDocument();
  });

  it('groups the plan by the day it is planned for, and keeps every fact on the row', () => {
    // Far enough out that the label is a date rather than 今天 / 明天.
    unlocked([{ ...task, due_date: '2026-12-01' },
              { ...task, id: 8, title: '复习进程调度', due_date: '2026-12-03', computed_status: 'not_started', status: 'not_started' }]);
    render(<Cs408StudyPlanWorkspace />);

    // The body opens on the tasks themselves: no 学习计划 headline, no subtitle restating the tab.
    expect(screen.getByRole('heading', { name: '学习计划' })).toHaveClass('sr-only');
    expect(screen.getByText('12 月 1 日')).toBeInTheDocument();
    expect(screen.getByText('12 月 3 日')).toBeInTheDocument();
    expect(screen.getByText('理解虚拟内存')).toBeInTheDocument();
    expect(screen.getByText('复习进程调度')).toBeInTheDocument();
    // status and the factual action survive the regrouping
    expect(screen.getByText('进行中')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '继续学习' })).toHaveAttribute('href', '/exam/cs408/knowledge?module=operating_system');
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /完成|标记/i })).not.toBeInTheDocument();
  });

  it('names the day relatively only where that is unambiguous', () => {
    const today = new Date();
    const pad = (value: number) => String(value).padStart(2, '0');
    const iso = (offset: number) => {
      const day = new Date(today); day.setDate(day.getDate() + offset);
      return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;
    };
    unlocked([{ ...task, id: 11, title: '今天的任务', due_date: iso(0) },
              { ...task, id: 12, title: '明天的任务', due_date: iso(1) }]);
    render(<Cs408StudyPlanWorkspace />);
    expect(screen.getByText('今天')).toBeInTheDocument();
    expect(screen.getByText('明天')).toBeInTheDocument();
  });
});
