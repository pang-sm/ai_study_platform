import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { describe, expect, it } from 'vitest';
import { SubjectAvailabilityBadge } from '@/features/exam/components/subject-availability-badge';
import { ContentUnavailableState } from '@/features/exam/components/content-unavailable-state';
import { normalizeApiError } from '@/features/exam/api/errors';
import { knowledgeStatusLabel, wrongResolutionLabel } from '@/features/exam/view-models/status-labels';
import { renderApp } from '@/test/render-app';

function renderUnavailable(subjectName: string, selected = false) {
  const router = createRouter({
    routeTree: createRootRoute({ component: () => <ContentUnavailableState subjectName={subjectName} selected={selected} /> }),
    history: createMemoryHistory(),
  });
  return render(<RouterProvider router={router} />);
}

describe('Exam foundation primitives', () => {
  it('marks the active Exam context route accessibly', async () => {
    renderApp('/exam/subjects');

    expect(await screen.findByRole('navigation', { name: '考研学习导航' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '科目' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: '我的备考' })).not.toHaveAttribute('aria-current');
    expect(screen.getByText('考研学习', { selector: 'p' })).toBeInTheDocument();
    expect(screen.queryByText(/EXAM PREPARATION/)).not.toBeInTheDocument();
    expect(screen.queryByText(/A BRIGHTER YOU TOMORROW/)).not.toBeInTheDocument();
  });

  it('uses honest availability labels', () => {
    const { rerender } = render(<SubjectAvailabilityBadge availability="active" />);
    expect(screen.getByText('可学习')).toBeInTheDocument();
    expect(screen.getByText('可学习')).toHaveClass('text-emerald-800');

    rerender(<SubjectAvailabilityBadge availability="framework_only" />);
    expect(screen.getByText('内容建设中')).toBeInTheDocument();
  });

  it('renders the dedicated unavailable-content state without fake learning data', async () => {
    renderUnavailable('该科目');

    expect(await screen.findByRole('heading', { name: '该科目内容建设中' })).toBeInTheDocument();
    expect(screen.getByText('已开放加入我的备考，学习内容将后续开放。')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '返回科目' })).toHaveAttribute('href', '/exam/subjects');
  });

  it('states the subject relationship when framework-only content is already selected', async () => {
    renderUnavailable('数学（一）', true);

    expect(await screen.findByText('这门科目已加入你的备考范围。')).toBeInTheDocument();
  });

  it('normalizes structured and string backend details without leaking internals', () => {
    expect(normalizeApiError(409, {
      code: 'EXAM_CONTENT_NOT_AVAILABLE',
      subject_id: 'math_1',
      message: '该科目已开放选择，但内容尚未上线。',
    }).kind).toBe('content_unavailable');

    expect(normalizeApiError(403, 'AI capability unavailable')).toMatchObject({
      kind: 'capability_required',
      message: '当前功能需要升级后使用。',
    });

    expect(normalizeApiError(409, { detail: { code: 'EXAM_CONTENT_NOT_AVAILABLE' } }).kind).toBe('content_unavailable');

    expect(normalizeApiError(429, 'quota key: exam_11408')).toMatchObject({
      kind: 'usage_exhausted',
      message: '本次额度已用完，请稍后再试。',
    });
  });

  it('keeps knowledge and wrong-answer terminology distinct', () => {
    expect(knowledgeStatusLabel('not_started')).toBe('未学习');
    expect(knowledgeStatusLabel('learning')).toBe('学习中');
    expect(knowledgeStatusLabel('mastered')).toBe('已学习');
    expect(knowledgeStatusLabel('review_due')).toBe('待复习');
    expect(wrongResolutionLabel(true)).toBe('已解决');
  });

  it('keeps the CS408 workspace route available while module summaries load independently', async () => {
    renderApp('/exam/cs408');

    expect(await screen.findByRole('heading', { name: '学习工作区' })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'CS408 工具导航' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '数据结构' })).toBeInTheDocument();
  });
});
