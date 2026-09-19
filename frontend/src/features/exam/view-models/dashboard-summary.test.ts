import { describe, expect, it } from 'vitest';
import type { components } from '@/types/api';
import { toCs408ModuleViewModel } from './dashboard-summary';

type DashboardSummary = components['schemas']['ExamSubjectDashboardSummaryResponse'];

const summary: DashboardSummary = {
  subject_key: 'data_structure',
  subject_name: '数据结构',
  overview: {
    total_chapters: 12,
    total_knowledge_points: 86,
    learned_percent: 34,
    study_minutes: 45,
  },
  today_plan: [
    { id: 1, title: '复习线性表', knowledge_point_name: '线性表', task_type: 'knowledge', computed_status: 'in_progress', due_date: '2026-09-17' },
    { id: 2, title: '完成栈练习', knowledge_point_name: '', task_type: 'practice', computed_status: 'not_started', due_date: '' },
    { id: 3, title: '不应展示的任务', knowledge_point_name: '队列', task_type: 'knowledge', computed_status: 'not_started', due_date: '' },
  ],
  materials: { lecture_notes: 2, exercises: 1, references: 0, code_examples: 0, total_materials: 3 },
  quota: {
    ai_chat: { used: 0, limit: 1, remaining: 1, unit: '次' },
    ai_question: { used: 0, limit: 1, remaining: 1, unit: '次' },
    material_upload: { used: 0, limit: 100, remaining: 100, unit: 'MB' },
  },
};

describe('toCs408ModuleViewModel', () => {
  it('keeps only learning-relevant generated dashboard facts and the first two real tasks', () => {
    expect(toCs408ModuleViewModel(summary)).toEqual({
      subjectKey: 'data_structure',
      subjectName: '数据结构',
      learnedPercent: 34,
      totalChapters: 12,
      totalKnowledgePoints: 86,
      studyMinutes: 45,
      tasks: [
        { id: 1, title: '复习线性表', knowledgePointName: '线性表', status: '学习中', dueDate: '2026-09-17' },
        { id: 2, title: '完成栈练习', knowledgePointName: '', status: '未开始', dueDate: '' },
      ],
      isNew: false,
    });
  });

  it('treats an all-zero empty summary as a start state rather than a zero-metric dashboard', () => {
    const newUser = { ...summary, overview: { total_chapters: 12, total_knowledge_points: 86, learned_percent: 0, study_minutes: 0 }, today_plan: [] };

    expect(toCs408ModuleViewModel(newUser)).toMatchObject({
      isNew: true,
      tasks: [],
    });
  });
});
