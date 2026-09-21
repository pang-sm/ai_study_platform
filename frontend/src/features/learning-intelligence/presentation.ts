export type LearningSpace = 'course_learning' | 'exam_11408' | 'programming';

export type LearningScope = {
  service_key: LearningSpace;
  course_id: string;
  exam_module_id: string;
  language: string;
};

export function displayMetric(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return '—';
}

export function reportScopeFromSearch(search: { space?: unknown; courseId?: unknown; module?: unknown; language?: unknown }): LearningScope {
  const space: LearningSpace = search.space === 'exam_11408' || search.space === 'programming' ? search.space : 'course_learning';
  return {
    service_key: space,
    course_id: space === 'course_learning' && typeof search.courseId === 'string' ? search.courseId : '',
    exam_module_id: space === 'exam_11408' && typeof search.module === 'string' ? search.module : '',
    language: space === 'programming' && typeof search.language === 'string' ? search.language : '',
  };
}

/** Returns a route only when the backend supplied both a destination and its canonical context. */
export function safeActionHref(value: Record<string, unknown>): string | undefined {
  const destination = value.destination;
  const serviceKey = value.service_key;
  if ((destination !== 'review' && destination !== 'plan' && destination !== 'wrong') || (serviceKey !== 'course_learning' && serviceKey !== 'exam_11408' && serviceKey !== 'programming')) return undefined;
  const courseId = typeof value.course_id === 'string' ? value.course_id : '';
  const module = typeof value.exam_module_id === 'string' ? value.exam_module_id : '';
  const language = typeof value.language === 'string' ? value.language : '';
  if ((serviceKey === 'course_learning' && !courseId) || (serviceKey === 'exam_11408' && !module) || (serviceKey === 'programming' && !language)) return undefined;
  if (destination === 'review') return `/review?space=${encodeURIComponent(serviceKey)}${module ? `&module=${encodeURIComponent(module)}` : ''}`;
  if (destination === 'plan') return serviceKey === 'course_learning' ? `/course/${encodeURIComponent(courseId)}/plan` : serviceKey === 'exam_11408' ? `/exam/cs408/plan?module=${encodeURIComponent(module)}` : `/programming/${encodeURIComponent(language)}/plan`;
  return serviceKey === 'course_learning' ? `/course/${encodeURIComponent(courseId)}/wrong` : serviceKey === 'exam_11408' ? `/exam/cs408/wrong?module=${encodeURIComponent(module)}` : undefined;
}
