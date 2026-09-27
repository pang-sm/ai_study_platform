import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408PastPaperWorkspace } from './cs408-past-paper-workspace';

const questions: components['schemas']['PastPaperQuestion'][] = [
  { subject_key: 'operating_system', year: 2022, question_number: 23, question_type: 'choice', stem: '进程调度的主要目标是（ ）。', options: { A: 'A. 提高吞吐量', B: '增加存储' }, resources: [], full_score: 2 },
  { subject_key: 'operating_system', year: 2022, question_number: 46, question_type: 'big', stem: '说明死锁的必要条件。', options: {}, resources: [{ url: '/exam/11408/past-paper-images/operating_system/2022/q46.jpg' }], full_score: 10 },
  // This one IS about its figure — 「如题 47 图所示」 — so its image is the question, not a copy of it.
  { subject_key: 'operating_system', year: 2022, question_number: 47, question_type: 'big', stem: '某网络拓扑如题 47 图所示，R 为路由器。', options: {}, resources: [{ url: '/exam/11408/past-paper-images/operating_system/2022/q47.jpg' }], full_score: 10 },
];
let attemptDetail: components['schemas']['PastPaperAttemptDetailResponse'] | undefined;
const create = vi.fn((_input: unknown, options?: { onSuccess?: (value: { attempt_id: number }) => void }) => {
  attemptDetail = { attempt: { id: 21, attempt_no: 1, subject_key: 'operating_system', year: 2022, status: 'in_progress', total_questions: 2, started_at: null, submitted_at: null }, questions, saved_answers: {} };
  options?.onSuccess?.({ attempt_id: 21 });
});
const save = vi.fn();
const submit = vi.fn((_input: unknown, options?: { onSuccess?: (value: components['schemas']['PastPaperSubmitResponse']) => void }) => options?.onSuccess?.({
  attempt_id: 21, attempt_no: 1, subject_key: 'operating_system', year: 2022, total_questions: 2, choice_total: 1, choice_correct: 1, self_review_count: 1, ai_graded_count: 0, total_score: 2, max_score: 12, answer_grade: { applied: false, reason: 'unavailable' },
  results: [
    { subject_key: 'operating_system', year: 2022, question_number: 23, question_type: 'choice', user_answer: 'A', correct: true, judge: null, standard_answer: 'A', analysis: null, score: 2, full_score: 2, feedback: null },
    { subject_key: 'operating_system', year: 2022, question_number: 46, question_type: 'big', user_answer: '四个条件', correct: null, judge: 'self_review', standard_answer: '互斥、占有且等待、不可抢占、循环等待。', analysis: null, score: null, full_score: 10, feedback: null },
  ],
}));

vi.mock('@/features/exam/api/past-paper', () => ({
  usePastPaperIndex: () => ({ data: { subject_key: 'operating_system', subject_name: '操作系统', papers: [{ year: 2022, question_count: 2, choice_count: 1, big_count: 1, source: 'bank' }] }, isPending: false, isError: false, refetch: vi.fn() }),
  usePastPaperQuestions: () => ({ data: { subject_key: 'operating_system', subject_name: '操作系统', year: 2022, source: 'bank', questions }, isPending: false, isError: false, refetch: vi.fn() }),
  usePastPaperAttempt: () => ({ data: attemptDetail, isPending: false, isError: false, refetch: vi.fn() }),
  useCreatePastPaperAttempt: () => ({ mutate: create, isPending: false, isError: false }),
  useSavePastPaperAnswers: () => ({ mutate: save, isPending: false, isError: false }),
  useSubmitPastPaper: () => ({ mutate: submit, isPending: false, isError: false }),
}));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

function renderWorkspace(props: Partial<React.ComponentProps<typeof Cs408PastPaperWorkspace>> = {}) {
  return render(<QueryClientProvider client={new QueryClient()}><Cs408PastPaperWorkspace moduleKey="operating_system" year={2022} {...props} /></QueryClientProvider>);
}

/**
 * The two strips exist so that exactly ONE is ever on screen: the left column above 40rem, the
 * drawer below it. jsdom applies no stylesheet, so both are mounted here and a bare
 * `getByRole('button', { name: '46' })` would match two. Scoping to the desktop column keeps the
 * assertion about what a desktop learner actually sees.
 */
const desktopQuestionButton = (container: HTMLElement, name: string) =>
  within(container.querySelector<HTMLElement>('.past-paper__navigator')!).getByRole('button', { name });

describe('Cs408PastPaperWorkspace', () => {
  beforeEach(() => { attemptDetail = undefined; create.mockClear(); save.mockClear(); });

  it('renders real dossier years and official public question numbers without source branches', async () => {
    const { rerender } = renderWorkspace({ year: undefined });
    // The tab strip above already says 真题. The page name survives only as the region's
    // accessible name, so the year list is what the body actually opens on.
    expect(screen.getByRole('heading', { name: '真题' })).toHaveClass('sr-only');
    expect(screen.queryByText('选择真实年份试卷')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '选择年份' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /2022/ })).toHaveAttribute('href', '/exam/cs408/past-papers?module=operating_system&year=2022');
    rerender(<QueryClientProvider client={new QueryClient()}><Cs408PastPaperWorkspace moduleKey="operating_system" year={2022} /></QueryClientProvider>);
    expect(screen.getByText('第 23 题')).toBeInTheDocument();
    expect(screen.queryByText(/standard_answer|bank|document/)).not.toBeInTheDocument();
  });

  it('states which paper is open without repeating the tool name as a headline', () => {
    renderWorkspace();
    // The year is the one thing the tab cannot say, so it stays — as context, not a title.
    expect(screen.getByText('2022 年全国硕士研究生招生考试')).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { name: '真题' })).toHaveLength(1);
    expect(screen.getByRole('heading', { name: '真题' })).toHaveClass('sr-only');
  });

  it('draws a printed option letter once, without touching the stored label', () => {
    renderWorkspace();
    // The paper wrote this option the way it is printed inline ("A. 提高吞吐量"). The row already
    // draws the key, so the repeated letter is dropped from the DISPLAY only.
    expect(screen.getByText('提高吞吐量')).toBeInTheDocument();
    expect(screen.queryByText('A. 提高吞吐量')).not.toBeInTheDocument();
    // A label that does not repeat its own key is left exactly as it came.
    expect(screen.getByText('增加存储')).toBeInTheDocument();
  });

  it('saves by official question number, submits without frontend grading, and renders self review', async () => {
    const user = userEvent.setup();
    const { container } = renderWorkspace();
    await user.click(screen.getByRole('radio', { name: /提高吞吐量/ }));
    await user.click(screen.getByRole('button', { name: '开始作答' }));
    expect(create).toHaveBeenCalledWith({ moduleKey: 'operating_system', year: 2022 }, expect.anything());
    await user.click(screen.getByRole('button', { name: '保存答案' }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ answers: { '23': 'A' } }));
    await user.click(screen.getByRole('button', { name: '提交答卷' }));
    expect(screen.getByRole('heading', { name: '本次答卷' })).toBeInTheDocument();
    expect(screen.queryByText(/50%|5\s*\/\s*10|自动评分/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '查看答题纸' }));
    await user.click(desktopQuestionButton(container, '46'));
    expect(screen.getByText('自行复盘')).toBeInTheDocument();
    expect(screen.getByText('参考答案')).toBeInTheDocument();
    // Q46 carries a real resolvable figure. The stem and the answer are what the learner reads;
    // the source screenshot of the same question is not drawn, and nothing is derived from it.
    expect(screen.getByText('说明死锁的必要条件。')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('draws the figure only for a question that is about one', async () => {
    const user = userEvent.setup();
    const { container } = renderWorkspace();
    // Q46 is answerable from its text, so its scan is not drawn.
    expect(container.querySelectorAll('.past-paper-question__figure')).toHaveLength(0);
    await user.click(desktopQuestionButton(container, '47'));
    // Q47 says 「如题 47 图所示」. Without the topology the question cannot be answered at all, so
    // the figure is the question — and it is drawn.
    expect(screen.getByText('某网络拓扑如题 47 图所示，R 为路由器。')).toBeInTheDocument();
    expect(container.querySelectorAll('.past-paper-question__figure')).toHaveLength(1);
    expect(screen.getByRole('img')).toHaveAttribute('src', 'http://localhost:8000/exam/11408/past-paper-images/operating_system/2022/q47.jpg');
  });

  it('gives a narrow screen the current position and a way to reach any question', async () => {
    const user = userEvent.setup();
    const { container } = renderWorkspace();
    const drawer = container.querySelector('.past-paper__nav-drawer') as HTMLDetailsElement;
    // The desktop strip is a permanent left column that cannot exist at 390px; this is what
    // replaces it there, and it stays out of the way above 40rem (see the stylesheet).
    expect(drawer.querySelector('summary')).toHaveTextContent('第 1 / 3 题');
    expect(drawer.querySelector('summary')).toHaveTextContent('题号');
    const buttons = [...drawer.querySelectorAll('.past-paper__nav-drawer-list button')];
    expect(buttons.map((button) => button.textContent)).toEqual(['23', '46', '47']);
    expect(buttons[0]).toHaveAttribute('aria-current', 'step');

    await user.click(buttons[1]!);
    // The paper's own number is the label, and the picker closes on the question it was opened for.
    expect(screen.getByText('第 46 题')).toBeInTheDocument();
    expect(drawer.open).toBe(false);
    expect(buttons[1]).toHaveAttribute('aria-current', 'step');
  });

  it('rehydrates submitted answers and remains reviewable after refresh', async () => {
    attemptDetail = { attempt: { id: 21, attempt_no: 1, subject_key: 'operating_system', year: 2022, status: 'submitted', total_questions: 2, started_at: null, submitted_at: null }, questions, saved_answers: { '23': 'A', '46': '四个条件' }, results: [
      { subject_key: 'operating_system', year: 2022, question_number: 23, question_type: 'choice', user_answer: 'A', correct: false, judge: null, standard_answer: 'B', analysis: null, score: 0, full_score: 2, feedback: null },
      { subject_key: 'operating_system', year: 2022, question_number: 46, question_type: 'big', user_answer: '四个条件', correct: null, judge: 'self_review', standard_answer: '参考答案', analysis: null, score: null, full_score: 10, feedback: null },
    ] };
    const user = userEvent.setup();
    renderWorkspace({ attemptId: 21 });
    expect(screen.getByRole('heading', { name: '本次答卷' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '查看答题纸' }));
    expect(screen.getByRole('radio', { name: /提高吞吐量/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /提高吞吐量/ })).toBeDisabled();
    expect(screen.getByText('回答错误')).toBeInTheDocument();
  });
});
