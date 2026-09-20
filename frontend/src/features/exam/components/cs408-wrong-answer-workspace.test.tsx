import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408WrongAnswerWorkspace } from './cs408-wrong-answer-workspace';

const records: components['schemas']['WrongAnswerRecord'][] = [
  { wrong_record_id: 7, status: 'active', service_namespace: 'exam_prep', module_key: 'operating_system', module_name: '操作系统', source_kind: 'past_paper', source_label: '历年真题', question_type: 'choice', stem: '某系统采用页式存储管理。', options: { A: '甲', B: '乙' }, user_answer: 'B', reference_answer: 'A', analysis: '页表项解析。', year: 2022, question_number: 46, question_bank_id: null, knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, resources: [{ url: '/exam/11408/past-paper-images/operating_system/2022/img_14.jpg' }], first_wrong_at: null, last_wrong_at: null, resolved_at: null, repeat_wrong_count: 2 },
  { wrong_record_id: 8, status: 'resolved', service_namespace: 'exam_prep', module_key: 'data_structure', module_name: '数据结构', source_kind: 'chapter_practice', source_label: '章节练习', question_type: 'choice', stem: '排序算法的稳定性是指什么？', options: { A: '甲', B: '乙' }, user_answer: 'A', reference_answer: 'B', analysis: null, year: null, question_number: null, question_bank_id: 42, knowledge_point_id: '1.1', knowledge_point_name: '排序', knowledge_point_path: '第一章 / 排序', resources: [], first_wrong_at: null, last_wrong_at: null, resolved_at: null, repeat_wrong_count: 1 },
];
const refetch = vi.fn();
let empty = false;
vi.mock('@/features/exam/api/wrong-answers', () => ({
  useWrongAnswers: () => ({ data: { items: empty ? [] : records, total: empty ? 0 : 2, limit: 20, offset: 0 }, isPending: false, isError: false, refetch }),
}));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

describe('Cs408WrongAnswerWorkspace', () => {
  beforeEach(() => {
    empty = false;
    refetch.mockClear();
  });

  it('renders canonical factual statuses and expanded snapshots without legacy terminology', async () => {
    const user = userEvent.setup();
    render(<QueryClientProvider client={new QueryClient()}><Cs408WrongAnswerWorkspace /></QueryClientProvider>);
    expect(screen.getByRole('heading', { name: '错题档案' })).toBeInTheDocument();
    expect(screen.getByText('未订正', { selector: '.wrong-answer__status' })).toBeInTheDocument();
    expect(screen.getByText('已订正', { selector: '.wrong-answer__status' })).toBeInTheDocument();
    expect(screen.getByText(/历年真题 · 2022 · 第 46 题/)).toBeInTheDocument();
    expect(screen.queryByText(/掌握|复习次数/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '展开第 1 条错题记录' }));
    expect(screen.getByText('你的答案：B')).toBeInTheDocument();
    expect(screen.getByText('正确答案：A')).toBeInTheDocument();
    expect(screen.getByText('题目解析')).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute('src', 'http://localhost:8000/exam/11408/past-paper-images/operating_system/2022/img_14.jpg');
    // S8: the source link carries the record's own public question identity, so it opens
    // the paper AT the question the record is about rather than at question 1.
    expect(screen.getByRole('link', { name: '查看原真题第 46 题' })).toHaveAttribute('href', '/exam/cs408/past-papers?module=operating_system&year=2022&question=46');
  });

  it('links a chapter-practice record to its module, never to a chapter guessed from a title', async () => {
    const user = userEvent.setup();
    render(<QueryClientProvider client={new QueryClient()}><Cs408WrongAnswerWorkspace /></QueryClientProvider>);
    await user.click(screen.getByRole('button', { name: '展开第 2 条错题记录' }));
    // The record carries `knowledge_point_path` ('第一章 / 排序') and `knowledge_point_id`
    // ('1.1'), and NEITHER is a chapter identity the practice route accepts. The link
    // therefore states only what is canonical — the module.
    expect(screen.getByRole('link', { name: '进入本模块章节练习' })).toHaveAttribute('href', '/exam/cs408/practice?module=data_structure');
    expect(screen.queryByRole('link', { name: /原真题/ })).not.toBeInTheDocument();
  });

  it('uses the filter-specific factual empty copy', () => {
    empty = true;
    render(<QueryClientProvider client={new QueryClient()}><Cs408WrongAnswerWorkspace status="active" /></QueryClientProvider>);
    expect(screen.getByText('当前没有未订正错题')).toBeInTheDocument();
  });
});
