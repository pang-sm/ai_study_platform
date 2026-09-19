export type KnowledgeStatus = 'not_started' | 'learning' | 'mastered' | 'review_due';

const knowledgeLabels: Record<KnowledgeStatus, string> = {
  not_started: '未学习',
  learning: '学习中',
  mastered: '已学习',
  review_due: '待复习',
};

export function knowledgeStatusLabel(status: KnowledgeStatus): string {
  return knowledgeLabels[status];
}

export type ProgressStatus = 'not_started' | 'learning' | 'completed';

const progressLabels: Record<ProgressStatus, string> = {
  not_started: '未开始',
  learning: '学习中',
  completed: '已完成',
};

export function progressStatusLabel(status: ProgressStatus): string {
  return progressLabels[status];
}

export type TaskStatus = 'not_started' | 'in_progress' | 'completed';

const taskLabels: Record<TaskStatus, string> = {
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
};

export function taskStatusLabel(status: TaskStatus): string {
  return taskLabels[status];
}

export function wrongResolutionLabel(resolved: boolean): string {
  return resolved ? '已解决' : '待复习';
}
