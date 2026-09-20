import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ChapterPracticeOutline = components['schemas']['ExamChapterPracticeOutlineResponse'];
export type ChapterPracticeQuestions = components['schemas']['ExamChapterPracticeQuestionsResponse'];
export type ChapterPracticeSubmit = components['schemas']['ExamPracticeSubmitResponse'];

// The API mints a SYNTHETIC code (`_leaf:<path>`) for a knowledge node the module seed gives
// no code. Such a node has no canonical identity, so there is nothing to propagate from it and
// no practice link should be offered. Everything else the tree publishes is a real seed code.
//
// This is not an identity check the frontend performs on its own: the SERVER still validates
// every concept it receives and refuses anything that is not a canonical leaf of the module.
// The helper only decides whether to offer the action at all, so a learner never gets an
// error page for an entry point that could never have worked.
const SYNTHETIC_NODE_CODE_PREFIXES = ['_leaf:', 'leaf:', '_node:', 'node:', '_kp:', 'kp:'] as const;

export function isCanonicalConceptCode(code?: string | null): boolean {
  const value = (code ?? '').trim();
  return value !== '' && !SYNTHETIC_NODE_CODE_PREFIXES.some((prefix) => value.startsWith(prefix));
}

export const chapterPracticeOutlineKey = (moduleKey: string) => ['exam', 'cs408', 'chapter-practice', 'outline', moduleKey] as const;
export const chapterPracticeQuestionsKey = (moduleKey: string, chapterCode: string, conceptCode?: string) => ['exam', 'cs408', 'chapter-practice', 'questions', moduleKey, chapterCode, conceptCode ?? null] as const;
export const chapterPracticeAttemptKey = (moduleKey: string, attemptId: number) => ['exam', 'cs408', 'chapter-practice', 'attempt', moduleKey, attemptId] as const;

async function requestOutline(moduleKey: string): Promise<ChapterPracticeOutline> {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/outline', { params: { path: { subject_key: moduleKey } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

// `conceptCode` is the canonical knowledge leaf the learner came FROM. It is only ever set
// by a surface that already holds it as a canonical id — the knowledge tree's own `code` —
// and it is never derived from a title, a path, a list position or the question text. The
// server refuses any value that is not a canonical leaf of the module (422), so a wrong id
// fails loudly instead of quietly labelling the attempt with a concept it does not have.
//
// The read uses `concept_code` (canonical filter, distinct from the legacy practice
// sub-group filter) while the write uses `knowledge_point_id` (the concept slot the attempt
// and its learning event actually store). One mapping, stated here, so no call site repeats it.
async function requestQuestions(moduleKey: string, chapterCode: string, conceptCode?: string): Promise<ChapterPracticeQuestions> {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/questions', { params: { path: { subject_key: moduleKey }, query: { chapter_code: chapterCode, concept_code: conceptCode } } });
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

async function createAttempt(input: { moduleKey: string; questionIds: number[]; knowledgePointId?: string }) {
  const { data, error, response } = await apiClient.POST('/exam/11408/{subject_key}/chapter-practice/attempts', { params: { path: { subject_key: input.moduleKey } }, body: { question_ids: input.questionIds, knowledge_point_id: input.knowledgePointId } });
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

export function useChapterPracticeQuestions(moduleKey: string, chapterCode: string, conceptCode?: string) {
  return useQuery({ queryKey: chapterPracticeQuestionsKey(moduleKey, chapterCode, conceptCode), queryFn: () => requestQuestions(moduleKey, chapterCode, conceptCode), enabled: Boolean(moduleKey && chapterCode), retry: false });
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
