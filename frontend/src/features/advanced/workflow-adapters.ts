import type { components } from '@/types/api';

export type DeepStudyInput = {
  question: string;
  courseId?: string;
  subjectKey?: string;
  chapterId?: string;
  knowledgePointId?: string;
  materialIds?: number[];
};

export type DeepStudyView = components['schemas']['DeepStudyResponse'];
export type AgentDebugView = components['schemas']['AgentDebugResponse'];
export type ReviewItemView = components['schemas']['ReviewItemView'];

export function toDeepStudyPayload(input: DeepStudyInput): components['schemas']['DeepStudyRequest'] {
  return {
    question: input.question,
    service_key: input.subjectKey ? 'exam_11408' : 'course_learning',
    course_id: input.courseId ?? '', subject_key: input.subjectKey ?? '',
    chapter_id: input.chapterId ?? '', knowledge_point_id: input.knowledgePointId ?? '',
    material_ids: input.materialIds ?? [],
  };
}

export function deepStudyKey(input: Pick<DeepStudyInput, 'question' | 'courseId' | 'subjectKey' | 'chapterId' | 'knowledgePointId' | 'materialIds'>) {
  return ['deep-study', input.courseId ?? '', input.subjectKey ?? '', input.chapterId ?? '', input.knowledgePointId ?? '', input.materialIds?.join(',') ?? '', input.question] as const;
}

export function toWorkflowSteps(steps: NonNullable<AgentDebugView['steps']>) {
  return [...steps].sort((left, right) => left.step_index - right.step_index);
}

export function toReviewItem(item: ReviewItemView) {
  return { ...item, dueLabel: item.due_at ? new Date(item.due_at).toLocaleDateString('zh-CN') : '待处理 / 未设日期' };
}
