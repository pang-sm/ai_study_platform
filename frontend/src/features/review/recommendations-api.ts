import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';
import type { components } from '@/types/api';

export type ReviewRecommendation = components['schemas']['ReviewRecommendationView'];
export type ReviewRecommendationList = components['schemas']['ReviewRecommendationListResponse'];

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useReviewRecommendations(serviceNamespace?: string) {
  return useQuery({
    queryKey: ['review', 'recommendations', serviceNamespace ?? 'all'],
    queryFn: async (): Promise<ReviewRecommendationList> => {
      const result = await apiClient.GET('/review/recommendations', {
        params: { query: { service_namespace: serviceNamespace, limit: 200, offset: 0 } },
      });
      return dataOrThrow(result.response, result.data, result.error);
    },
    retry: false,
  });
}

export function useSnoozeReviewRecommendation() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (recommendationKey: string) => {
      const result = await apiClient.POST('/review/recommendations/{recommendation_key}/snooze', {
        params: { path: { recommendation_key: recommendationKey } },
      });
      return dataOrThrow(result.response, result.data, result.error);
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ['review', 'recommendations'] }),
  });
}
