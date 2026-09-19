import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ChapterPracticeOutline = components['schemas']['ExamChapterPracticeOutlineResponse'];
export type ChapterPracticeQuestions = components['schemas']['ExamChapterPracticeQuestionsResponse'];
export type ChapterPracticeSubmit = components['schemas']['ExamPracticeSubmitResponse'];

export const chapterPracticeOutlineKey = (moduleKey: string) => ['exam', 'cs408', 'chapter-practice', 'outline', moduleKey] as const;
export const chapterPracticeQuestionsKey = (moduleKey: string, chapterCode: string) => ['exam', 'cs408', 'chapter-practice', 'questions', moduleKey, chapterCode] as const;
export const chapterPracticeAttemptKey = (moduleKey: string, attemptId: number) => ['exam', 'cs408', 'chapter-practice', 'attempt', moduleKey, attemptId] as const;

async function requestOutline(moduleKey: string): Promise<ChapterPracticeOutline> {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/outline', { params: { path: { subject_key: moduleKey } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function requestQuestions(moduleKey: string, chapterCode: string): Promise<ChapterPracticeQuestions> {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/questions', { params: { path: { subject_key: moduleKey }, query: { chapter_code: chapterCode } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function requestAttempt(moduleKey: string, attemptId: number) {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}', { params: { path: { subject_key: moduleKey, attempt_id: attemptId } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

// The attempt detail as the typed client delivers it, derived rather than annotated so it stays
// generated-only — no handwritten transport DTO, no cast. The single difference from
// `components['schemas']['ExamPracticeAttemptDetailResponse']` is that openapi-typescript-helpers'
// `Readable` mapping drops `null`-only properties from read responses, and the only such property
// here is `correct` on a big question: always `null`, and never read, because a big question is
// identified by `question_type` and carried by `judge: 'self_review'`.
export type ChapterPracticeAttempt = Awaited<ReturnType<typeof requestAttempt>>;

async function createAttempt(input: { moduleKey: string; questionIds: number[] }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/chapter-practice/attempts', { params: { path: { subject_key: input.moduleKey } }, body: { question_ids: input.questionIds } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function saveAnswers(input: { moduleKey: string; attemptId: number; answers: Record<string, string> }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/answers', { params: { path: { subject_key: input.moduleKey, attempt_id: input.attemptId } }, body: { answers: input.answers } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function submitAttempt(input: { moduleKey: string; attemptId: number; answers: Record<string, string> }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/submit', { params: { path: { subject_key: input.moduleKey, attempt_id: input.attemptId } }, body: { answers: input.answers } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useChapterPracticeOutline(moduleKey: string) {
  return useQuery({ queryKey: chapterPracticeOutlineKey(moduleKey), queryFn: () => requestOutline(moduleKey), enabled: Boolean(moduleKey), retry: false });
}

export function useChapterPracticeQuestions(moduleKey: string, chapterCode: string) {
  return useQuery({ queryKey: chapterPracticeQuestionsKey(moduleKey, chapterCode), queryFn: () => requestQuestions(moduleKey, chapterCode), enabled: Boolean(moduleKey && chapterCode), retry: false });
}

export function useChapterPracticeAttempt(moduleKey: string, attemptId?: number) {
  return useQuery({ queryKey: chapterPracticeAttemptKey(moduleKey, attemptId ?? 0), queryFn: () => requestAttempt(moduleKey, attemptId!), enabled: attemptId !== undefined, retry: false });
}

export function useCreateChapterPracticeAttempt() {
  const client = useQueryClient();
  return useMutation({ mutationFn: createAttempt, onSuccess: async (attempt, input) => { await client.invalidateQueries({ queryKey: chapterPracticeAttemptKey(input.moduleKey, attempt.attempt_id) }); } });
}

export function useSaveChapterPracticeAnswers() {
  const client = useQueryClient();
  return useMutation({ mutationFn: saveAnswers, onSuccess: async (_result, input) => { await client.invalidateQueries({ queryKey: chapterPracticeAttemptKey(input.moduleKey, input.attemptId) }); } });
}

export function useSubmitChapterPractice() {
  const client = useQueryClient();
  return useMutation({ mutationFn: submitAttempt, onSuccess: async (_result, input) => { await client.invalidateQueries({ queryKey: chapterPracticeAttemptKey(input.moduleKey, input.attemptId) }); } });
}
