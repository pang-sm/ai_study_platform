import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}
const programmingKeys = {
  onboarding: ['programming', 'onboarding'] as const,
  exercises: (language: string) => ['programming', 'exercises', language] as const,
  exercise: (language: string, id: number) => ['programming', 'exercise', language, id] as const,
  /** The learner's own project for one exercise: its files, and the code they last left there. */
  workspace: (language: string, id: number) => ['programming', 'workspace', language, id] as const,
  records: ['programming', 'records'] as const,
  plan: (language: string) => ['programming', 'plan', language] as const,
};

/* ------------------------------------------------------------------ declared context */

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
      void client.invalidateQueries({ queryKey: ['auth', 'session'] });
    },
  });
}

/* ------------------------------------------------------------------ the bank */

export type BankExercise = Record<string, unknown>;

/** The bank's own page ceiling (`page_size` is clamped to 12..48 server-side). */
const BANK_PAGE_SIZE = 48;

export type ExerciseBank = {
  items: BankExercise[];
  /** The bank's real size, which is what a learner is told — never the page's own count. */
  total: number;
  /** Product status counts as the backend computed them: needs_improvement / not_started / passed. */
  statusCounts: Record<string, number>;
};

function bankItems(data: unknown): BankExercise[] {
  if (!data || typeof data !== 'object') return [];
  const record = data as Record<string, unknown>;
  const list = Array.isArray(record.exercises) ? record.exercises : Array.isArray(record.items) ? record.items : [];
  return list.filter((item): item is BankExercise => typeof item === 'object' && item !== null);
}

export function exerciseTotal(data: unknown): number | undefined {
  if (typeof data !== 'object' || data === null) return undefined;
  const total = (data as Record<string, unknown>).total;
  return typeof total === 'number' && Number.isFinite(total) ? total : undefined;
}

export function exerciseTotalPages(data: unknown): number | undefined {
  if (typeof data !== 'object' || data === null) return undefined;
  const pages = (data as Record<string, unknown>).total_pages;
  return typeof pages === 'number' && Number.isFinite(pages) ? pages : undefined;
}

export function statusCountsOf(data: unknown): Record<string, number> {
  if (typeof data !== 'object' || data === null) return {};
  const counts = (data as Record<string, unknown>).status_counts;
  if (typeof counts !== 'object' || counts === null) return {};
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(counts as Record<string, unknown>)) {
    if (typeof value === 'number' && Number.isFinite(value)) out[key] = value;
  }
  return out;
}

/**
 * A language's WHOLE bank, in the bank's own order.
 *
 * The endpoint caps `page_size` at 48 while a language holds 120 exercises, so one page would
 * silently be a third of the题目 — and the left rail is the learner's map of what there is to do:
 * a map that hides two thirds of itself is worse than no map. The remaining pages are fetched
 * together, so the rail's cost is one round trip plus one parallel batch.
 */
export function useProgrammingExerciseBank(language: string) {
  return useQuery({
    queryKey: [...programmingKeys.exercises(language), 'bank'],
    enabled: Boolean(language),
    retry: false,
    queryFn: async (): Promise<ExerciseBank> => {
      const first = await apiClient.GET('/programming/exercises', {
        params: { query: { language, page: 1, page_size: BANK_PAGE_SIZE } },
      });
      const data = dataOrThrow(first.response, first.data, first.error);
      const items = bankItems(data);
      const totalPages = exerciseTotalPages(data) ?? 1;
      if (totalPages > 1) {
        const rest = await Promise.all(
          Array.from({ length: totalPages - 1 }, (_, index) =>
            apiClient.GET('/programming/exercises', {
              params: { query: { language, page: index + 2, page_size: BANK_PAGE_SIZE } },
            }),
          ),
        );
        for (const page of rest) items.push(...bankItems(dataOrThrow(page.response, page.data, page.error)));
      }
      return { items, total: exerciseTotal(data) ?? items.length, statusCounts: statusCountsOf(data) };
    },
  });
}

/* ------------------------------------------------------------------ one exercise's题面 */

export function useProgrammingExercise(language: string, id: number) {
  return useQuery({ queryKey: programmingKeys.exercise(language, id), queryFn: async () => { const r = await apiClient.GET('/programming/exercises/{exercise_id}', { params: { path: { exercise_id: id } } }); return dataOrThrow(r.response, r.data, r.error); }, retry: false, enabled: Boolean(language) && Number.isFinite(id) });
}

/* ------------------------------------------------------------------ the open project */

export type ProjectFile = { id: number; relative_path: string; filename: string; content: string; file_type?: string };
export type ExerciseWorkspace = {
  project: { id: number; entry_file: string; main_class?: string | null; language: string; files: ProjectFile[] };
  /** The exercise's own starter files, as the backend stores them — what 重置代码 restores. */
  starterFiles: Array<{ path: string; content: string }>;
  /** True when the backend found the learner's existing draft instead of creating a new project. */
  resumed: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readProjectFiles(value: unknown): ProjectFile[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry): ProjectFile[] => {
    if (!isRecord(entry) || typeof entry.id !== 'number') return [];
    return [{
      id: entry.id,
      relative_path: String(entry.relative_path ?? ''),
      filename: String(entry.filename ?? ''),
      content: typeof entry.content === 'string' ? entry.content : '',
      file_type: typeof entry.file_type === 'string' ? entry.file_type : undefined,
    }];
  });
}

/**
 * Opening an exercise for work: 开始练习, which is also 继续练习.
 *
 * `POST /programming/exercises/{id}/start` is the endpoint that establishes the exercise's
 * context — it creates the learner's project on first open and returns the existing one on every
 * open after that, with the files as the learner left them. That makes it BOTH reads at once: the
 * starter code for a new exercise, and the learner's own draft for a resumed one. Nothing is
 * invented for a file the server did not send; an exercise with no stored source simply opens
 * with an empty buffer.
 *
 * It is a query rather than a mutation because it is what opening a题目 means, and the key is
 * per (language, exercise), so switching题目 loads that题's own project and nothing refetches on
 * focus. It is never invalidated on run/test — a run must not re-open the exercise and overwrite
 * the buffer with the stored file.
 */
export function useExerciseWorkspace(language: string, exerciseId: number | undefined) {
  return useQuery({
    queryKey: programmingKeys.workspace(language, exerciseId ?? 0),
    enabled: Boolean(language) && typeof exerciseId === 'number' && Number.isFinite(exerciseId),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: Infinity,
    queryFn: async (): Promise<ExerciseWorkspace> => {
      const r = await apiClient.POST('/programming/exercises/{exercise_id}/start', {
        params: { path: { exercise_id: exerciseId as number } },
        body: { username: '' },
      });
      const data = dataOrThrow(r.response, r.data, r.error);
      const root = isRecord(data) ? data : {};
      const project = isRecord(root.project) ? root.project : {};
      const exercise = isRecord(root.exercise) ? root.exercise : {};
      const starter = Array.isArray(exercise.starter_files) ? exercise.starter_files : [];
      return {
        project: {
          id: typeof project.id === 'number' ? project.id : 0,
          entry_file: String(project.entry_file ?? ''),
          main_class: typeof project.main_class === 'string' ? project.main_class : null,
          language: String(project.language ?? ''),
          files: readProjectFiles(project.files),
        },
        starterFiles: starter.flatMap((entry) =>
          isRecord(entry) && typeof entry.path === 'string'
            ? [{ path: entry.path, content: typeof entry.content === 'string' ? entry.content : '' }]
            : [],
        ),
        resumed: root.resumed === true,
      };
    },
  });
}

/* ------------------------------------------------------------------ run / test / submit */

export type JudgeAction = 'run' | 'test' | 'submit';

export type JudgeRequest = {
  action: JudgeAction;
  /** The open project. The judge executes the STORED project, so the buffer is saved first. */
  projectId: number;
  entryFileId: number | undefined;
  code: string;
  stdin: string;
  entryFile: string;
  mainClass: string | null;
  /** The visible sample ids, which `test` requires — the endpoint 400s without at least one. */
  publicCaseIds: string[];
};

/**
 * One learner action against the real judge.
 *
 * Two calls, in this order, and the order is the point: the endpoint set that runs, tests and
 * submits a programming exercise executes the learner's PROJECT FILES — it takes no code in its
 * body. So the editor's buffer is written to the project first, and only then is the action asked
 * for. Without the save, 运行 would execute whatever the project last held rather than what is on
 * screen, and the answer the learner reads would not be about their code.
 *
 * `test` additionally requires the ids of the visible samples it should run; the caller passes
 * them because they belong to the题面, not to this request shape.
 */
export function useProgrammingJudge(language: string, exerciseId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: JudgeRequest) => {
      if (input.entryFileId !== undefined) {
        const saved = await apiClient.PUT('/code/projects/{project_id}/files/{file_id}', {
          params: { path: { project_id: input.projectId, file_id: input.entryFileId } },
          body: { username: '', content: input.code },
        });
        if (!saved.response.ok) throw new ApiRequestError(saved.response.status, saved.error);
      }
      const path = { exercise_id: exerciseId };
      const body = {
        username: '',
        project_id: input.projectId,
        stdin: input.stdin,
        entry_file: input.entryFile,
        main_class: input.mainClass,
        public_case_ids: input.action === 'test' ? input.publicCaseIds : null,
      };
      const response = input.action === 'run'
        ? await apiClient.POST('/programming/exercises/{exercise_id}/run', { params: { path }, body })
        : input.action === 'test'
          ? await apiClient.POST('/programming/exercises/{exercise_id}/test', { params: { path }, body })
          : await apiClient.POST('/programming/exercises/{exercise_id}/submit', { params: { path }, body });
      return dataOrThrow(response.response, response.data, response.error) as Record<string, unknown>;
    },
    onSuccess: (_data, variables) => {
      // The bank carries each题's status, so a run/test/submit can change the left rail's marks.
      // The workspace (the open project) is deliberately NOT invalidated: it is the buffer's
      // source, and refetching it would replace what the learner is typing with the stored file.
      void client.invalidateQueries({ queryKey: programmingKeys.exercises(language) });
      void client.invalidateQueries({ queryKey: programmingKeys.exercise(language, exerciseId) });
      if (variables.action === 'submit') {
        void client.invalidateQueries({ queryKey: programmingKeys.records });
        void client.invalidateQueries({ queryKey: programmingKeys.plan(language) });
        void client.invalidateQueries({ queryKey: ['learning', 'agenda'] });
      }
    },
  });
}

/* ------------------------------------------------------------------ records */

/**
 * The learner's own programming study timeline, newest first — the space's own facts.
 *
 * `eventType` filters in SQL before pagination, which is what lets 提交记录 ask for the graded
 * facts alone instead of paging a whole mixed timeline to find them.
 */
export function useProgrammingRecords(limit = 200, eventType = '') {
  return useQuery({
    queryKey: [...programmingKeys.records, limit, eventType],
    queryFn: async () => {
      const r = await apiClient.GET('/programming/records', {
        params: { query: { limit, event_type: eventType } },
      });
      return dataOrThrow(r.response, r.data, r.error);
    },
    retry: false,
  });
}

export function useProgrammingPlan(language: string) { return useQuery({ queryKey: programmingKeys.plan(language), queryFn: async () => { const r = await apiClient.GET('/programming/plan', { params: { query: { language } } }); return dataOrThrow(r.response, r.data, r.error); }, retry: false }); }

/* ------------------------------------------------------------------ the coach */

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

export type CoachTurn = { role: 'user' | 'assistant'; content: string };

export type CoachAsk = {
  language: string;
  code: string;
  question: string;
  /** The open题目, which the backend loads by id and describes to the model itself. */
  exerciseId?: number;
  /** The last run's own output, in the shape the endpoint reads (`stdout`/`stderr`/`exit_code`…). */
  lastRun?: Record<string, unknown>;
  /** The last test's cases, reshaped to the `{total, passed, results}` this endpoint reads. */
  lastTest?: Record<string, unknown>;
  /** The editor's own compiler verdict, when one was asked for. */
  diagnostics?: Record<string, unknown>;
  /** The turns already exchanged in this exercise, so the coach answers in context. */
  history?: CoachTurn[];
};

/**
 * AI 教练 — the real `programming.explain` capability, asked with the work in front of the learner.
 *
 * The endpoint takes the context as FIELDS rather than as a paragraph the client composes: the
 * exercise id (the backend loads the题面 and its knowledge points itself), the code, the last run,
 * the last test's cases, the compiler diagnostics, and the turns so far. That is why the coach
 * answers about THIS failure instead of a generic one — and why nothing here fabricates history,
 * usage or a verdict. `request_id` comes back with the answer and is what the learner rates.
 */
export function useCodeCoach() {
  return useMutation({
    mutationFn: async ({ language, code, question, exerciseId, lastRun, lastTest, diagnostics, history }: CoachAsk) => {
      const r = await apiClient.POST('/code/analyze', {
        body: {
          username: '',
          course_id: '',
          language,
          code,
          question,
          exercise_id: exerciseId ?? null,
          last_run_result: lastRun ?? null,
          last_test_results: lastTest ?? null,
          diagnostics: diagnostics ?? null,
          chat_history: history ?? null,
        },
      });
      return dataOrThrow(r.response, r.data, r.error) as Record<string, unknown>;
    },
  });
}
