import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type MathTaxonomy = components['schemas']['MathTaxonomyResponse'];

export const mathTaxonomyKey = ['exam', 'math-taxonomy'] as const;

async function requestMathTaxonomy(): Promise<MathTaxonomy> {
  const { data, error, response } = await apiClient.GET('/exam/prep/math/taxonomy');
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

/**
 * The maths taxonomy, which the BACKEND owns.
 *
 * The domains, the papers and whatever is known about each paper's exam range all come from here;
 * the frontend keeps no copy of them, so there is one statement of what maths is (P3B moved this
 * out of a frontend config constant). It is versioned config that is identical for every learner,
 * so it is cached for a while rather than refetched per navigation.
 */
export function useMathTaxonomy() {
  return useQuery({
    queryKey: mathTaxonomyKey,
    queryFn: requestMathTaxonomy,
    staleTime: 5 * 60_000,
    retry: 1,
  });
}
