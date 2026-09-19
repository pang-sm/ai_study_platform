import { useMutation } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type QuestionExplainInput = components['schemas']['ExamQuestionAnalysisRequest'];

async function requestQuestionExplain({ moduleKey, input }: { moduleKey: string; input: QuestionExplainInput }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/question-analysis', {
    params: { path: { subject_key: moduleKey } },
    body: input,
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useQuestionExplain() {
  return useMutation({ mutationFn: requestQuestionExplain, retry: false });
}
