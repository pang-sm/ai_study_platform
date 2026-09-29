import { useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ReviewSummary = components['schemas']['ReviewSummaryResponse'];

/** The ONE summary the 学习状态 page reads. Scoped to exam prep, never to the whole account. */
export const examReviewSummaryKey = ['exam', 'cs408', 'review-summary'] as const;

async function requestReviewSummary(): Promise<ReviewSummary> {
  const { data, error, response } = await apiClient.GET('/review/summary', {
    params: { query: { service_namespace: 'exam_prep' } },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

/**
 * How much review is waiting. A 403 means this learner's tier does not include the review
 * capability — the caller omits the row rather than showing an error, because "you have no
 * review list" and "review is not in your tier" are different facts and neither is a failure
 * of the page.
 */
export function useExamReviewSummary(enabled = true) {
  return useQuery({ queryKey: examReviewSummaryKey, queryFn: requestReviewSummary, retry: false, enabled });
}
