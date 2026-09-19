import { useInfiniteQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ExamRecordPage = components['schemas']['RecordPage'];

export const cs408RecordsKey = (moduleKey?: string) => ['exam', 'cs408', 'records', moduleKey ?? 'all'] as const;

async function requestRecords(moduleKey: string | undefined, cursor: string | undefined): Promise<ExamRecordPage> {
  const { data, error, response } = await apiClient.GET('/exam/prep/records', {
    params: { query: { exam_module_id: moduleKey, cursor, limit: 30 } },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useCs408LearningRecords(moduleKey?: string) {
  return useInfiniteQuery({
    queryKey: cs408RecordsKey(moduleKey),
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => requestRecords(moduleKey, pageParam),
    getNextPageParam: (page) => page.has_more ? page.next_cursor ?? undefined : undefined,
    retry: false,
  });
}
