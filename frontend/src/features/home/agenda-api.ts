import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

export const agendaKey = ['learning', 'agenda'] as const;
export const agendaExplainKey = ['learning', 'agenda', 'explain'] as const;

function requireData<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useDailyAgenda() {
  return useQuery({
    queryKey: agendaKey,
    queryFn: async (): Promise<components['schemas']['AgendaResponse']> => {
      const result = await apiClient.GET('/learning/agenda', { params: { query: { limit: 12 } } });
      return requireData(result.response, result.data, result.error);
    },
    retry: false,
  });
}

/** The contract is intentionally open-ended, so UI only reads public explanation fields. */
export function useAgendaExplain() {
  return useQuery({
    queryKey: agendaExplainKey,
    queryFn: async (): Promise<Record<string, unknown>> => {
      const result = await apiClient.GET('/learning/agenda/explain', { params: { query: { limit: 12 } } });
      return requireData(result.response, result.data, result.error);
    },
    retry: false,
  });
}
