import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SubjectAvailabilityBadge } from '@/features/exam/components/subject-availability-badge';
import { normalizeApiError } from '@/features/exam/api/errors';
import { knowledgeStatusLabel, wrongResolutionLabel } from '@/features/exam/view-models/status-labels';
import { renderApp } from '@/test/render-app';

describe('Exam foundation primitives', () => {
  it('uses honest availability labels', () => {
    // "内容已开放" says what the catalogue flag actually states — real content exists — and not
    // "可学习", which would be this page claiming a study surface of its own.
    const { rerender } = render(<SubjectAvailabilityBadge availability="active" />);
    expect(screen.getByText('内容已开放')).toBeInTheDocument();
    expect(screen.getByText('内容已开放')).toHaveClass('bg-success-soft');

    rerender(<SubjectAvailabilityBadge availability="framework_only" />);
    expect(screen.getByText('内容建设中')).toBeInTheDocument();
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

  it('keeps the CS408 chooser route available while the papers it names have no summary yet', async () => {
    renderApp('/exam/cs408');

    expect(await screen.findByRole('heading', { name: '选择学习科目' })).toBeInTheDocument();
    // 408's front door asks one question and offers one strip of answers. The space-level
    // 我的备考 / 科目 bar is gone, and so is the tool strip here: the tools belong to a paper,
    // and no paper has been chosen yet.
    expect(screen.queryByRole('navigation', { name: 'CS408 工具导航' })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '考研学习导航' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /^数据结构/ })).toHaveAttribute(
      'href',
      '/exam/cs408/knowledge?module=data_structure',
    );
  });
});
