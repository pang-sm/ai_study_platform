import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { deepStudyKey, toDeepStudyPayload, type AgentDebugView, type DeepStudyInput, type DeepStudyView } from '../workflow-adapters';
import type { components } from '@/types/api';

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useDeepStudy(input?: DeepStudyInput) {
  return useMutation({
    mutationKey: input ? deepStudyKey(input) : ['deep-study'],
    mutationFn: async (value: DeepStudyInput): Promise<DeepStudyView> => {
      const result = await apiClient.POST('/ai/deep-study', { body: toDeepStudyPayload(value) });
      return dataOrThrow(result.response, result.data, result.error);
    },
  });
}

export function useDebugAgent() {
  return useMutation({
    mutationFn: async (payload: components['schemas']['AgentDebugRequest']): Promise<AgentDebugView> => {
      const result = await apiClient.POST('/programming/agent/debug', { body: payload });
      return dataOrThrow(result.response, result.data, result.error);
    },
  });
}

export function useReview(serviceNamespace?: string) {
  return useQuery({ queryKey: ['review', serviceNamespace ?? 'all'], queryFn: async () => {
    const result = await apiClient.GET('/review', { params: { query: { service_namespace: serviceNamespace, limit: 100, offset: 0 } } });
    return dataOrThrow(result.response, result.data, result.error);
  }, retry: false });
}

export function useReviewSummary() {
  return useQuery({ queryKey: ['review', 'summary'], queryFn: async () => {
    const result = await apiClient.GET('/review/summary', {});
    return dataOrThrow(result.response, result.data, result.error);
  }, retry: false });
}
