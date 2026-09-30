import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

function dataOrThrow<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

/* ---------------------------------------------------------------- learning context

   The one thing the learner chooses before asking. It is not a UI concept: each option maps to
   the backend's own canonical scope, which is what tells the AI layer WHICH subject it is being
   asked about — and what files the answer under the right space in the usage ledger.

   `service_key` is the backend's `service_namespace` (`course_learning` / `exam_11408` /
   `programming`), not a display name. Nothing here is invented client-side. */

export type AiScope =
  | { kind: 'general' }
  | {
      kind: 'exam';
      moduleKey: string;
      label: string;
      /**
       * The canonical knowledge point this conversation is about, when the learner entered the
       * assistant from that node on the knowledge outline. Absent for every other entry point,
       * and cleared the moment the paper above changes: a data-structure node has no meaning
       * inside 操作系统.
       *
       * It is an IDENTITY (`1.1.1.1`, `3.6` — the id the learner's own knowledge map publishes),
       * not a question. The turn carries it, the model is told which point the learner is
       * asking from, and nothing is sent on the learner's behalf.
       */
      knowledgePoint?: string;
      /**
       * How that point is named — the title the learner read on the page. It is what the model
       * is told the question is about; the id above is what the platform records. Neither
       * substitutes for the other, which is why a turn carries both.
       */
      knowledgePointTitle?: string;
    }
  | {
      kind: 'course';
      courseId: string;
      label: string;
      /**
       * The learner's OWN knowledge point this conversation is about, when 学习 handed the
       * question over from a point they were reading.
       *
       * The EXAM scope's point is a canonical code from the published outline; this one is a
       * `knowledge_points` row id, because a learner's structure is their own and has no code
       * outside their account. Both are identities, and both are settled by the same rule: the
       * point is the turn's context, never a question asked for the learner.
       */
      knowledgePoint?: string;
      /** The point's title as the page that linked here wrote it — display and prompt only. */
      knowledgePointTitle?: string;
    }
  | { kind: 'programming'; language: string; label: string };

export function scopeKey(scope: AiScope): string {
  switch (scope.kind) {
    case 'general': return 'general';
    case 'exam': return `exam:${scope.moduleKey}`;
    case 'course': return `course:${scope.courseId}`;
    case 'programming': return `programming:${scope.language}`;
  }
}

/** The `/chat` fields a scope turns into. Empty strings are the product's own "no scope". */
export function scopeToChatBody(scope: AiScope) {
  switch (scope.kind) {
    case 'general':
      return { service_key: '', course_id: '', course: '', subject_key: '', exam_subject: '', knowledge_point_id: '', knowledge_point_title: '' };
    case 'exam':
      return {
        service_key: 'exam_11408', course_id: '', course: '', subject_key: '', exam_subject: scope.moduleKey,
        // The one scope that can name a knowledge point. Every other scope has none, and the
        // server treats the empty string as "this turn is not about a point".
        knowledge_point_id: scope.knowledgePoint ?? '',
        knowledge_point_title: scope.knowledgePointTitle ?? '',
      };
    case 'course':
      // A course turn can carry one of the learner's own knowledge points, the same way an exam
      // turn carries a node of the published outline. Every other course entry point leaves both
      // empty, and the server reads the empty string as "this turn is not about a point".
      return {
        service_key: 'course_learning', course_id: scope.courseId, course: scope.courseId,
        subject_key: '', exam_subject: '',
        knowledge_point_id: scope.knowledgePoint ?? '',
        knowledge_point_title: scope.knowledgePointTitle ?? '',
      };
    case 'programming':
      return { service_key: 'programming', course_id: '', course: '', subject_key: 'programming', exam_subject: '', knowledge_point_id: '', knowledge_point_title: '' };
  }
}

/** The strong-reasoning workflow takes the same scope, under its own field names. */
export function scopeToDeepStudy(scope: AiScope) {
  switch (scope.kind) {
    case 'general':
      return { service_key: 'course_learning', course_id: '', subject_key: '' };
    case 'exam':
      return { service_key: 'exam_11408', course_id: '', subject_key: scope.moduleKey };
    case 'course':
      return { service_key: 'course_learning', course_id: scope.courseId, subject_key: '' };
    case 'programming':
      return { service_key: 'programming', course_id: '', subject_key: 'programming' };
  }
}

/* ---------------------------------------------------------------- the conversation */

export type AiCitation = { filename: string; snippet: string };
/**
 * A file that rode along with a learner turn.
 *
 * `sourceKind` is only ever present on a turn RESTORED from a stored message, where the server
 * reports how that attachment was recorded at the time. A turn still being composed carries the
 * composer's own attachment (see `AttachmentMaterial`), which has no such field and is not
 * displayed from one — the chip shows the filename.
 */
export type AiAttachment = { materialId: number; filename: string; fileType: string; sourceKind?: string; parseStatus: string };

/**
 * Where a re-worded question sits among its own versions.
 *
 * `previousMessageId` / `nextMessageId` are MESSAGE ids, not branch ids: the client asks to see a
 * message, and which branch that means stays the server's business.
 */
export type AiVersionInfo = {
  /** 1-based position of THIS version. */
  index: number;
  total: number;
  hasPrevious: boolean;
  hasNext: boolean;
  previousMessageId?: number;
  nextMessageId?: number;
};

export type AiTurn = {
  id: string;
  role: 'learner' | 'assistant';
  text: string;
  citations?: AiCitation[];
  requestId?: string | null;
  deep?: boolean;
  /** Which model the Router actually resolved for this answer, as the stream reported it. */
  resolvedModel?: string | null;
  /** Why the model stopped (`stop` / `length` …) — reported by the terminal `done` event. */
  finishReason?: string | null;
  /** True when the learner stopped this answer, so the partial text is all there will be. */
  stopped?: boolean;
  attachments?: AiAttachment[];
  /**
   * The stored id of this learner turn's own question, when the server has told us one.
   *
   * Editing a question is a fork FROM a stored message, so the id is what makes the fork
   * expressible. It arrives with the answer's `start` event for a turn asked here, and with the
   * conversation itself for a turn restored from history.
   */
  messageId?: number;
  /** Present only when this question has other versions. */
  version?: AiVersionInfo;
  state: 'pending' | 'done' | 'failed';
};

export type AiAsk = {
  message: string;
  sessionId?: number;
  scope: AiScope;
  thinkingMode: 'standard' | 'deep';
  materialIds?: number[];
  attachmentIds?: number[];
  modelId?: string;
  /**
   * The stored question this one RE-WORDS, when it is an edit.
   *
   * The server records the new wording as a version of that question, in the same conversation:
   * the original stays, and this branch becomes the one the learner is reading.
   */
  editSourceMessageId?: number;
  /**
   * The message the learner is looking at, when they have stepped onto an older version.
   *
   * The turn then belongs to THAT version's branch rather than to whichever one is newest, so
   * asking from an older version continues the older version.
   */
  continueFromMessageId?: number;
};

/**
 * The `/chat` request body, built once so the one-shot POST and the streaming POST cannot drift
 * apart: they answer the same capability with the same scope, and only the transport differs.
 */
export function chatRequestBody(input: AiAsk) {
  const scope = scopeToChatBody(input.scope);
  return {
    message: input.message,
    ...scope,
    subject: '', grade: '', major: '', material_ids: input.materialIds ?? [], attachment_ids: input.attachmentIds ?? [],
    branch_id: '', hidden_instruction: '', mastery_level: '', learning_goal: '',
    edit_source_message_id: input.editSourceMessageId ?? null,
    continue_from_message_id: input.continueFromMessageId ?? null,
    model_preference: '', session_id: input.sessionId ?? null,
    model_id: input.modelId || null, thinking_mode: input.thinkingMode,
  };
}

export async function sendAiChat(input: AiAsk): Promise<Record<string, unknown>> {
  const { data, error, response } = await apiClient.POST('/chat', { body: chatRequestBody(input) });
  return dataOrThrow(response, data, error) as Record<string, unknown>;
}

export function useAiChat() {
  return useMutation({
    mutationFn: sendAiChat,
  });
}

/** The learner's own past conversations, newest first. */
export type AiSessionSummary = { id: number; title: string; createdAt: string };

function scopeHistoryQuery(scope: AiScope): Record<string, string> {
  switch (scope.kind) {
    case 'exam':
      return { exam_subject: scope.moduleKey, subject_key: scope.moduleKey };
    case 'course':
      return { course: scope.courseId };
    case 'programming':
      return { subject: 'programming', subject_key: 'programming' };
    case 'general':
      return {};
  }
}

export async function fetchScopedAiSessions(scope: AiScope): Promise<AiSessionSummary[]> {
  const { data, response } = await apiClient.GET('/chat/history', {
    params: { query: scopeHistoryQuery(scope) },
  });
  if (!response.ok || !isRecord(data)) return [];
  const sessions = Array.isArray(data.sessions) ? data.sessions : [];
  return sessions.flatMap((entry): AiSessionSummary[] => {
    if (!isRecord(entry) || typeof entry.id !== 'number') return [];
    return [{
      id: entry.id,
      title: text(entry.title) ?? '未命名对话',
      createdAt: text(entry.created_at) ?? '',
    }];
  });
}

export function useScopedAiSessions(scope: AiScope) {
  return useQuery({
    queryKey: ['ai', 'sessions', scopeKey(scope)],
    queryFn: () => fetchScopedAiSessions(scope),
    retry: false,
  });
}

export async function fetchAiSessionTurns(sessionId: number, scope: AiScope, versionMessageId?: number): Promise<AiTurn[]> {
  const { data, response } = await apiClient.GET('/chat/sessions/{session_id}', {
    params: {
      path: { session_id: sessionId },
      // Naming a version reads THAT version's branch. It is a read: nothing is written, and the
      // conversation's own current branch is untouched.
      query: { ...scopeHistoryQuery(scope), ...(versionMessageId === undefined ? {} : { version_message_id: versionMessageId }) },
    },
  });
  if (!response.ok || !isRecord(data)) return [];
  const messages = Array.isArray(data.messages) ? data.messages : [];
  const turns: AiTurn[] = [];
  for (const message of messages) {
    if (!isRecord(message)) continue;
    const role = text(message.role);
    const content = text(message.content);
    if ((role !== 'user' && role !== 'assistant') || !content) continue;
    turns.push({
      id: `stored-${String(message.id ?? turns.length)}`,
      role: role === 'user' ? 'learner' : 'assistant',
      text: content,
      citations: role === 'assistant' ? citationsFrom(message.references) : [],
      attachments: role === 'user' ? attachmentsFrom(message.attachments) : [],
      messageId: typeof message.id === 'number' ? message.id : undefined,
      version: versionFrom(message.version),
      state: 'done',
    });
  }
  return turns;
}

export function citationsFrom(value: unknown): AiCitation[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const out: AiCitation[] = [];
  for (const entry of value) {
    if (!isRecord(entry)) continue;
    const filename = text(entry.filename);
    if (!filename || seen.has(filename)) continue;
    seen.add(filename);
    out.push({ filename, snippet: text(entry.snippet) ?? text(entry.chunk_text) ?? '' });
  }
  return out;
}

function versionFrom(value: unknown): AiVersionInfo | undefined {
  if (!isRecord(value)) return undefined;
  const index = value.index;
  const total = value.total;
  if (typeof index !== 'number' || typeof total !== 'number' || total < 2) return undefined;
  return {
    index,
    total,
    hasPrevious: value.has_previous === true,
    hasNext: value.has_next === true,
    previousMessageId: typeof value.previous_message_id === 'number' ? value.previous_message_id : undefined,
    nextMessageId: typeof value.next_message_id === 'number' ? value.next_message_id : undefined,
  };
}

export function attachmentsFrom(value: unknown): AiAttachment[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<number>();
  return value.flatMap((entry): AiAttachment[] => {
    if (!isRecord(entry) || typeof entry.material_id !== 'number' || seen.has(entry.material_id)) return [];
    const filename = text(entry.filename);
    if (!filename) return [];
    seen.add(entry.material_id);
    return [{ materialId: entry.material_id, filename, fileType: text(entry.file_type) ?? '', sourceKind: text(entry.source_kind) ?? '', parseStatus: text(entry.parse_status) ?? 'success' }];
  });
}

/* ---------------------------------------------------------------- reading /chat's answer */

export function answerOf(data: unknown): string {
  return (isRecord(data) && text(data.answer)) || '';
}

export function citationsOf(data: unknown): AiCitation[] {
  return isRecord(data) ? citationsFrom(data.references) : [];
}

export function sessionIdOf(data: unknown): number | undefined {
  if (!isRecord(data) || !isRecord(data.session)) return undefined;
  const id = data.session.id;
  return typeof id === 'number' ? id : undefined;
}

/* ---------------------------------------------------------------- the qualified model pool

   A learner picks a CLASS of model, never a model. The list is served by the backend from the
   Router's own qualified pool for the caller's tier and capability, and each entry carries only
   a key and a label — no provider, no model id, no price. When the backend has not supplied
   that list the picker is not rendered at all, rather than rendering a control whose choice
   would not reach the Router. */

export type ModelOption = { id: string; label: string; provider: string; thinking: boolean };
export type ModelOptions = { options: ModelOption[]; recommended: Pick<ModelOption, 'id' | 'label'> | null };

export function fetchModelOptions(capability: string): Promise<ModelOptions> {
  return apiClient
    .GET('/ai/models', { params: { query: { capability } } })
    .then(({ data, response }) => {
      if (!response.ok || !isRecord(data)) return { options: [], recommended: null };
      const list = data.options;
      if (!Array.isArray(list)) return { options: [], recommended: null };
      const options = list.flatMap((entry): ModelOption[] => {
        if (!isRecord(entry)) return [];
        const id = text(entry.model);
        return id ? [{ id, label: text(entry.display_name) ?? id, provider: text(entry.provider) ?? '其他', thinking: entry.thinking === true }] : [];
      });
      const recommendedId = text(data.recommended_model_id);
      return { options, recommended: recommendedId ? options.find((option) => option.id === recommendedId) ?? null : null };
    })
    .catch(() => ({ options: [], recommended: null }));
}

export function useModelOptions(capability: string) {
  return useQuery({
    queryKey: ['ai', 'model-options', capability],
    queryFn: () => fetchModelOptions(capability),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

/* ---------------------------------------------------------------- materials to ground on */

export type AiMaterial = { id: number; filename: string };

export function useCourseMaterialsForChat(courseId: string | undefined) {
  return useQuery({
    queryKey: ['ai', 'materials', courseId ?? ''],
    enabled: Boolean(courseId),
    retry: false,
    queryFn: async (): Promise<AiMaterial[]> => {
      const { data, response } = await apiClient.GET(
        '/course-learning/courses/{course_id}/materials',
        { params: { path: { course_id: courseId as string } } },
      );
      if (!response.ok || !isRecord(data)) return [];
      const items = Array.isArray(data.items) ? data.items : [];
      return items.flatMap((entry): AiMaterial[] => {
        if (!isRecord(entry) || typeof entry.id !== 'number') return [];
        const filename = text(entry.original_filename) ?? text(entry.filename);
        return filename ? [{ id: entry.id, filename }] : [];
      });
    },
  });
}

/* ---------------------------------------------------------------- history: rename */

export const AI_SESSIONS_KEY = ['ai', 'sessions'] as const;

/**
 * Rename one of the learner's own conversations.
 *
 * The scope goes with it for the same reason every other session call carries it: a session id
 * alone is not a way into a conversation whose course the learner no longer has, and the server
 * refuses a mismatch rather than trusting whatever the client's list happens to hold.
 */
export async function renameAiSession(sessionId: number, title: string, scope: AiScope): Promise<void> {
  const { response, error } = await apiClient.PATCH('/chat/sessions/{session_id}', {
    params: { path: { session_id: sessionId }, query: scopeHistoryQuery(scope) },
    body: { title },
  });
  if (!response.ok) throw new ApiRequestError(response.status, error);
}
