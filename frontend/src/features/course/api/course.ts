import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { LIBRARY_MATERIALS_KEY } from '@/features/library/api/library';

export type CourseIdentity = { id: string | undefined; name: string | undefined };
export type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringAt(value: unknown, key: string): string | undefined {
  return isRecord(value) && typeof value[key] === 'string' ? value[key] : undefined;
}

export function toCourseIdentity(value: unknown): CourseIdentity {
  return { id: stringAt(value, 'id') ?? stringAt(value, 'course_id'), name: stringAt(value, 'name') ?? stringAt(value, 'course_name') };
}

export function courseScopedQuery(courseId: string) {
  return { course_id: courseId };
}

function requireData<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export const courseKeys = {
  onboarding: ['course', 'onboarding'] as const,
  catalog: ['course', 'catalog'] as const,
  dashboard: (courseId: string) => ['course', courseId, 'dashboard'] as const,
  materials: (courseId: string) => ['course', courseId, 'materials'] as const,
  knowledge: (courseId: string) => ['course', courseId, 'knowledge'] as const,
  map: (courseId: string) => ['course', courseId, 'knowledge-map'] as const,
  practice: (courseId: string) => ['course', courseId, 'practice'] as const,
  history: (courseId: string) => ['course', courseId, 'practice-history'] as const,
  plan: (courseId: string) => ['course', courseId, 'plan'] as const,
  entitlements: ['course', 'entitlements'] as const,
  todayPlan: (courseId: string) => ['course', courseId, 'today-plan'] as const,
  records: (courseId: string) => ['course', courseId, 'records'] as const,
  recordsSummary: (courseId: string) => ['course', courseId, 'records-summary'] as const,
  wrong: (courseId: string) => ['course', courseId, 'wrong'] as const,
  state: (courseId: string) => ['course', courseId, 'state'] as const,
} as const;

async function getCourseCatalog(): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/courses', {});
  return requireData(response, data, error);
}

async function getCourseDashboard(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-dashboard', { params: { query: { course: courseId } } });
  return requireData(response, data, error);
}

async function getMaterials(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/courses/{course_id}/materials', { params: { path: { course_id: courseId } } });
  return requireData(response, data, error);
}

async function getKnowledgePoints(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/knowledge-points', { params: { query: courseScopedQuery(courseId) } });
  return requireData(response, data, error);
}

async function getKnowledgeMap(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/knowledge-map', { params: { query: courseScopedQuery(courseId) } });
  return requireData(response, data, error);
}

async function getPracticeWorkbook(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/courses/{course_id}/practice/workbook', { params: { path: { course_id: courseId } } });
  return requireData(response, data, error);
}

async function getPracticeHistory(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/courses/{course_id}/practice/history', { params: { path: { course_id: courseId } } });
  return requireData(response, data, error);
}

async function getStudyPlan(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/study-plan', { params: { query: courseScopedQuery(courseId) } });
  return requireData(response, data, error);
}

async function getEntitlements(): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/entitlements', {});
  return requireData(response, data, error);
}

async function getTodayPlan(courseId: string): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/courses/{course_id}/today-plan', { params: { path: { course_id: courseId } } });
  return requireData(response, data, error);
}

export type CourseOnboardingInput = components['schemas']['CourseLearningOnboardingRequest'];

/**
 * The stored course-learning context: what the learner declared in the setup flow.
 *
 * Read separately from the course list because they answer different questions — this one is
 * "what was declared" (major, grade, the declared course names and their goals), the list is
 * "what those declarations now contain" (materials, pending tasks, the stored mode).
 */
async function getCourseOnboarding(): Promise<unknown> {
  const { data, error, response } = await apiClient.GET('/course-learning/onboarding', {});
  return requireData(response, data, error);
}

/**
 * The one write path for the course context.
 *
 * `plan` is deliberately not sent: when it is absent the backend keeps the track's existing plan,
 * so a save from this screen cannot move a paid learner onto `free`. Sending `null` explicitly
 * would do the opposite of that.
 */
export function useSaveCourseOnboarding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (input: CourseOnboardingInput) => {
      const r = await apiClient.POST('/course-learning/onboarding', { body: input });
      return requireData(r.response, r.data, r.error);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: courseKeys.onboarding });
      void client.invalidateQueries({ queryKey: courseKeys.catalog });
      // The course context also lands on the account row (`major`, `grade`, `focus_courses`), so
      // the session and the profile are re-read rather than left showing the previous answer.
      void client.invalidateQueries({ queryKey: ['auth', 'session'] });
      void client.invalidateQueries({ queryKey: ['profile', 'detail'] });
    },
  });
}

export function useCourseOnboarding() { return useQuery({ queryKey: courseKeys.onboarding, queryFn: getCourseOnboarding, retry: false }); }
export function useCourseCatalog() { return useQuery({ queryKey: courseKeys.catalog, queryFn: getCourseCatalog, retry: false }); }
export function useCourseDashboard(courseId: string) { return useQuery({ queryKey: courseKeys.dashboard(courseId), queryFn: () => getCourseDashboard(courseId), retry: false }); }
export function useCourseMaterials(courseId: string) { return useQuery({ queryKey: courseKeys.materials(courseId), queryFn: () => getMaterials(courseId), retry: false }); }
export function useCourseKnowledge(courseId: string) { return useQuery({ queryKey: courseKeys.knowledge(courseId), queryFn: () => getKnowledgePoints(courseId), retry: false }); }
export function useCourseKnowledgeMap(courseId: string) { return useQuery({ queryKey: courseKeys.map(courseId), queryFn: () => getKnowledgeMap(courseId), retry: false }); }
export function useCoursePractice(courseId: string) { return useQuery({ queryKey: courseKeys.practice(courseId), queryFn: () => getPracticeWorkbook(courseId), retry: false }); }
export function useCoursePracticeHistory(courseId: string) { return useQuery({ queryKey: courseKeys.history(courseId), queryFn: () => getPracticeHistory(courseId), retry: false }); }
export function useCourseStudyPlan(courseId: string) { return useQuery({ queryKey: courseKeys.plan(courseId), queryFn: () => getStudyPlan(courseId), retry: false }); }
export function useCourseEntitlements() { return useQuery({ queryKey: courseKeys.entitlements, queryFn: getEntitlements, retry: false }); }
export function useCourseTodayPlan(courseId: string) { return useQuery({ queryKey: courseKeys.todayPlan(courseId), queryFn: () => getTodayPlan(courseId), retry: false }); }
export function useCourseRecords(courseId: string) { return useQuery({ queryKey: courseKeys.records(courseId), queryFn: async () => { const r = await apiClient.GET('/course-learning/courses/{course_id}/records', { params: { path: { course_id: courseId } } }); return requireData(r.response, r.data, r.error); }, retry: false }); }
export function useCourseRecordsSummary(courseId: string) { return useQuery({ queryKey: courseKeys.recordsSummary(courseId), queryFn: async () => { const r = await apiClient.GET('/course-learning/courses/{course_id}/records/summary', { params: { path: { course_id: courseId } } }); return requireData(r.response, r.data, r.error); }, retry: false }); }
export function useCourseWrongAnswers(courseId: string) { return useQuery({ queryKey: courseKeys.wrong(courseId), queryFn: async () => { const r = await apiClient.GET('/course-learning/courses/{course_id}/wrong-answers', { params: { path: { course_id: courseId } } }); return requireData(r.response, r.data, r.error); }, retry: false }); }
export function useCourseState(courseId: string) { return useQuery({ queryKey: courseKeys.state(courseId), queryFn: async () => { const r = await apiClient.GET('/course-learning/courses/{course_id}/state', { params: { path: { course_id: courseId } } }); return requireData(r.response, r.data, r.error); }, retry: false }); }
/**
 * What this endpoint actually accepts, taken from the server's own allow-lists.
 *
 * `accept` is the union of `ALLOWED_EXTENSIONS`; the format sentence names what that list means
 * to a reader; the ceiling is `MAX_NEW_TYPE_SIZE` (20MB), which is the larger of the two size
 * limits the backend applies — the other, 10MB, covers PDF and images.
 */
export const MATERIAL_UPLOAD_ACCEPT = [
  '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.docx', '.pptx', '.txt', '.md', '.markdown',
  '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.js', '.jsx', '.ts', '.tsx', '.html', '.htm',
  '.css', '.json', '.xml', '.yaml', '.yml', '.sql', '.sh',
].join(',');

export const MATERIAL_UPLOAD_FORMATS =
  'PDF、图片（PNG / JPG / WebP）、Word（.docx）、PPT（.pptx）、TXT、Markdown 和常见代码文件';
export const MATERIAL_UPLOAD_MAX_MB = 20;

/** The server's refusal, unwrapped from whichever shape it arrived in. */

/**
 * Why an upload was refused, in words a learner can act on.
 *
 * The endpoint answers 400 with a sentence for each rule it enforces (format, extension/type
 * mismatch, a legacy `.doc` or `.ppt`, size) and 413/409 with a coded object whose `message` is
 * already written for a reader. Those sentences are the answer, so they are shown as they
 * arrive; only a failure with nothing to say falls back to naming the limits.
 *
 * The previous text — "上传未成功，后端没有接受这个文件。" — was true of every possible failure and
 * therefore told the learner nothing: not what was wrong with the file, and not what to do.
 */
export function materialUploadErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    const message = serverMessage(error.detail);
    if (message) return message;
    if (error.status === 413) return `文件太大。单个文件最大支持 ${MATERIAL_UPLOAD_MAX_MB}MB，压缩或拆分后再上传。`;
    if (error.status === 409) return '这门课程里已经有一份内容相同的资料。';
    if (error.status === 401 || error.status === 403) return '登录状态已失效，重新登录后就可以继续上传。';
  }
  return `上传没有成功。支持 ${MATERIAL_UPLOAD_FORMATS}，单个文件最大 ${MATERIAL_UPLOAD_MAX_MB}MB。`;
}


export function useCourseMaterialUpload(courseId: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: async (file: File) => {
    const r = await apiClient.POST('/course-learning/courses/{course_id}/materials', {
      params: { path: { course_id: courseId } },
      // openapi-typescript renders multipart binary as `string`, and openapi-fetch only leaves a
      // body alone when it is already FormData — anything else is JSON-stringified with a
      // `application/json` content type. So `{ file }` used to arrive as JSON, the multipart
      // parser never ran, the required `file` part was missing, and FastAPI answered 422 before
      // the handler was reached: every upload failed, whatever the file was.
      body: { file: file as unknown as string },
      bodySerializer: () => {
        const form = new FormData();
        form.append('file', file);
        return form;
      },
    });
    return requireData(r.response, r.data, r.error);
  }, onSuccess: () => {
    // A course upload is ALSO a library asset, and the 资料 page reads the library rather than
    // this course's own list — so the list the learner is looking at is the one to refresh.
    void client.invalidateQueries({ queryKey: courseKeys.materials(courseId) });
    void client.invalidateQueries({ queryKey: LIBRARY_MATERIALS_KEY });
  } });
}
export function useCoursePracticeAction(courseId: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: async ({ kind, id, answer }: { kind: 'start' | 'generate' | 'submit'; id?: number; answer?: string }) => { if (kind === 'start') { const r = await apiClient.POST('/course-learning/courses/{course_id}/practice/questions/{question_id}/attempts', { params: { path: { course_id: courseId, question_id: id ?? 0 } } }); return requireData(r.response, r.data, r.error); } if (kind === 'generate') { const r = await apiClient.POST('/course-learning/courses/{course_id}/practice/generate', { params: { path: { course_id: courseId } }, body: { knowledge_point_code: '', knowledge_point_id: '', knowledge_point_title: '', chapter: '', difficulty: '', material_ids: [] } }); return requireData(r.response, r.data, r.error); } const r = await apiClient.POST('/course-learning/courses/{course_id}/practice/{attempt_id}/submit', { params: { path: { course_id: courseId, attempt_id: id ?? 0 } }, body: { answer: answer ?? '' } }); return requireData(r.response, r.data, r.error); }, onSuccess: (_data, variables) => {
    const keys = variables.kind === 'submit'
      ? [courseKeys.practice(courseId), courseKeys.history(courseId), courseKeys.wrong(courseId), courseKeys.records(courseId), courseKeys.recordsSummary(courseId), courseKeys.state(courseId), courseKeys.todayPlan(courseId), courseKeys.plan(courseId)]
      : [courseKeys.practice(courseId), courseKeys.history(courseId)];
    keys.forEach((queryKey) => void client.invalidateQueries({ queryKey }));
    if (variables.kind === 'submit') void client.invalidateQueries({ queryKey: ['learning', 'agenda'] });
  } });
}

/**
 * One turn of course Q&A.
 *
 * `sessionId` continues the server's own conversation, which is what makes the surface a chat
 * rather than a series of unrelated questions: passing it back means the follow-up is stored
 * under the same `ChatSession` and the backend can see what was already asked. The first turn
 * omits it and the server opens one.
 */
/**
 * The conversation the server already holds for this course, if there is one.
 *
 * The backend has always persisted course Q&A (`ChatSession` / `ChatMessage`, and the assistant
 * message's own `reference_payload`), and `GET /chat/history` + `GET /chat/sessions/{id}` expose
 * it. The surface simply never read it back, so a learner who reloaded lost a conversation the
 * server still had — the answers and their citations were on disk the whole time.
 *
 * The newest session for THIS course is the one the page continues; a session belonging to another
 * course is not this page's history, and merging them would put another course's material in front
 * of the learner here.
 */
export type CourseQaStoredTurn = {
  id: string;
  role: 'learner' | 'assistant';
  text: string;
  citations: CourseCitation[];
};

export async function fetchCourseQaHistory(courseId: string): Promise<{ sessionId?: number; turns: CourseQaStoredTurn[] }> {
  // Scoped by `course` on the SERVER: the endpoint takes it, so another course's conversation is
  // never even sent to this page.
  const history = await apiClient.GET('/chat/history', {
    params: { query: { course: courseId } },
  });
  const sessions = isRecord(history.data) && Array.isArray(history.data.sessions) ? history.data.sessions : [];
  const mine = sessions
    .filter((entry): entry is JsonRecord => isRecord(entry) && stringAt(entry, 'course') === courseId)
    .sort((left, right) => String(stringAt(right, 'id') ?? '').localeCompare(String(stringAt(left, 'id') ?? '')));
  const newest = mine[0];
  const sessionId = newest && typeof newest.id === 'number' ? newest.id : undefined;
  if (sessionId === undefined) return { turns: [] };

  const detail = await apiClient.GET('/chat/sessions/{session_id}', {
    params: { path: { session_id: sessionId } },
  });
  const messages = isRecord(detail.data) && Array.isArray(detail.data.messages) ? detail.data.messages : [];
  const turns: CourseQaStoredTurn[] = [];
  for (const message of messages) {
    if (!isRecord(message)) continue;
    const role = stringAt(message, 'role');
    const content = stringAt(message, 'content');
    if ((role !== 'user' && role !== 'assistant') || !content) continue;
    turns.push({
      id: `stored-${String(message.id ?? turns.length)}`,
      role: role === 'user' ? 'learner' : 'assistant',
      text: content,
      citations: role === 'assistant' ? citationsFromStored(message.references) : [],
    });
  }
  return { sessionId, turns };
}

/** The same reference shape `chatCitations` reads, from a stored message's own payload. */
function citationsFromStored(value: unknown): CourseCitation[] {
  return chatCitations({ references: value });
}

/** The session id the server opened or continued, if it reported one. */
export function chatSessionId(data: unknown): number | undefined {
  if (!isRecord(data) || !isRecord(data.session)) return undefined;
  const id = data.session.id;
  return typeof id === 'number' ? id : undefined;
}

/** The answer text, when the server produced one. */
export function chatAnswer(data: unknown): string | undefined {
  return stringAt(data, 'answer');
}

/**
 * Which of the course's materials grounded the answer.
 *
 * `references` is the retrieval result: one entry per chunk the answer was allowed to use, each
 * carrying the file it came from and the passage itself. The learner sees the file and the
 * passage — a citation they can check — and never the chunk id or the similarity score.
 */
export type CourseCitation = { filename: string; snippet: string };

export function chatCitations(data: unknown): CourseCitation[] {
  if (!isRecord(data) || !Array.isArray(data.references)) return [];
  const seen = new Set<string>();
  const citations: CourseCitation[] = [];
  for (const entry of data.references) {
    if (!isRecord(entry)) continue;
    const filename = stringAt(entry, 'filename');
    const snippet = stringAt(entry, 'snippet');
    if (!filename || seen.has(filename)) continue;
    seen.add(filename);
    citations.push({ filename, snippet: snippet ?? '' });
  }
  return citations;
}

export function isExplicitlyScopedToCourse(value: unknown, courseId: string): boolean {
  return stringAt(value, 'course_id') === courseId;
}
