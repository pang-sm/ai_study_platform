import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

export type LearningRecord = components['schemas']['RecordView'];

export const learningRecordKeys = {
  recent: (limit: number, namespace: string) =>
    ['learning-records', 'recent', namespace || 'all', limit] as const,
};

/**
 * The canonical study-history stream (STEP 7F). Server-side scoping already excludes audit-only
 * facts such as `ai_called`, so nothing here is filtered out in the browser — the list a
 * learner sees is the list the backend decided they may see.
 */
export async function fetchRecentRecords(
  limit: number,
  serviceNamespace: string,
): Promise<LearningRecord[]> {
  const { data, error, response } = await apiClient.GET('/learning-records', {
    params: {
      query: {
        limit,
        service_namespace: serviceNamespace || undefined,
      },
    },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data.records;
}

export function useRecentRecords(limit = 8, serviceNamespace = '') {
  return useQuery({
    queryKey: learningRecordKeys.recent(limit, serviceNamespace),
    queryFn: () => fetchRecentRecords(limit, serviceNamespace),
    retry: false,
  });
}
