import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408WrongAnswerWorkspace } from './cs408-wrong-answer-workspace';

const records: components['schemas']['WrongAnswerRecord'][] = [
  { wrong_record_id: 7, status: 'active', service_namespace: 'exam_prep', module_key: 'operating_system', module_name: '操作系统', source_kind: 'past_paper', source_label: '历年真题', question_type: 'choice', stem: '某系统采用页式存储管理。', options: { A: 'A. 甲', B: '乙' }, user_answer: 'B', reference_answer: 'A', analysis: '页表项解析。', year: 2022, question_number: 46, question_bank_id: null, knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, resources: [{ url: '/exam/11408/past-paper-images/operating_system/2022/img_14.jpg' }], first_wrong_at: null, last_wrong_at: null, resolved_at: null, repeat_wrong_count: 2 },
  { wrong_record_id: 8, status: 'resolved', service_namespace: 'exam_prep', module_key: 'data_structure', module_name: '数据结构', source_kind: 'chapter_practice', source_label: '章节练习', question_type: 'choice', stem: '排序算法的稳定性是指什么？', options: { A: '甲', B: '乙' }, user_answer: 'A', reference_answer: 'B', analysis: null, year: null, question_number: null, question_bank_id: 42, knowledge_point_id: '1.1', knowledge_point_name: '排序', knowledge_point_path: '第一章 / 排序', resources: [], first_wrong_at: null, last_wrong_at: null, resolved_at: null, repeat_wrong_count: 1 },
  // A record whose question IS its figure: 「在下图所示的 5 阶 B 树 T 中」. Its text cannot carry
  // the tree, so the image stays — dropping it would leave the question unanswerable.
  { wrong_record_id: 9, status: 'active', service_namespace: 'exam_prep', module_key: 'data_structure', module_name: '数据结构', source_kind: 'past_paper', source_label: '历年真题', question_type: 'choice', stem: '在下图所示的 5 阶 B 树 T 中，删除关键字 260 之后……', options: { A: '60，90，280', B: '60，90，350' }, user_answer: 'B', reference_answer: 'A', analysis: null, year: 2022, question_number: 8, question_bank_id: null, knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, resources: [{ url: '/exam/11408/past-paper-images/data_structure/2022/img_7.jpg' }], first_wrong_at: null, last_wrong_at: null, resolved_at: null, repeat_wrong_count: 1 },
];
const refetch = vi.fn();
let empty = false;
vi.mock('@/features/exam/api/wrong-answers', () => ({
  useWrongAnswers: () => ({ data: { items: empty ? [] : records, total: empty ? 0 : 3, limit: 20, offset: 0 }, isPending: false, isError: false, refetch }),
}));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

describe('Cs408WrongAnswerWorkspace', () => {
  beforeEach(() => {
    empty = false;
    refetch.mockClear();
  });

  it('renders canonical factual statuses and expanded snapshots without legacy terminology', async () => {
    const user = userEvent.setup();
    const { container } = render(<QueryClientProvider client={new QueryClient()}><Cs408WrongAnswerWorkspace /></QueryClientProvider>);
    // 错题 is the tab above. The page opens on the ledger, and the only heading it keeps is
    // the region's own accessible name.
    expect(screen.getByRole('heading', { name: '错题' })).toHaveClass('sr-only');
    expect(screen.queryByText('CS408 / 错题')).not.toBeInTheDocument();
    expect(screen.queryByText('错题档案')).not.toBeInTheDocument();
    expect(screen.queryByText('学习过程中记下的错题')).not.toBeInTheDocument();
    expect(screen.getAllByText('未订正', { selector: '.wrong-answer__status' })).toHaveLength(2);
    expect(screen.getByText('已订正', { selector: '.wrong-answer__status' })).toBeInTheDocument();
    expect(screen.getByText(/历年真题 · 2022 · 第 46 题/)).toBeInTheDocument();
    expect(screen.queryByText(/掌握|复习次数/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '展开第 1 条错题记录' }));
    expect(screen.getAllByText('你的答案：B').length).toBeGreaterThan(0);
    expect(screen.getAllByText('正确答案：A').length).toBeGreaterThan(0);
    expect(screen.getByText('题目解析')).toBeInTheDocument();
    // The record's own 题干 and 选项 ARE the question, so the scan they were read from would
    // restate them. Same rule as 真题: it is not drawn.
    const detail = container.querySelector('.wrong-answer__detail') as HTMLElement;
    expect(detail).toHaveTextContent('某系统采用页式存储管理。');
    // The stored label is 「A. 甲」; the row draws the key itself, so the letter appears once.
    expect(detail).toHaveTextContent('甲');
    expect(detail).not.toHaveTextContent('A. 甲');
    expect(detail.querySelector('img')).toBeNull();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    // S8: the source link carries the record's own public question identity, so it opens
    // the paper AT the question the record is about rather than at question 1.
    expect(screen.getByRole('link', { name: '查看原真题第 46 题' })).toHaveAttribute('href', '/exam/cs408/past-papers?module=operating_system&year=2022&question=46');
  });

  it('keeps the figure for a record whose question is about one', async () => {
    const user = userEvent.setup();
    const { container } = render(<QueryClientProvider client={new QueryClient()}><Cs408WrongAnswerWorkspace /></QueryClientProvider>);
    await user.click(screen.getByRole('button', { name: '展开第 3 条错题记录' }));
    const detail = container.querySelector('.wrong-answer__detail') as HTMLElement;
    expect(detail).toHaveTextContent('在下图所示的 5 阶 B 树 T 中');
    expect(detail.querySelector('img')).toHaveAttribute('src', 'http://localhost:8000/exam/11408/past-paper-images/data_structure/2022/img_7.jpg');
    expect(screen.getByRole('link', { name: '查看原真题第 8 题' })).toHaveAttribute('href', '/exam/cs408/past-papers?module=data_structure&year=2022&question=8');
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
