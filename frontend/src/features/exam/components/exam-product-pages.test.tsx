import { describe, expect, it } from 'vitest';
import { isKnownExamSubject, profileAction } from '@/features/exam/view-models/profile';

describe('Exam profile view models', () => {
  it('keeps the unknown stored-subject branch safe', () => {
    expect(isKnownExamSubject({ id: 'retired_subject', availability: 'unknown' })).toBe(false);
  });

  it('chooses only deterministic profile actions', () => {
    expect(profileAction({ configured: false, selected_subjects: [] })).toBe('设置我的备考');
    expect(profileAction({ configured: true, selected_subjects: ['math_1'] })).toBe('编辑备考设置');
    expect(profileAction({ configured: true, selected_subjects: ['cs_408'] })).toBe('进入 CS408');
  });
});
