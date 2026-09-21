import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
vi.mock('@tanstack/react-router', () => ({
  createFileRoute: () => () => ({}),
  Link: ({ children }: { children: ReactNode }) => <a href="#review-link">{children}</a>,
}));
vi.mock('@/features/advanced/api/workflows', () => ({
  useReview: () => ({ isPending: false, isError: false, data: { items: [] } }),
  useReviewSummary: () => ({ isError: false, data: { total: 0, has_stored_due_dates: false } }),
}));
vi.mock('@/components/learning/p4-api', () => ({ useScheduleReviews: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false }), useCompleteReview: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false }) }));
import { ReviewPage } from '@/features/review/review-page';

describe('shared review', () => {
  it('keeps the three learning spaces as filters and an honest empty state', () => {
    render(<ReviewPage />);
    expect(screen.getByRole('button', { name: '全部' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '课程学习' })).toBeInTheDocument();
    expect(screen.getByText('暂无待处理复习')).toBeInTheDocument();
  });
});
