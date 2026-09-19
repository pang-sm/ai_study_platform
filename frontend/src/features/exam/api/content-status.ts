import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';

export class ApiRequestError extends Error {
  constructor(readonly status: number, readonly detail: unknown) {
    super(`Request failed with status ${status}`);
  }
}

export async function getExamSubjectContentStatus(subjectId: string): Promise<components['schemas']['ExamContentStatusResponse']> {
  const { data, error, response } = await apiClient.GET('/exam/prep/subjects/{subject_id}/content-status', {
    params: { path: { subject_id: subjectId } },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useExamSubjectContentStatus(subjectId: string) {
  return useQuery({
    queryKey: ['exam', 'subject-content-status', subjectId],
    queryFn: () => getExamSubjectContentStatus(subjectId),
    retry: (failureCount, error) => !(error instanceof ApiRequestError) && failureCount < 1,
  });
}
