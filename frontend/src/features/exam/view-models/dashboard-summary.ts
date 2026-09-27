import type { components } from '@/types/api';

type DashboardSummary = components['schemas']['ExamSubjectDashboardSummaryResponse'];

const taskStatusLabels: Record<DashboardSummary['today_plan'][number]['computed_status'], string> = {
  not_started: '未开始',
  in_progress: '学习中',
  completed: '已完成',
};

export type Cs408ModuleViewModel = {
  subjectKey: string;
  subjectName: string;
  learnedPercent: number;
  totalChapters: number;
  totalKnowledgePoints: number;
  studyMinutes: number;
  tasks: Array<{ id: number; title: string; knowledgePointName: string; status: string; dueDate: string }>;
  isNew: boolean;
};

/**
 * One of the three states a paper can be in, in the learner's words.
 *
 * It is a reading of two facts the summary actually reports — how many knowledge points are marked
 * learned, and whether anything has been recorded at all — and nothing else. It is deliberately
 * not a score: the label says what has been worked through, never how well, and a paper with no
 * recorded work is 尚未开始 rather than 0%.
 */
export function toCs408ModuleStatus(summary: DashboardSummary): string {
  const view = toCs408ModuleViewModel(summary);
  if (view.isNew) return '尚未开始';
  return view.learnedPercent >= 100 ? '已学习' : '学习中';
}

export function toCs408ModuleViewModel(summary: DashboardSummary): Cs408ModuleViewModel {
  const { overview, today_plan: todayPlan } = summary;

  return {
    subjectKey: summary.subject_key,
    subjectName: summary.subject_name,
    learnedPercent: overview.learned_percent,
    totalChapters: overview.total_chapters,
    totalKnowledgePoints: overview.total_knowledge_points,
    studyMinutes: overview.study_minutes,
    tasks: todayPlan.slice(0, 2).map((task) => ({
      id: task.id,
      title: task.title,
      knowledgePointName: task.knowledge_point_name,
      status: taskStatusLabels[task.computed_status],
      dueDate: task.due_date,
    })),
    isNew: overview.learned_percent === 0 && overview.study_minutes === 0 && todayPlan.length === 0,
  };
}
