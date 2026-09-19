import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type StudentTwinPreview = components['schemas']['StudentTwinPreviewResponse'];

export const studentTwinPreviewKey = (moduleKey?: string) => ['exam', 'cs408', 'student-twin-preview', moduleKey ?? 'all'] as const;

async function requestStudentTwinPreview(moduleKey?: string): Promise<StudentTwinPreview> {
  const { data, error, response } = await apiClient.GET('/exam/prep/scientific/student-twin', {
    params: { query: { exam_module_id: moduleKey } },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useStudentTwinPreview(moduleKey?: string) {
  return useQuery({ queryKey: studentTwinPreviewKey(moduleKey), queryFn: () => requestStudentTwinPreview(moduleKey), retry: false });
}
