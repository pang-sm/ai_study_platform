import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';
import type { LearningScope } from './presentation';

export type LearningReport = components['schemas']['LearningReportResponse'];
export type PlanProposal = components['schemas']['PlanAdjustmentProposal'];
export type WrongAnalysis = components['schemas']['WrongAnalysisResponse'];

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export const learningReportKey = (scope: LearningScope) => ['learning-report', scope.service_key, scope.course_id, scope.exam_module_id, scope.language] as const;

export function useLearningReport() {
  const client = useQueryClient();
  return useMutation({ mutationFn: async ({ scope, includeNarrative }: { scope: LearningScope; includeNarrative: boolean }): Promise<LearningReport> => {
    const result = await apiClient.POST('/ai/learning-report', { body: { ...scope, period_days: 7, include_narrative: includeNarrative } });
    return dataOrThrow(result.response, result.data, result.error);
  }, onSuccess: (data, variables) => { client.setQueryData(learningReportKey(variables.scope), data); } });
}

export function useWrongAnalysis() {
  return useMutation({ mutationFn: async (stateId: number): Promise<WrongAnalysis> => {
    const result = await apiClient.POST('/wrong-answers/{state_id}/analysis', { params: { path: { state_id: stateId } } });
    return dataOrThrow(result.response, result.data, result.error);
  } });
}

function invalidateAppliedPlan(client: ReturnType<typeof useQueryClient>, scope: LearningScope) {
  void client.invalidateQueries({ queryKey: ['learning', 'agenda'] });
  void client.invalidateQueries({ queryKey: learningReportKey(scope) });
  if (scope.service_key === 'course_learning') {
    void client.invalidateQueries({ queryKey: ['course', scope.course_id, 'plan'] });
    void client.invalidateQueries({ queryKey: ['course', scope.course_id, 'today-plan'] });
    void client.invalidateQueries({ queryKey: ['course', scope.course_id, 'dashboard'] });
    void client.invalidateQueries({ queryKey: ['course', scope.course_id, 'records'] });
    void client.invalidateQueries({ queryKey: ['course', scope.course_id, 'records-summary'] });
    void client.invalidateQueries({ queryKey: ['course', scope.course_id, 'state'] });
  } else if (scope.service_key === 'exam_11408') {
    void client.invalidateQueries({ queryKey: ['exam', 'cs408', 'plan', scope.exam_module_id] });
    void client.invalidateQueries({ queryKey: ['exam', 'cs408', 'study-plan', scope.exam_module_id] });
    void client.invalidateQueries({ queryKey: ['exam', 'cs408', 'records'] });
    void client.invalidateQueries({ queryKey: ['exam', 'cs408', 'state'] });
  } else {
    void client.invalidateQueries({ queryKey: ['programming', 'plan', scope.language] });
    void client.invalidateQueries({ queryKey: ['programming', 'home'] });
    void client.invalidateQueries({ queryKey: ['programming', 'records'] });
    void client.invalidateQueries({ queryKey: ['programming', 'records-summary'] });
    void client.invalidateQueries({ queryKey: ['programming', 'state'] });
  }
}

export function usePlanProposal() {
  return useMutation({ mutationFn: async ({ scope, goal }: { scope: LearningScope; goal: string }): Promise<PlanProposal> => {
    const result = await apiClient.POST('/ai/plan-adjustment', { body: { ...scope, goal } });
    return dataOrThrow(result.response, result.data, result.error);
  } });
}

export function useApplyPlanProposal(scope: LearningScope) {
  const client = useQueryClient();
  return useMutation({ mutationFn: async (proposal: PlanProposal) => {
    const result = await apiClient.POST('/ai/plan-adjustment/apply', { body: { ...scope, plan_identity: proposal.plan_identity, proposed_changes: proposal.proposed_changes ?? [], proposal_id: proposal.proposal_id } });
    return dataOrThrow(result.response, result.data, result.error);
  }, onSuccess: () => invalidateAppliedPlan(client, scope) });
}
