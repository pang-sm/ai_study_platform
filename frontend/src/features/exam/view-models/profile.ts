import type { components } from '@/types/api';

type ProfileMinimum = Pick<components['schemas']['ExamPrepProfileResponse'], 'configured' | 'selected_subjects'>;
export type ProfileAction = '设置我的备考' | '编辑备考设置' | '进入 CS408';

export function profileAction(profile: ProfileMinimum): ProfileAction {
  if (!profile.configured) return '设置我的备考';
  return profile.selected_subjects.includes('cs_408') ? '进入 CS408' : '编辑备考设置';
}

export function isKnownExamSubject(subject: components['schemas']['ExamSubjectSummary'] | components['schemas']['UnknownExamSubject']): subject is components['schemas']['ExamSubjectSummary'] {
  return 'display_name' in subject;
}
