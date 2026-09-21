import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}
const programmingKeys = {
  home: ['programming', 'home'] as const,
  onboarding: ['programming', 'onboarding'] as const,
  exercises: (language: string) => ['programming', 'exercises', language] as const,
  exercise: (language: string, id: number) => ['programming', 'exercise', language, id] as const,
  records: ['programming', 'records'] as const,
  summary: ['programming', 'records-summary'] as const,
  state: ['programming', 'state'] as const,
  plan: (language: string) => ['programming', 'plan', language] as const,
};
export function useProgrammingHome() { return useQuery({ queryKey: programmingKeys.home, queryFn: async () => { const r = await apiClient.GET('/programming/home', {}); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
/**
 * The declared programming context: `main_language`, `selected_languages`,
 * `onboarding_completed`. This is what makes the programming space *configured* — a learner who
 * has declared a language has a context, whether or not the legacy account-level flag was set.
 */
export function useProgrammingOnboarding() { return useQuery({ queryKey: programmingKeys.onboarding, queryFn: async () => { const r = await apiClient.GET('/programming/onboarding', {}); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
export type ProgrammingOnboardingInput = components['schemas']['ProgrammingOnboardingRequest'];

/**
 * The write side of the programming context — the only one.
 *
 * `plan` is sent explicitly rather than omitted: with `onboarding_completed: true` the backend
 * takes the request's plan as the new one and activates it, so leaving it out would silently
 * move a paid learner back to `free`. The caller passes the plan the GET returned.
 */
export function useSaveProgrammingOnboarding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProgrammingOnboardingInput) => {
      const r = await apiClient.POST('/programming/onboarding', { body: input });
      return dataOrThrow(r.response, r.data, r.error);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: programmingKeys.onboarding });
      void client.invalidateQueries({ queryKey: programmingKeys.home });
      void client.invalidateQueries({ queryKey: ['auth', 'session'] });
    },
  });
}

export function useProgrammingExercises(language: string) { return useQuery({ queryKey: programmingKeys.exercises(language), queryFn: async () => { const r = await apiClient.GET('/programming/exercises', { params: { query: { language } } }); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
export function useProgrammingExercise(language: string, id: number) { return useQuery({ queryKey: programmingKeys.exercise(language, id), queryFn: async () => { const r = await apiClient.GET('/programming/exercises/{exercise_id}', { params: { path: { exercise_id: id } } }); return dataOrThrow(r.response, r.data, r.error); }, retry: false, enabled: Boolean(language) && Number.isFinite(id) }); }
export function useProgrammingRecords() { return useQuery({ queryKey: programmingKeys.records, queryFn: async () => { const r = await apiClient.GET('/programming/records', {}); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
export function useProgrammingRecordsSummary() { return useQuery({ queryKey: programmingKeys.summary, queryFn: async () => { const r = await apiClient.GET('/programming/records/summary', {}); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
export function useProgrammingState() { return useQuery({ queryKey: programmingKeys.state, queryFn: async () => { const r = await apiClient.GET('/programming/state', {}); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
export function useProgrammingPlan(language: string) { return useQuery({ queryKey: programmingKeys.plan(language), queryFn: async () => { const r = await apiClient.GET('/programming/plan', { params: { query: { language } } }); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }
export function useProgrammingAction(language: string, exerciseId: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: async ({ action, projectId, stdin = '' }: { action: 'start' | 'run' | 'test' | 'submit'; projectId?: number; stdin?: string }) => {
    if (action === 'start') { const r = await apiClient.POST('/programming/exercises/{exercise_id}/start', { params: { path: { exercise_id: exerciseId } }, body: { username: '' } }); return dataOrThrow(r.response, r.data, r.error); }
    const body = { username: '', project_id: projectId ?? 0, stdin };
    if (action === 'run') { const r = await apiClient.POST('/programming/exercises/{exercise_id}/run', { params: { path: { exercise_id: exerciseId } }, body }); return dataOrThrow(r.response, r.data, r.error); }
    if (action === 'test') { const r = await apiClient.POST('/programming/exercises/{exercise_id}/test', { params: { path: { exercise_id: exerciseId } }, body }); return dataOrThrow(r.response, r.data, r.error); }
    const r = await apiClient.POST('/programming/exercises/{exercise_id}/submit', { params: { path: { exercise_id: exerciseId } }, body }); return dataOrThrow(r.response, r.data, r.error);
  }, onSuccess: (_data, variables) => {
    void client.invalidateQueries({ queryKey: programmingKeys.exercise(language, exerciseId) });
    void client.invalidateQueries({ queryKey: programmingKeys.exercises(language) });
    if (variables.action === 'submit') {
      void client.invalidateQueries({ queryKey: programmingKeys.records });
      void client.invalidateQueries({ queryKey: programmingKeys.summary });
      void client.invalidateQueries({ queryKey: programmingKeys.state });
      void client.invalidateQueries({ queryKey: programmingKeys.plan(language) });
      void client.invalidateQueries({ queryKey: ['learning', 'agenda'] });
    }
  } });
}
/**
 * 代码诊断（静态语法检查）— deterministic, and deliberately NOT an AI capability.
 *
 * The backend runs a real compiler (`gcc -fsyntax-only` / `py_compile`) and returns its own
 * line and column. It creates no `ai_requests` row, returns no `request_id`, spends no AI 额度
 * and is subject to no capability or budget decision — so it must never be presented as AI, and
 * it keeps working when no model is available.
 */
export function useCodeDiagnose() {
  return useMutation({
    mutationFn: async ({ language, code }: { language: string; code: string }) => {
      const r = await apiClient.POST('/code/diagnose', { body: { language, code } });
      return dataOrThrow(r.response, r.data, r.error);
    },
  });
}

/**
 * AI Debug — the real AI capability (`programming.explain`), one call, one request_id that can be
 * rated. A non-empty `question` is required: the backend answers 400 without one, and an
 * "analysis" that names no problem would be the client inventing the prompt's content.
 */
export function useCodeAnalysis() {
  return useMutation({
    mutationFn: async ({
      language,
      code,
      question,
    }: {
      language: string;
      code: string;
      question: string;
    }) => {
      const r = await apiClient.POST('/code/analyze', {
        body: { username: '', course_id: '', language, code, question },
      });
      return dataOrThrow(r.response, r.data, r.error);
    },
  });
}
