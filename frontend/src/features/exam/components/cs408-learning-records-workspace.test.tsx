import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408LearningRecordsWorkspace } from './cs408-learning-records-workspace';

type LearningRecord = components['schemas']['RecordView'];

const hooks = vi.hoisted(() => ({ useCs408LearningRecords: vi.fn() }));
vi.mock('@/features/exam/api/learning-records', () => ({ useCs408LearningRecords: hooks.useCs408LearningRecords }));
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: globalThis.Record<string, string | undefined> }) => {
  const query = new URLSearchParams(); Object.entries(search ?? {}).forEach(([key, value]) => { if (value) query.set(key, value); });
  return <a href={`${to}${query.size ? `?${query}` : ''}`}>{children}</a>;
} }));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

const record = (event_id: string, occurred_at: string, event_type: string, summary: LearningRecord['summary'], module = 'operating_system'): LearningRecord => ({
  event_id, event_type, record_category: null, service_namespace: 'exam_prep', occurred_at, schema_version: 1,
  context: { exam_module_id: module, knowledge_point_id: null, course_id: null, subject_key: 'cs_408' },
  source: { type: 'practice_attempt', id: event_id, item_key: null }, summary,
});

describe('Cs408LearningRecordsWorkspace', () => {
  it('renders factual chronological records with browser-local date grouping and a cursor load-more control', async () => {
    const fetchNextPage = vi.fn();
    hooks.useCs408LearningRecords.mockReturnValue({ isPending: false, isError: false, data: { pages: [
      { records: [record('new', '2026-09-19T14:32:00+00:00', 'question_answered', { correct: true, score: 9 }), record('wrong', '2026-09-19T13:48:00+00:00', 'question_answered', { correct: false, score: null }), record('unknown', '2026-09-18T12:00:00+00:00', 'question_answered', { correct: null, score: null }), record('knowledge', '2026-09-18T11:00:00+00:00', 'knowledge_status_changed', { new_status: 'learning' })], next_cursor: 'opaque-cursor', has_more: true },
    ] }, hasNextPage: true, isFetchingNextPage: false, fetchNextPage, refetch: vi.fn() });
    render(<Cs408LearningRecordsWorkspace />);
    expect(screen.getByRole('heading', { name: '学习记录档案' })).toBeInTheDocument();
    expect(screen.getByText(/回答正确/)).toBeInTheDocument();
    expect(screen.getByText(/回答错误/)).toBeInTheDocument();
    expect(screen.getByText(/未作答 \/ 未判定/)).toBeInTheDocument();
    expect(screen.queryByText(/0 分/)).not.toBeInTheDocument();
    expect(screen.getByText('知识状态发生变化')).toBeInTheDocument();
    expect(screen.queryByText(/错题创建|错题解决|已订正|计划/)).not.toBeInTheDocument();
    expect(screen.queryByText('ai_called')).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: '加载更多' }));
    expect(fetchNextPage).toHaveBeenCalledOnce();
  });

  it('keeps module filtering server-side through the selected route search and has a restrained empty state', () => {
    hooks.useCs408LearningRecords.mockReturnValue({ isPending: false, isError: false, data: { pages: [{ records: [], next_cursor: null, has_more: false }] }, hasNextPage: false, isFetchingNextPage: false, fetchNextPage: vi.fn(), refetch: vi.fn() });
    render(<Cs408LearningRecordsWorkspace moduleKey="data_structure" />);
    expect(hooks.useCs408LearningRecords).toHaveBeenCalledWith('data_structure');
    expect(screen.getByRole('link', { name: '操作系统' })).toHaveAttribute('href', '/exam/cs408/records?module=operating_system');
    expect(screen.getByText('暂无学习记录')).toBeInTheDocument();
  });
});
