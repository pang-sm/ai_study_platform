import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';
import { cs408Modules } from './dashboard-summary';

export type Cs408Plan = components['schemas']['ExamStudyPlanResponse'];
export type MembershipEntitlements = components['schemas']['MembershipEntitlementsResponse'];
export type Cs408PlanTask = components['schemas']['ExamStudyPlanTaskItem'];
export type Cs408TaskCreate = components['schemas']['ExamStudyPlanTaskCreate'];
export type Cs408TaskUpdate = components['schemas']['ExamStudyPlanTaskUpdate'];

export const examPlanEntitlementKey = ['membership', 'entitlements', 'exam_11408'] as const;
export const cs408PlanKey = (subjectKey: string) => ['exam', 'cs408', 'plan', subjectKey] as const;

async function requestEntitlement(): Promise<MembershipEntitlements> {
  const { data, error, response } = await apiClient.GET('/membership/entitlements', { params: { query: { service_key: 'exam_11408' } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function requestPlan(subjectKey: string): Promise<Cs408Plan> {
  const { data, error, response } = await apiClient.GET('/exam/11408/subjects/{subject_key}/study-plan', { params: { path: { subject_key: subjectKey } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useExamPlanEntitlement() {
  return useQuery({ queryKey: examPlanEntitlementKey, queryFn: requestEntitlement, retry: false });
}

export function useCs408StudyPlans(enabled: boolean) {
  return useQueries({
    queries: cs408Modules.map((module) => ({
      queryKey: cs408PlanKey(module.key), queryFn: () => requestPlan(module.key), enabled, retry: false, refetchOnWindowFocus: true,
    })),
  });
}

/* ── Manual authoring ──────────────────────────────────────────────────────────────
 *
 * These are the learner's OWN edits, saved against the real task endpoints. They are kept
 * apart from the AI proposal path on purpose: a proposal is a suggestion until it is applied,
 * while a manual save is the plan itself changing. Both end at the same rows, so both
 * invalidate the same keys.
 */

async function createPlanTask(input: Cs408TaskCreate): Promise<Cs408PlanTask> {
  const { data, error, response } = await apiClient.POST('/exam/11408/subjects/{subject_key}/study-plan/tasks', {
    params: { path: { subject_key: input.subject_key } },
    body: input,
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data.task;
}

async function updatePlanTask(input: Cs408TaskUpdate & { task_id: number }): Promise<Cs408PlanTask> {
  // `task_id` identifies the ROW and travels in the path; the body carries only what may change.
  // The route's schema forbids unknown fields, so leaving the id in the body was a 422 on every
  // edit — the request never reached the row it named.
  const { task_id, ...editable } = input;
  const { data, error, response } = await apiClient.PATCH('/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}', {
    params: { path: { subject_key: input.subject_key, task_id } },
    body: editable,
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data.task;
}

async function deletePlanTask(input: { subject_key: string; task_id: number }): Promise<void> {
  const { error, response } = await apiClient.DELETE('/exam/11408/subjects/{subject_key}/study-plan/tasks/{task_id}', {
    params: { path: { subject_key: input.subject_key, task_id: input.task_id } },
  });
  if (!response.ok) throw new ApiRequestError(response.status, error);
}

/** Every mutation re-reads the plans, so what the learner sees next is what the server holds. */
function useRefreshPlans() {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all(cs408Modules.map((module) => queryClient.invalidateQueries({ queryKey: cs408PlanKey(module.key) })));
  };
}

export function useCreateCs408PlanTask() {
  const refresh = useRefreshPlans();
  return useMutation({ mutationFn: createPlanTask, onSuccess: refresh });
}

export function useUpdateCs408PlanTask() {
  const refresh = useRefreshPlans();
  return useMutation({ mutationFn: updatePlanTask, onSuccess: refresh });
}

export function useDeleteCs408PlanTask() {
  const refresh = useRefreshPlans();
  return useMutation({ mutationFn: deletePlanTask, onSuccess: refresh });
}
