import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export type AdaptiveScope = { serviceKey: 'course_learning' | 'exam_11408' | 'programming'; courseId?: string; examModuleId?: string; language?: string };
export const adaptiveKey = (scope: AdaptiveScope) => ['adaptive-practice', scope.serviceKey, scope.courseId ?? '', scope.examModuleId ?? '', scope.language ?? ''] as const;

export function useAdaptivePractice(scope: AdaptiveScope) {
  return useQuery({ queryKey: adaptiveKey(scope), queryFn: async (): Promise<components['schemas']['AdaptivePracticeResponse']> => {
    const result = await apiClient.GET('/adaptive/practice', { params: { query: { service_key: scope.serviceKey, course_id: scope.courseId, exam_module_id: scope.examModuleId, language: scope.language, limit: 6 } } });
    return dataOrThrow(result.response, result.data, result.error);
  }, retry: false });
}

export function useAiFeedback() {
  return useMutation({ mutationFn: async (body: components['schemas']['AIFeedbackRequest']) => {
    const result = await apiClient.POST('/ai/feedback', { body });
    return dataOrThrow(result.response, result.data, result.error);
  } });
}

export function useScheduleReviews() {
  const client = useQueryClient();
  return useMutation({ mutationFn: async (body: components['schemas']['ReviewScheduleRequest']) => {
    const result = await apiClient.POST('/review/schedule', { body });
    return dataOrThrow(result.response, result.data, result.error);
  }, onSuccess: () => { void client.invalidateQueries({ queryKey: ['review'] }); } });
}

export function useCompleteReview() {
  const client = useQueryClient();
  return useMutation({ mutationFn: async ({ itemId, result }: { itemId: string; result: 'correct' | 'incorrect' }) => {
    const response = await apiClient.POST('/review/{item_id}/complete', { params: { path: { item_id: itemId } }, body: { result } });
    return dataOrThrow(response.response, response.data, response.error);
  }, onSuccess: (_data, value) => {
    void client.invalidateQueries({ queryKey: ['learning', 'agenda'] });
    void client.invalidateQueries({ queryKey: ['review'] });
    void client.invalidateQueries({ queryKey: ['adaptive-practice'] });
    void client.invalidateQueries({ queryKey: ['home', 'summary'] });
    if (value.itemId.includes('course')) void client.invalidateQueries({ queryKey: ['course'] });
    if (value.itemId.includes('exam')) void client.invalidateQueries({ queryKey: ['exam'] });
    if (value.itemId.includes('programming')) void client.invalidateQueries({ queryKey: ['programming'] });
  } });
}
