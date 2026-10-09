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
  useSnoozeReviewRecommendation: vi.fn(),
  snoozeMutate: vi.fn(),
}));
vi.mock('@/features/review/recommendations-api', () => mockRecommendations);
import { ReviewPage } from '@/features/review/review-page';

describe('unified review recommendations', () => {
  it('shows real recommendation cards, filters, and no old manual completion controls', async () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({
      isPending: false,
      isError: false,
      data: { total: 1, items: [{ recommendation_key: 'key', title: '队列操作', direction: '专业学习 · 数据结构', reason: '已有复习计划已到期', action: { deep_link: '/course/数据结构/study?knowledge_point_id=12' } }] },
    });
    mockRecommendations.snoozeMutate.mockReset();
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: mockRecommendations.snoozeMutate, isPending: false, isSuccess: false });
    render(<ReviewPage />);
    for (const name of ['全部', '专业学习', '11408', '编程']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument();
    }
    expect(screen.getByText('今日建议 1 项')).toBeInTheDocument();
    expect(screen.getByText('已有复习计划已到期')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '开始复习' })).toHaveAttribute('href', expect.stringContaining('/course/'));
    expect(screen.queryByText(/三个方向的待复习/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /完成：/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '暂缓' }));
    expect(mockRecommendations.snoozeMutate).toHaveBeenCalledWith('key');
  });

  it('uses a minimal empty state when the real recommendation set is empty', () => {
    mockRecommendations.useReviewRecommendations.mockReturnValue({ isPending: false, isError: false, data: { total: 0, items: [] } });
    mockRecommendations.useSnoozeReviewRecommendation.mockReturnValue({ mutate: vi.fn(), isPending: false, isSuccess: false });
    render(<ReviewPage />);
    expect(screen.getByText('今日建议 0 项')).toBeInTheDocument();
    expect(screen.getByText('暂无建议')).toBeInTheDocument();
    expect(screen.queryByText(/换个范围看看/)).not.toBeInTheDocument();
  });
});
