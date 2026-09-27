import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

export const agendaKey = ['learning', 'agenda'] as const;

function requireData<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

/**
 * The learner's next actions, ranked. This is the ONE read the home page's decision and its list
 * both come from: they are two views of one ranking, so a second request for the same ranking
 * could only ever disagree with the first.
 *
 * The explain endpoint is deliberately not read here. Its `priority_rules` text is written for an
 * engineer and names payload fields (`wrong_count >= 2`), and the ranking is already restated in
 * the learner's words from the facts carried by each item.
 */
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
