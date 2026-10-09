import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
  useCourseWrongAnswers: vi.fn(),
  useStartCourseQuestionAttempt: vi.fn(),
}));

vi.mock('@/features/course/api/course', () => hooks);

const settled = (data: unknown) => ({ isPending: false, isError: false, data });

describe('course wrong-answer redo action', () => {
  beforeEach(() => {
    hooks.useCourseCatalog.mockReturnValue(settled({ courses: [{ course_id: '数据结构', course_name: '数据结构' }] }));
    hooks.useCourseDashboard.mockReturnValue(settled({ course_name: '数据结构' }));
    hooks.useCourseWrongAnswers.mockReturnValue(settled({ items: [
      { wrong_record_id: 22, status: 'active', course_id: '数据结构', question_id: 314,
        stem: '栈的特点是什么？', user_answer: '先进先出', reference_answer: '后进先出' },
      { wrong_record_id: 23, status: 'active', course_id: '数据结构', question_id: null,
        stem: '缺少可重做身份的来源题', user_answer: '', reference_answer: '' },
    ], total: 2 }));
  });

  it('starts the existing course-scoped attempt and opens it in the practice player', async () => {
    const start = vi.fn((_input: unknown, options?: { onSuccess?: (result: unknown) => void }) => {
      options?.onSuccess?.({ attempt_id: 91 });
    });
    hooks.useStartCourseQuestionAttempt.mockReturnValue({ isPending: false, isError: false, mutate: start });
    const app = renderApp('/course/数据结构/wrong');

    await userEvent.click(await screen.findByRole('button', { name: '重做此题' }));

    expect(start).toHaveBeenCalledWith(
      { courseId: '数据结构', questionId: 314 },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    );
    await waitFor(() => expect(app.router.state.location.pathname).toBe('/course/数据结构/practice'));
    expect(app.router.state.location.search).toEqual({ session: 91 });
  });

  it('does not offer a fabricated redo action without a real question identity', async () => {
    hooks.useStartCourseQuestionAttempt.mockReturnValue({ isPending: false, isError: false, mutate: vi.fn() });
    renderApp('/course/数据结构/wrong');
    await screen.findByText('缺少可重做身份的来源题');
    expect(screen.getAllByRole('button', { name: '重做此题' })).toHaveLength(1);
  });
});
