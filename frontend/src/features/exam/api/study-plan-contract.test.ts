import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '@/types/api';

const { GET, POST, PATCH, DELETE } = vi.hoisted(() => ({
  GET: vi.fn(),
  POST: vi.fn(),
  PATCH: vi.fn(),
  DELETE: vi.fn(),
}));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, POST, PATCH, DELETE } }));

import { apiClient } from '@/lib/api/client';

// BC8 — compile-level proof that the canonical CS408 study-plan transport is concrete and
// can express the minimum F1C5 flow, with NO handwritten transport DTO and no cast. Every
// alias resolves through the generated `paths` / `components`, so a regeneration that
// drops or loosens one of these operations fails `npm run typecheck` rather than silently
// becoming `unknown`.
//
// The status in this contract is DERIVED, not writable. There is deliberately no way to
// express `status` in a task write: completing a task means performing the factual action
// its type points at (`action_target`), not asserting a checkbox.

type PlanResponse = paths['/exam/11408/subjects/{subject_key}/study-plan']['get']['responses'][200]['content']['application/json'];
type CreateBody = paths['/exam/11408/subjects/{subject_key}/study-plan/tasks']['post']['requestBody']['content']['application/json'];
type CreateResponse = paths['/exam/11408/subjects/{subject_key}/study-plan/tasks']['post']['responses'][200]['content']['application/json'];
type UpdateBody = paths['/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}']['patch']['requestBody']['content']['application/json'];
type UpdateResponse = paths['/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}']['patch']['responses'][200]['content']['application/json'];
type DeleteResponse = paths['/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}']['delete']['responses'][200]['content']['application/json'];
type SettingsBody = paths['/exam/11408/subjects/{subject_key}/study-plan/settings']['patch']['requestBody']['content']['application/json'];
type SettingsResponse = paths['/exam/11408/subjects/{subject_key}/study-plan/settings']['patch']['responses'][200]['content']['application/json'];
type SummaryResponse = paths['/exam/11408/study-plan/tasks/summary']['get']['responses'][200]['content']['application/json'];

type Plan = components['schemas']['ExamStudyPlanResponse'];
type PlanTask = components['schemas']['ExamStudyPlanTaskItem'];
type TaskStatus = PlanTask['computed_status'];
type ActionTarget = PlanTask['action_target'];
type Settings = components['schemas']['ExamStudyPlanSettings'];

// The vocabulary the workspace renders — closed by the backend, never guessed here.
const STATUS_LABELS: Record<TaskStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
};

// Where a task's status actually comes from. The plan workspace links out; it never
// asserts a completion the learner has not earned.
const ACTION_TARGETS: Record<ActionTarget, string> = {
  knowledge_map: '去知识脉络',
  practice_center: '去练习中心',
};

function statusLabel(task: PlanTask) {
  return STATUS_LABELS[task.computed_status];
}

function actionLabel(task: PlanTask) {
  return ACTION_TARGETS[task.action_target];
}

function moduleOf(plan: Plan) {
  return { key: plan.subject_key, name: plan.subject_name };
}

// The only date the backend owns is the factual due_date string plus its own overdue rule.
function dueLabel(task: PlanTask, today = new Date().toISOString().slice(0, 10)) {
  if (!task.due_date) return '未设期限';
  return task.due_date < today ? `逾期 · ${task.due_date}` : task.due_date;
}

function incompleteTasks(plan: Plan) {
  return plan.tasks.filter((task) => task.computed_status !== 'completed');
}

const task: PlanTask = {
  id: 1,
  username: 'learner',
  subject_key: 'operating_system',
  subject_name: '操作系统',
  title: '进程管理第一遍',
  knowledge_point_name: '1.1 操作系统的基本概念',
  scope_type: 'single',
  task_type: 'knowledge',
  computed_status: 'in_progress',
  completion_reason: '已掌握 1/8 个知识点，等待知识脉络中标记为已学习',
  action_target: 'knowledge_map',
  due_date: '2026-12-01',
  note: '',
  created_at: '2026-09-19T09:00:00Z',
  updated_at: '2026-09-19T09:00:00Z',
  status: 'in_progress',
  primary_knowledge: '',
  secondary_knowledge: '',
};

const settings: Settings = {
  learning_goal: '',
  start_date: null,
  daily_hours: null,
  weekly_days: null,
  review_strategy: 'sequential',
  show_completed: true,
};

const plan: PlanResponse = {
  course_id: 'operating_system_11408',
  course_name: '操作系统',
  subject_key: 'operating_system',
  subject_name: '操作系统',
  settings,
  stats: {
    total_knowledge_points: 222,
    mastered: 1,
    total_sections: 18,
    sections_completed: 0,
    sections_learning: 1,
    sections_not_started: 17,
    overall_progress: 0,
    overall_status: 'not_started',
  },
  review_interval_days: 7,
  chapters: [],
  tasks: [task],
};

describe('BC8 CS408 study-plan generated contract', () => {
  it('types the plan list with a truthful, derived status and its reason', async () => {
    GET.mockResolvedValue({
      data: plan,
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });

    const { data } = await apiClient.GET('/exam/11408/subjects/{subject_key}/study-plan', {
      params: { path: { subject_key: 'operating_system' } },
    });
    if (!data) throw new Error('unreachable');

    expect(moduleOf(data)).toEqual({ key: 'operating_system', name: '操作系统' });
    const [first] = data.tasks;
    if (!first) throw new Error('unreachable');
    expect(statusLabel(first)).toBe('进行中');
    // the backend explains WHY, so the UI never has to infer a status
    expect(first.completion_reason).not.toBe('');
    // `status` mirrors `computed_status`; neither is writable
    expect(first.status).toBe(first.computed_status);
    expect(incompleteTasks(data)).toHaveLength(1);
    expect(actionLabel(first)).toBe('去知识脉络');
    expect(dueLabel(first, '2026-11-01')).toBe('2026-12-01');
    expect(dueLabel(first, '2026-12-31')).toBe('逾期 · 2026-12-01');
    expect(dueLabel({ ...first, due_date: '' }, '2026-12-31')).toBe('未设期限');
  });

  it('types a task write without any way to assert a status', async () => {
    const body: CreateBody = {
      username: 'learner',
      subject_key: 'operating_system',
      title: '进程管理第一遍',
      knowledge_point_name: '1.1 操作系统的基本概念',
      scope_type: 'single',
      task_type: 'knowledge',
      due_date: '2026-12-01',
      note: '',
    };
    // @ts-expect-error a status is not part of the task write contract
    const withStatus: CreateBody = { ...body, status: 'completed' };
    void withStatus;

    POST.mockResolvedValue({
      data: { success: true, task },
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });
    const created = await apiClient.POST(
      '/exam/11408/subjects/{subject_key}/study-plan/tasks',
      { params: { path: { subject_key: 'operating_system' } }, body },
    );
    if (!created.data) throw new Error('unreachable');
    const createResponse: CreateResponse = created.data;
    // the write answers with the SAME task shape the list returns
    const asPlanTask: PlanTask = createResponse.task;
    expect(statusLabel(asPlanTask)).toBe('进行中');

    const patch: UpdateBody = { username: 'learner', subject_key: 'operating_system', note: '备注' };
    PATCH.mockResolvedValue({
      data: { success: true, task },
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });
    const updated = await apiClient.PATCH(
      '/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}',
      { params: { path: { subject_key: 'operating_system', task_id: 1 } }, body: patch },
    );
    if (!updated.data) throw new Error('unreachable');
    const updateResponse: UpdateResponse = updated.data;
    expect(updateResponse.task.id).toBe(1);
  });

  it('types the delete and settings writes', async () => {
    DELETE.mockResolvedValue({
      data: { success: true, deleted_id: 1 },
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });
    const removed = await apiClient.DELETE(
      '/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}',
      { params: { path: { subject_key: 'operating_system', task_id: 1 } } },
    );
    if (!removed.data) throw new Error('unreachable');
    const deleteResponse: DeleteResponse = removed.data;
    expect(deleteResponse.deleted_id).toBe(1);

    const settingsBody: SettingsBody = {
      username: 'learner',
      subject_key: 'operating_system',
      learning_goal: '60 天冲线',
      weekly_days: 6,
    };
    PATCH.mockResolvedValue({
      data: { success: true, settings },
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });
    const patched = await apiClient.PATCH(
      '/exam/11408/subjects/{subject_key}/study-plan/settings',
      { params: { path: { subject_key: 'operating_system' } }, body: settingsBody },
    );
    if (!patched.data) throw new Error('unreachable');
    const settingsResponse: SettingsResponse = patched.data;
    // the settings write returns the same shape the plan read does
    expect(settingsResponse.settings).toEqual(plan.settings);
    expect(settingsResponse.settings.start_date).toBeNull();
  });

  it('types the incomplete-task summary', async () => {
    GET.mockResolvedValue({
      data: { tasks: [task] },
      error: undefined,
      response: { ok: true, status: 200 } as Response,
    });
    const { data } = await apiClient.GET('/exam/11408/study-plan/tasks/summary', {});
    if (!data) throw new Error('unreachable');
    const summary: SummaryResponse = data;
    expect(summary.tasks).toHaveLength(1);
    expect(summary.tasks[0]?.action_target).toBe('knowledge_map');
  });
});
