import { describe, expect, it } from 'vitest';
import type { ReviewRecommendation } from './recommendations-api';
import { reviewDirectionLabel, reviewRecommendationTitle } from './review-presentation';

function recommendation(overrides: Partial<ReviewRecommendation> = {}): ReviewRecommendation {
  return {
    recommendation_key: 'stable-key',
    kind: 'question',
    service_namespace: 'exam_prep',
    domain_context: { exam_module_id: 'operating_system' },
    title: '题目 1686572',
    direction: '11408 · operating_system',
    reason_code: 'single_wrong',
    reason: '这道题有一次尚未订正的真实错误',
    evidence: { source_id: '52' },
    action: { deep_link: '/exam/cs408/wrong?module=operating_system' },
    ...overrides,
  };
}

describe('review presentation', () => {
  it('uses the real wrong-question stem and never the answer or explanation', () => {
    const item = recommendation();
    const result = reviewRecommendationTitle(item, new Map([
      ['52', '进程调度中，以下哪种算法会导致短作业优先？'],
    ]));
    expect(result).toBe('进程调度中，以下哪种算法会导致短作业优先？');
    expect(result).not.toContain('题目 1686572');
    expect(result).not.toContain('正确答案');
  });

  it('collapses a long stem to safe plain text and falls back without an internal id', () => {
    const longStem = '  题干第一行\n  题干第二行  ';
    expect(reviewRecommendationTitle(recommendation(), new Map([['52', longStem]])))
      .toBe('题干第一行 题干第二行');
    expect(reviewRecommendationTitle(recommendation(), new Map()))
      .toBe('待复习题目');
  });

  it.each([
    ['data_structure', '数据结构'],
    ['computer_organization', '计算机组成原理'],
    ['operating_system', '操作系统'],
    ['computer_network', '计算机网络'],
  ])('labels the 11408 module %s in Chinese', (module, label) => {
    expect(reviewDirectionLabel(recommendation({
      domain_context: { exam_module_id: module },
    }), undefined)).toBe(`11408 · ${label}`);
  });

  it('uses existing course and programming labels and safely hides unknown enums', () => {
    expect(reviewDirectionLabel(recommendation({
      service_namespace: 'course_learning',
      domain_context: { course_id: 'course-123' },
    }), { courses: [{ course_id: 'course-123', course_name: '离散数学' }] }))
      .toBe('专业学习 · 离散数学');
    expect(reviewDirectionLabel(recommendation({
      service_namespace: 'programming',
      domain_context: { language: 'python' },
    }), undefined)).toBe('编程 · Python');
    expect(reviewDirectionLabel(recommendation({
      service_namespace: 'exam_prep',
      domain_context: { exam_module_id: 'unknown_module' },
    }), undefined)).toBe('11408');
    expect(reviewDirectionLabel(recommendation({
      service_namespace: 'programming',
      domain_context: { language: 'unknown_language' },
    }), undefined)).toBe('编程');
  });
});
