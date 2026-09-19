import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export const pastPaperIndexKey = (moduleKey: string) => ['exam', 'cs408', 'past-papers', 'index', moduleKey] as const;
export const pastPaperQuestionsKey = (moduleKey: string, year: number) => ['exam', 'cs408', 'past-papers', 'questions', moduleKey, year] as const;
export const pastPaperAttemptKey = (moduleKey: string, attemptId: number) => ['exam', 'cs408', 'past-papers', 'attempt', moduleKey, attemptId] as const;

async function requestIndex(moduleKey: string) {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/past-papers', { params: { path: { subject_key: moduleKey } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function requestQuestions(moduleKey: string, year: number) {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/past-paper-questions', { params: { path: { subject_key: moduleKey }, query: { year } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function requestAttempt(moduleKey: string, attemptId: number) {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}', { params: { path: { subject_key: moduleKey, attempt_id: attemptId } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function createAttempt(input: { moduleKey: string; year: number }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/past-paper-attempts', { params: { path: { subject_key: input.moduleKey } }, body: { year: input.year } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function saveAnswers(input: { moduleKey: string; attemptId: number; answers: Record<string, string> }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers', { params: { path: { subject_key: input.moduleKey, attempt_id: input.attemptId } }, body: { answers: input.answers } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function submitAttempt(input: { moduleKey: string; attemptId: number; answers: Record<string, string> }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit', { params: { path: { subject_key: input.moduleKey, attempt_id: input.attemptId } }, body: { answers: input.answers } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function usePastPaperIndex(moduleKey: string) { return useQuery({ queryKey: pastPaperIndexKey(moduleKey), queryFn: () => requestIndex(moduleKey), enabled: Boolean(moduleKey), retry: false }); }
export function usePastPaperQuestions(moduleKey: string, year?: number) { return useQuery({ queryKey: pastPaperQuestionsKey(moduleKey, year ?? 0), queryFn: () => requestQuestions(moduleKey, year!), enabled: Boolean(moduleKey && year), retry: false }); }
export function usePastPaperAttempt(moduleKey: string, attemptId?: number) { return useQuery({ queryKey: pastPaperAttemptKey(moduleKey, attemptId ?? 0), queryFn: () => requestAttempt(moduleKey, attemptId!), enabled: attemptId !== undefined, retry: false }); }
export function useCreatePastPaperAttempt() { const client = useQueryClient(); return useMutation({ mutationFn: createAttempt, onSuccess: async (attempt, input) => { await client.invalidateQueries({ queryKey: pastPaperAttemptKey(input.moduleKey, attempt.attempt_id) }); } }); }
export function useSavePastPaperAnswers() { const client = useQueryClient(); return useMutation({ mutationFn: saveAnswers, onSuccess: async (_saved, input) => { await client.invalidateQueries({ queryKey: pastPaperAttemptKey(input.moduleKey, input.attemptId) }); } }); }
export function useSubmitPastPaper() { const client = useQueryClient(); return useMutation({ mutationFn: submitAttempt, onSuccess: async (_submitted, input) => { await client.invalidateQueries({ queryKey: pastPaperAttemptKey(input.moduleKey, input.attemptId) }); } }); }
