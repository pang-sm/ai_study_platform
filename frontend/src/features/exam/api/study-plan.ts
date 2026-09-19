import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ExamStudyPlan = components['schemas']['ExamStudyPlanResponse'];
export type ExamKnowledgeItemUpdate = components['schemas']['ExamStudyPlanKnowledgeItemUpdate'];
export type ExamKnowledgeItemUpdateResponse = components['schemas']['ExamKnowledgeItemUpdateResponse'];

export const examStudyPlanKey = (moduleKey: string) => ['exam', 'cs408', 'study-plan', moduleKey] as const;
export const examDashboardSummaryKey = (moduleKey: string) => ['exam', 'cs408', 'dashboard-summary', moduleKey] as const;

async function requestStudyPlan(moduleKey: string): Promise<ExamStudyPlan> {
  const { data, error, response } = await apiClient.GET('/exam/11408/subjects/{subject_key}/study-plan', {
    params: { path: { subject_key: moduleKey } },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function updateKnowledgeItem(input: ExamKnowledgeItemUpdate): Promise<ExamKnowledgeItemUpdateResponse> {
  const { data, error, response } = await apiClient.PATCH('/exam/11408/subjects/{subject_key}/study-plan/knowledge-items/{item_code}', {
    params: { path: { subject_key: input.subject_key, item_code: input.knowledge_point_code } },
    body: input,
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useExamStudyPlan(moduleKey: string) {
  return useQuery({ queryKey: examStudyPlanKey(moduleKey), queryFn: () => requestStudyPlan(moduleKey), retry: false });
}

export function useUpdateExamKnowledgeItem(moduleKey: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateKnowledgeItem,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: examStudyPlanKey(moduleKey) }),
        queryClient.invalidateQueries({ queryKey: examDashboardSummaryKey(moduleKey) }),
      ]);
    },
  });
}
