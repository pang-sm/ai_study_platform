import { describe, expect, it } from 'vitest';
import { displayMetric, reportScopeFromSearch, safeActionHref } from './presentation';
import { learningReportKey } from './api';

describe('learning intelligence presentation contracts', () => {
  it('preserves a missing metric instead of turning it into zero, and says so in the product’s language', () => {
    expect(displayMetric(null)).toBe('—');
    expect(displayMetric(undefined)).toBe('—');
    expect(displayMetric(0)).toBe('0');
  });

  it('keeps report contexts isolated across the three learning spaces', () => {
    expect(reportScopeFromSearch({ space: 'course_learning', courseId: 'course-a' })).toEqual({ service_key: 'course_learning', course_id: 'course-a', exam_module_id: '', language: '' });
    expect(reportScopeFromSearch({ space: 'exam_11408', module: 'operating_system' })).toEqual({ service_key: 'exam_11408', course_id: '', exam_module_id: 'operating_system', language: '' });
    expect(reportScopeFromSearch({ space: 'programming', language: 'python' })).toEqual({ service_key: 'programming', course_id: '', exam_module_id: '', language: 'python' });
  });

  it('uses a context-complete cache key so reports cannot leak between scopes', () => {
    const course = reportScopeFromSearch({ space: 'course_learning', courseId: 'course-a' });
    const programming = reportScopeFromSearch({ space: 'programming', language: 'python' });
    expect(learningReportKey(course)).not.toEqual(learningReportKey(programming));
    expect(learningReportKey(course)).toEqual(['learning-report', 'course_learning', 'course-a', '', '']);
  });

  it('creates navigation only from a backend-provided identity, never a display title', () => {
    expect(safeActionHref({ destination: 'review', service_key: 'exam_11408', exam_module_id: 'data_structure' })).toBe('/review?space=exam_11408&module=data_structure');
    expect(safeActionHref({ title: '去复习', reason: '建议复习' })).toBeUndefined();
  });
});
