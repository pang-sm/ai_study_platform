/**
 * ACCEL_PRODUCT_S8 — the cross-workspace links, and the ones that are deliberately absent.
 *
 * The rule this file enforces: a deep link is built from a canonical id the source surface
 * ACTUALLY carries. A link that would have to be guessed from a display title is not
 * rendered at all, and the tests that pin an absent link are as load-bearing as the ones
 * that pin a present one — otherwise "no link" and "a link nobody wrote" look the same.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));
// The records workspace navigates with the router's `<Link>`; every other surface here uses
// a plain anchor. Rendering `Link` without a router context throws, so it is mapped to the
// anchor it produces rather than the whole file being wrapped in a RouterProvider.
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: globalThis.Record<string, string | undefined> }) => {
  const query = new URLSearchParams(); Object.entries(search ?? {}).forEach(([key, value]) => { if (value) query.set(key, value); });
  return <a href={`${to}${query.size ? `?${query}` : ''}`}>{children}</a>;
} }));

// ---------------------------------------------------------------- past papers

type PaperQuestion = components['schemas']['PastPaperQuestion'];
type PaperResult = components['schemas']['PastPaperQuestionResult'];

const paperQuestions: PaperQuestion[] = [1, 2, 3].map((number) => ({
  subject_key: 'data_structure', year: 2022, question_number: number,
  question_type: 'choice' as const, stem: `第 ${number} 题的题干`,
  options: { A: '甲', B: '乙' }, resources: [],
}));

let attemptDetail: components['schemas']['PastPaperAttemptDetailResponse'] | undefined;

vi.mock('@/features/exam/api/past-paper', () => ({
  usePastPaperIndex: () => ({ data: { subject_key: 'data_structure', subject_name: '数据结构', papers: [{ year: 2022, question_count: 3, choice_count: 3, big_count: 0, source: 'local' }] }, isPending: false, isError: false, refetch: vi.fn() }),
  usePastPaperQuestions: () => ({ data: { subject_key: 'data_structure', year: 2022, questions: paperQuestions }, isPending: false, isError: false, refetch: vi.fn() }),
  usePastPaperAttempt: () => ({ data: attemptDetail, isPending: false, isError: false, refetch: vi.fn() }),
  useCreatePastPaperAttempt: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useSavePastPaperAnswers: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useSubmitPastPaper: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

import { Cs408PastPaperWorkspace } from './cs408-past-paper-workspace';

function renderWithClient(node: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);
}

describe('Cs408PastPaperWorkspace deep links', () => {
  beforeEach(() => { attemptDetail = undefined; });

  it('opens the paper AT the question a deep link names, matched by its own identity', () => {
    renderWithClient(<Cs408PastPaperWorkspace moduleKey="data_structure" year={2022} questionNumber={3} />);
    expect(screen.getByText('第 3 题')).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /甲/ })).toBeInTheDocument();
  });

  it('does not clamp an unknown question number onto question 1', () => {
    // A silent fallback would make a broken link look like a working one.
    renderWithClient(<Cs408PastPaperWorkspace moduleKey="data_structure" year={2022} questionNumber={99} />);
    expect(screen.getByText('第 1 题')).toBeInTheDocument();
  });

  it('renders an attempt on its own, without the paper year being addressed first', () => {
    attemptDetail = {
      attempt: { id: 21, attempt_no: 1, subject_key: 'data_structure', year: 2022, status: 'submitted', total_questions: 3, started_at: null, submitted_at: null },
      questions: paperQuestions, saved_answers: {},
      results: paperQuestions.map((question) => ({ question_number: question.question_number, user_answer: 'A', standard_answer: 'A', correct: true, judge: undefined, score: null, full_score: null, feedback: null, analysis: null })) as unknown as PaperResult[],
    };
    renderWithClient(<Cs408PastPaperWorkspace moduleKey="data_structure" attemptId={21} />);
    expect(screen.getByRole('heading', { name: '本次答卷' })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- practice → wrong

let submitResults: components['schemas']['ExamPracticeSubmitResponse']['results'] = [];

vi.mock('@/features/exam/api/chapter-practice', () => ({
  useChapterPracticeOutline: () => ({ data: { subject_key: 'data_structure', knowledge_points: {}, total: 1, chapters: [{ chapter_code: '1', chapter_no: 1, chapter_title: '线性表', question_count: 1 }] }, isPending: false, isError: false, refetch: vi.fn() }),
  useChapterPracticeQuestions: () => ({ data: { items: [{ id: 11, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 1, question_type: 'choice', stem: '题干', options: { A: '甲', B: '乙' }, difficulty: null, quality_status: null, created_at: null, practiced: false }], total: 1 }, isPending: false, isError: false, refetch: vi.fn() }),
  useChapterPracticeAttempt: () => ({ data: undefined, isPending: false, isError: false, refetch: vi.fn() }),
  useCreateChapterPracticeAttempt: () => ({ mutate: (_input: unknown, options?: { onSuccess?: (value: { attempt_id: number }) => void }) => options?.onSuccess?.({ attempt_id: 91 }), isPending: false, isError: false }),
  useSaveChapterPracticeAnswers: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
  useSubmitChapterPractice: () => ({ mutate: (_input: unknown, options?: { onSuccess?: (value: components['schemas']['ExamPracticeSubmitResponse']) => void }) => options?.onSuccess?.({ total_questions: 1, choice_total: 1, big_count: 0, correct_count: 0, wrong_count: 1, accuracy: 0, mistake_saved_count: 1, results: submitResults }), isPending: false, isError: false }),
}));
vi.mock('@/features/exam/api/question-explain', () => ({ useQuestionExplain: () => ({ mutate: vi.fn(), isPending: false }) }));

import { Cs408PracticeWorkspace } from './cs408-practice-workspace';

describe('Cs408PracticeWorkspace → Wrong Answers', () => {
  it('offers the wrong-answer book only when the session actually produced wrong answers', async () => {
    submitResults = [{ question_id: 11, correct: false, standard_answer: 'B', user_answer: 'A', stem: '题干', options: { A: '甲', B: '乙' }, analysis: '', question_type: 'choice' }] as unknown as components['schemas']['ExamPracticeSubmitResponse']['results'];
    const user = userEvent.setup();
    renderWithClient(<Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" />);
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    await user.click(screen.getByRole('radio', { name: /乙/ }));
    await user.click(screen.getByRole('button', { name: '提交本章答案' }));
    expect(screen.getByRole('link', { name: '去错题本订正' })).toHaveAttribute('href', '/exam/cs408/wrong?module=data_structure&status=active');
  });

  it('omits it entirely when nothing was answered incorrectly', async () => {
    submitResults = [{ question_id: 11, correct: true, standard_answer: 'A', user_answer: 'A', stem: '题干', options: { A: '甲', B: '乙' }, analysis: '', question_type: 'choice' }] as unknown as components['schemas']['ExamPracticeSubmitResponse']['results'];
    const user = userEvent.setup();
    renderWithClient(<Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" />);
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    await user.click(screen.getByRole('radio', { name: /甲/ }));
    await user.click(screen.getByRole('button', { name: '提交本章答案' }));
    expect(screen.queryByRole('link', { name: '去错题本订正' })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- records → source

vi.mock('@/features/exam/api/learning-records', () => ({
  useCs408LearningRecords: () => ({
    data: {
      pages: [{
        records: [
          { event_id: 'e1', event_type: 'question_answered', service_namespace: 'exam_prep', occurred_at: null, context: { exam_module_id: 'data_structure' }, source: { type: 'exam_practice_attempt', id: '91', item_key: '11:0' }, summary: { correct: true } },
          { event_id: 'e2', event_type: 'question_answered', service_namespace: 'exam_prep', occurred_at: null, context: { exam_module_id: 'operating_system' }, source: { type: 'past_paper_attempt', id: '21', item_key: '46:0' }, summary: { correct: false } },
          // No source id: a fact whose producer did not record one. It must render WITHOUT
          // a link rather than borrow a nearby id.
          { event_id: 'e3', event_type: 'knowledge_status_changed', service_namespace: 'exam_prep', occurred_at: null, context: { exam_module_id: 'data_structure' }, source: { type: 'knowledge_point', id: null }, summary: {} },
        ],
        next_cursor: null,
        has_more: false,
      }],
    },
    isPending: false, isError: false, hasNextPage: false, isFetchingNextPage: false, fetchNextPage: vi.fn(),
  }),
}));

import { Cs408LearningRecordsWorkspace } from './cs408-learning-records-workspace';

describe('Cs408LearningRecordsWorkspace → source', () => {
  it('links each record to the attempt that produced it', () => {
    renderWithClient(<Cs408LearningRecordsWorkspace />);
    expect(screen.getByRole('link', { name: '查看本次练习' })).toHaveAttribute('href', '/exam/cs408/practice?module=data_structure&attempt=91');
    expect(screen.getByRole('link', { name: '查看本次答卷' })).toHaveAttribute('href', '/exam/cs408/past-papers?module=operating_system&attempt=21');
  });

  it('renders no link for a record that carries no source id', () => {
    renderWithClient(<Cs408LearningRecordsWorkspace />);
    // The module filter nav renders links too, so scope the check to the timeline rows.
    const rows = screen.getAllByRole('listitem');
    const withoutSource = rows.find((row) => row.textContent?.includes('知识学习'));
    expect(withoutSource).toBeDefined();
    expect(withoutSource!.querySelector('a')).toBeNull();
    expect(rows.filter((row) => row.querySelector('.learning-records__source'))).toHaveLength(2);
  });
});

// ---------------------------------------------------------------- locked plan (PART 13)

vi.mock('@/features/exam/api/cs408-study-plan', () => ({
  useExamPlanEntitlement: () => ({ data: { service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1', features: { learning_plan: { allowed: false, required_tier: 'standard', required_capability: 'planning.generate' } } }, isPending: false, isError: false, refetch: vi.fn() }),
  useCs408StudyPlans: () => [],
}));

import { Cs408StudyPlanWorkspace } from './cs408-study-plan-workspace';

describe('Cs408StudyPlanWorkspace locked state', () => {
  // ACCEL_PRODUCT_S9 PART H RETIRED THE OLD ASSERTION. S8 pinned "no link is rendered"
  // because no membership route existed; a canonical one now does, so the locked state
  // points at it and the dead-end behaviour is gone. The requirement is still stated in
  // terms of the value the entitlement endpoint returns — never invented.
  //
  // ACCEL_PRODUCT_S10 made that value a UNIFIED TIER, so the sentence names `Standard`
  // rather than describing a plan code in words.
  it('states the tier requirement and points at the canonical membership route', () => {
    renderWithClient(<Cs408StudyPlanWorkspace />);
    expect(screen.getByText('学习计划需要 Standard 及以上档位，当前账号尚未开通。')).toBeInTheDocument();
    const link = screen.getByRole('link', { name: '查看会员档位与权益' });
    expect(link).toHaveAttribute('href', '/membership');
    // No legacy plan code anywhere: the entitlement contract no longer carries one.
    expect(screen.queryByText(/monthly_sprint|备考方案/)).not.toBeInTheDocument();
    // still no fake action: the only control is navigation, not a purchase that cannot finish
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- accessibility debt (PART 14)

describe('past-paper error text contrast', () => {
  it('uses the text-safe danger token instead of the fill token', () => {
    const dir = resolve(__dirname);
    const pastPaper = readFileSync(resolve(dir, 'cs408-past-paper-workspace.css'), 'utf8');
    const practice = readFileSync(resolve(dir, 'cs408-practice-workspace.css'), 'utf8');
    const errorRule = /\.past-paper__error\s*\{([^}]*)\}/.exec(pastPaper)?.[1] ?? '';
    expect(errorRule).toContain('--color-danger-ink');
    expect(errorRule).not.toContain('--color-danger;');
    expect(practice).toContain('var(--color-danger-ink)');

    // and the base token is untouched, so no frozen fill or inset accent moved
    const tokens = readFileSync(resolve(dir, '../../../styles/tokens.css'), 'utf8');
    expect(tokens).toContain('--color-danger: #dc2626;');
    expect(tokens).toContain('--color-danger-ink: #991b1b;');
  });
});
