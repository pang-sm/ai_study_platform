import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type WrongAnswerStatusFilter = 'active' | 'resolved' | 'all';
export const wrongAnswersKey = (moduleKey: string | undefined, status: WrongAnswerStatusFilter, page: number) => ['exam', 'cs408', 'wrong-answers', moduleKey ?? 'all', status, page] as const;

async function requestWrongAnswers(input: { moduleKey?: string; status: WrongAnswerStatusFilter; page: number }) {
  const { data, error, response } = await apiClient.GET('/wrong-answers', { params: { query: { service_namespace: 'exam_prep', module: input.moduleKey, status: input.status === 'all' ? undefined : input.status, limit: 20, offset: input.page * 20 } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useWrongAnswers(moduleKey?: string, status: WrongAnswerStatusFilter = 'all', page = 0) {
  return useQuery({ queryKey: wrongAnswersKey(moduleKey, status, page), queryFn: () => requestWrongAnswers({ moduleKey, status, page }), retry: false });
}
