import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ExamCatalog = components['schemas']['ExamPrepCatalogResponse'];
export const examCatalogKey = ['exam', 'catalog'] as const;

async function requestCatalog(): Promise<ExamCatalog> {
  const { data, error, response } = await apiClient.GET('/exam/prep/catalog');
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useExamCatalog() {
  return useQuery({ queryKey: examCatalogKey, queryFn: requestCatalog, staleTime: 5 * 60_000, retry: 1 });
}
