import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('@tanstack/react-router', () => ({
  createFileRoute: () => () => ({}),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const mockRecommendations = vi.hoisted(() => ({
  useReviewRecommendations: vi.fn(),
  useReviewQuestionStems: vi.fn(),
  useSnoozeReviewRecommendation: vi.fn(),
  snoozeMutate: vi.fn(),
}));
vi.mock('@/features/review/recommendations-api', () => mockRecommendations);
const mockCourseCatalog = vi.hoisted(() => ({ useCourseCatalog: vi.fn() }));
vi.mock('@/features/course/api/course', async (importOriginal) => ({
  ...await importOriginal(),
  ...mockCourseCatalog,
}));
import { ReviewPage } from '@/features/review/review-page';

describe('unified review recommendations', () => {
  it('shows real recommendation cards, filters, and no old manual completion controls', async () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({
      isPending: false,
      isError: false,
      data: { total: 1, items: [{ recommendation_key: 'key', kind: 'knowledge', service_namespace: 'course_learning', domain_context: { course_id: 'discrete-math' }, title: '队列操作', direction: '专业学习 · discrete-math', reason: '已有复习计划已到期', evidence: {}, action: { deep_link: '/course/数据结构/study?knowledge_point_id=12' } }] },
    });
    mockRecommendations.useReviewQuestionStems.mockReturnValue({ data: new Map() });
    mockCourseCatalog.useCourseCatalog.mockReturnValue({ data: { courses: [{ course_id: 'discrete-math', course_name: '离散数学' }] } });
    mockRecommendations.snoozeMutate.mockReset();
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: mockRecommendations.snoozeMutate, isPending: false, isSuccess: false });
    render(<ReviewPage />);
    for (const name of ['全部', '专业学习', '11408', '编程']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByText('今日建议 1 项')).toBeInTheDocument();
    expect(screen.getByText('已有复习计划已到期')).toBeInTheDocument();
    expect(screen.getByText('专业学习 · 离散数学')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '开始复习' })).toHaveAttribute('href', expect.stringContaining('/course/'));
    expect(screen.queryByText(/三个方向的待复习/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /完成：/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '暂缓' }));
    expect(mockRecommendations.snoozeMutate).toHaveBeenCalledWith('key');
  });

  it('uses a minimal empty state when the real recommendation set is empty', () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({ isPending: false, isError: false, data: { total: 0, items: [] } });
    mockRecommendations.useReviewQuestionStems.mockReturnValue({ data: new Map() });
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: vi.fn(), isPending: false, isSuccess: false });
    mockCourseCatalog.useCourseCatalog.mockReturnValue({ data: undefined });
    render(<ReviewPage />);
    expect(screen.getByText('今日建议 0 项')).toBeInTheDocument();
    expect(screen.getByText('暂无建议')).toBeInTheDocument();
    expect(screen.queryByText(/换个范围看看/)).not.toBeInTheDocument();
  });

  it('renders real question stems, hides the placeholder id, and keeps answer fields out of the card', () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({
      isPending: false,
      isError: false,
      data: { total: 1, items: [{ recommendation_key: 'question-key', kind: 'question', service_namespace: 'exam_prep', domain_context: { exam_module_id: 'operating_system' }, title: '题目 1686572', direction: '11408 · operating_system', reason: '这道题有一次尚未订正的真实错误', reason_code: 'single_wrong', evidence: { source_id: '52' }, action: { deep_link: '/exam/cs408/wrong?module=operating_system' } }] },
    });
    mockRecommendations.useReviewQuestionStems.mockReturnValue({ data: new Map([
      ['52', '进程调度时，先运行预计执行时间最短的就绪进程。'],
    ]) });
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: vi.fn(), isPending: false });
    mockCourseCatalog.useCourseCatalog.mockReturnValue({ data: undefined });

    const { container } = render(<ReviewPage />);
    const title = screen.getByRole('heading', { name: '进程调度时，先运行预计执行时间最短的就绪进程。' });
    expect(title).toHaveClass('line-clamp-2');
    expect(screen.getByText('11408 · 操作系统')).toBeInTheDocument();
    expect(screen.queryByText('题目 1686572')).not.toBeInTheDocument();
    expect(container.textContent).not.toContain('正确答案');
    expect(screen.getByRole('link', { name: '开始复习' })).toHaveAttribute('href', '/exam/cs408/wrong?module=operating_system');
  });

  it('uses a short honest fallback when a question stem is unavailable and keeps cards compact', () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({
      isPending: false,
      isError: false,
      data: { total: 2, items: [
        { recommendation_key: 'missing-stem', kind: 'question', service_namespace: 'exam_prep', domain_context: { exam_module_id: 'computer_network' }, title: '题目 1686572', direction: '11408 · computer_network', reason_code: 'single_wrong', reason: '这道题有一次尚未订正的真实错误', evidence: { source_id: '99' }, action: { deep_link: '/exam/cs408/wrong?module=computer_network' } },
        { recommendation_key: 'programming-item', kind: 'programming_exercise', service_namespace: 'programming', domain_context: { language: 'python' }, title: '数组窗口中的最大值', direction: '编程 · python', reason_code: 'programming_single_failure', reason: '最近一次真实提交未通过', evidence: {}, action: { deep_link: '/programming/workbench?language=Python&exercise=3' } },
      ] },
    });
    mockRecommendations.useReviewQuestionStems.mockReturnValue({ data: new Map() });
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: vi.fn(), isPending: false });
    mockCourseCatalog.useCourseCatalog.mockReturnValue({ data: undefined });

    const { container } = render(<ReviewPage />);
    expect(screen.getByText('待复习题目')).toBeInTheDocument();
    expect(screen.queryByText('题目 1686572')).not.toBeInTheDocument();
    expect(screen.getByText('11408 · 计算机网络')).toBeInTheDocument();
    expect(screen.getByText('编程 · Python')).toBeInTheDocument();
    expect(container.querySelector('ol')).toHaveClass('space-y-3');
    expect(screen.getAllByRole('link', { name: '开始复习' })).toHaveLength(2);
  });

  it('loads stems in one bounded batch only when a generic question title needs it', () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({
      isPending: false,
      isError: false,
      data: { total: 0, items: [] },
    });
    mockRecommendations.useReviewQuestionStems.mockReturnValue({ data: new Map() });
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: vi.fn(), isPending: false });
    mockCourseCatalog.useCourseCatalog.mockReturnValue({ data: undefined });
    render(<ReviewPage />);
    expect(mockRecommendations.useReviewQuestionStems).toHaveBeenCalledWith(false);
    expect(mockCourseCatalog.useCourseCatalog).toHaveBeenCalledWith(false);
  });
});
