import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';

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
export function useCourseMaterialUpload(courseId: string) {
  const client = useQueryClient();
  return useMutation({ mutationFn: async (file: File) => {
    // openapi-typescript renders multipart binary as string; openapi-fetch forwards File correctly.
    const r = await apiClient.POST('/course-learning/courses/{course_id}/materials', { params: { path: { course_id: courseId } }, body: { file: file as unknown as string } });
    return requireData(r.response, r.data, r.error);
  }, onSuccess: () => void client.invalidateQueries({ queryKey: courseKeys.materials(courseId) }) });
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

export function useCourseChat(courseId: string) {
  return useMutation({
    mutationFn: async (message: string) => {
      const { data, error, response } = await apiClient.POST('/chat', { body: {
        message, course_id: courseId, course: courseId, service_key: 'course_learning',
        subject: '', subject_key: '', exam_subject: '', grade: '', major: '', material_ids: [],
        branch_id: '', hidden_instruction: '', mastery_level: '', learning_goal: '',
      } });
      return requireData(response, data, error);
    },
  });
}

export function isExplicitlyScopedToCourse(value: unknown, courseId: string): boolean {
  return stringAt(value, 'course_id') === courseId;
}
