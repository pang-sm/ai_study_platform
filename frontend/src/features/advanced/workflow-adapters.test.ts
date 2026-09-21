import { describe, expect, it } from 'vitest';
import { deepStudyKey, toDeepStudyPayload, toReviewItem, toWorkflowSteps } from './workflow-adapters';

describe('P3A generated-contract adapters', () => {
  it('builds a deep-study request with its real course context and course-isolated key', () => {
    expect(toDeepStudyPayload({ question: '解释页表', courseId: 'os', materialIds: [9] })).toEqual({
      question: '解释页表', service_key: 'course_learning', course_id: 'os', subject_key: '', chapter_id: '', knowledge_point_id: '', material_ids: [9],
    });
    expect(deepStudyKey({ question: '解释页表', courseId: 'os' })).not.toEqual(deepStudyKey({ question: '解释页表', courseId: 'ds' }));
  });

  it('keeps only backend-returned citation refs and preserves agent step order', () => {
    const citations = [{ material_id: 4, filename: 'memory.pdf', subject: 'OS', file_type: 'pdf', snippet: '页表' }];
    expect(citations.map((citation) => citation.filename)).toEqual(['memory.pdf']);
    expect(toWorkflowSteps([{ step_index: 2, action: 'test', status: 'completed', file_type: 'test', snippet: 'after' }, { step_index: 1, action: 'diagnosis', status: 'completed', file_type: 'analysis', snippet: 'before' }]).map((step) => step.action)).toEqual(['diagnosis', 'test']);
  });

  it('does not invent a review due date', () => {
    expect(toReviewItem({ id: 'p:1', service_namespace: 'programming', domain_context: {}, source_type: 'needs_work', source_id: '1', title: '修复', summary: '', review_status: 'needs_attention', due_at: null, reason: '测试失败', deep_link: '/programming/python/errors' }).dueLabel).toBe('待处理 / 未设日期');
  });
});
