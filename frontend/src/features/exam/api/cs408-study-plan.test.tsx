import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { useCreateCs408PlanTask, useUpdateCs408PlanTask } from './cs408-study-plan';

const calls = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn(), PATCH: vi.fn(), DELETE: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: calls }));

const task = {
  id: 8, username: 'learner', subject_key: 'data_structure', subject_name: '数据结构',
  title: '学习第1章', knowledge_point_name: '', scope_type: 'all', task_type: 'knowledge',
  computed_status: 'not_started', completion_reason: '', action_target: 'knowledge_map',
  due_date: '2026-11-14', note: '', created_at: null, updated_at: null, status: 'not_started',
  primary_knowledge: '', secondary_knowledge: '',
};

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

function ok(data: unknown) {
  return { data, error: undefined, response: { ok: true, status: 200 } as Response };
}

describe('cs408 study-plan task writes', () => {
  it('sends an edit as the editable fields only — the row id travels in the path', async () => {
    // REGRESSION. The route's request schema is `extra="forbid"`, so a body that also carried
    // `task_id` was a 422 on EVERY manual edit: the request named the row in the path and then
    // failed validation before the row was ever read. Nothing caught it because the workspace
    // test stubs this hook.
    calls.PATCH.mockResolvedValue(ok({ success: true, task }));
    const { result } = renderHook(() => useUpdateCs408PlanTask(), { wrapper });

    await result.current.mutateAsync({
      username: 'learner', subject_key: 'data_structure', task_id: 8,
      title: '学习第1章（改）', due_date: '2026-11-20',
    });

    expect(calls.PATCH).toHaveBeenCalledTimes(1);
    const [path, init] = calls.PATCH.mock.calls[0] as [string, { params: { path: Record<string, unknown> }; body: Record<string, unknown> }];
    expect(path).toBe('/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}');
    expect(init.params.path).toEqual({ subject_key: 'data_structure', task_id: 8 });
    expect(init.body).toEqual({
      username: 'learner', subject_key: 'data_structure',
      title: '学习第1章（改）', due_date: '2026-11-20',
    });
    expect(init.body).not.toHaveProperty('task_id');
  });

  it('sends a create with the fields the create schema declares', async () => {
    calls.POST.mockResolvedValue(ok({ success: true, task }));
    const { result } = renderHook(() => useCreateCs408PlanTask(), { wrapper });

    await result.current.mutateAsync({
      username: '', subject_key: 'data_structure', scope_type: 'all',
      title: '第 2 章 线性表', task_type: 'knowledge', due_date: '2026-11-15',
    });

    const [, init] = calls.POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(init.body).toEqual({
      username: '', subject_key: 'data_structure', scope_type: 'all',
      title: '第 2 章 线性表', task_type: 'knowledge', due_date: '2026-11-15',
    });
  });

  it('surfaces a rejected write instead of reporting it as saved', async () => {
    calls.PATCH.mockResolvedValue({ data: undefined, error: { detail: 'x' }, response: { ok: false, status: 422 } as Response });
    const { result } = renderHook(() => useUpdateCs408PlanTask(), { wrapper });

    await expect(result.current.mutateAsync({
      username: 'learner', subject_key: 'data_structure', task_id: 8, title: 'x',
    })).rejects.toThrow();
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
