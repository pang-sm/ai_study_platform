import { toCourseIdentity } from '@/features/course/api/course';
import { cs408Modules } from '@/features/exam/api/dashboard-summary';
import { canonicalLanguage, normalizeLanguageSlug } from '@/features/programming/programming-language';
import type { ReviewRecommendation } from './recommendations-api';

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as UnknownRecord
    : {};
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

export function isGenericQuestionTitle(item: ReviewRecommendation): boolean {
  return /^题目\s+\d+$/u.test(item.title.trim());
}

export function reviewRecommendationTitle(
  item: ReviewRecommendation,
  stemsByWrongAnswerId: ReadonlyMap<string, string>,
): string {
  if (!isGenericQuestionTitle(item)) return item.title.trim() || '复习内容';

  const wrongAnswerId = text(record(item.evidence).source_id);
  const stem = text(stemsByWrongAnswerId.get(wrongAnswerId)).replace(/\s+/gu, ' ');
  return stem || '待复习题目';
}

function courseRows(catalog: unknown): unknown[] {
  if (Array.isArray(catalog)) return catalog;
  const value = record(catalog);
  if (Array.isArray(value.courses)) return value.courses;
  if (Array.isArray(value.items)) return value.items;
  return [];
}

export function reviewDirectionLabel(item: ReviewRecommendation, catalog: unknown): string {
  const domain = record(item.domain_context);

  if (item.service_namespace === 'course_learning') {
    const courseId = text(domain.course_id);
    const course = courseRows(catalog)
      .map(toCourseIdentity)
      .find((candidate) => candidate.id === courseId);
    return course?.name ? `专业学习 · ${course.name}` : '专业学习';
  }

  if (item.service_namespace === 'exam_11408' || item.service_namespace === 'exam_prep') {
    const moduleKey = text(domain.exam_module_id);
    const module = cs408Modules.find((candidate) => candidate.key === moduleKey);
    return module ? `11408 · ${module.name}` : '11408';
  }

  if (item.service_namespace === 'programming') {
    const languageSlug = normalizeLanguageSlug(domain.language);
    const language = languageSlug ? canonicalLanguage(languageSlug) : undefined;
    return language ? `编程 · ${language}` : '编程';
  }

  return '学习';
}
