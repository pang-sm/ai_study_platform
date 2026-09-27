import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { renderApp } from '@/test/render-app';
import { Cs408PracticeWorkspace } from './cs408-practice-workspace';

const feedbackProps = vi.fn();
vi.mock('@/components/learning/ai-feedback', () => ({ AiFeedback: (props: unknown) => { feedbackProps(props); return null; } }));

type Question = components['schemas']['ExamPracticeQuestion'];
type ExplainOptions = { onSuccess?: (value: { analysis: string; generated_at: null; model: string | null; request_id: string }) => void; onError?: (error: Error) => void; onSettled?: () => void };

// The pre-submit boundary must remain compile-time visible: list questions cannot expose solutions.
type PreSubmitQuestion = components['schemas']['ExamPracticeQuestion'];
// @ts-expect-error The generated pre-submit question schema intentionally has no answer key.
type _NoPreSubmitAnswer = PreSubmitQuestion['standard_answer'];
// @ts-expect-error The generated pre-submit question schema intentionally has no explanation key.
type _NoPreSubmitAnalysis = PreSubmitQuestion['analysis'];

const questions: Question[] = [
  { id: 11, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: '1.1', knowledge_point_name: '线性表的顺序存储', knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 1, question_type: 'choice', stem: '线性表的逻辑顺序由什么决定？', options: { A: '存储地址', B: '元素之间的前后关系' }, difficulty: null, quality_status: null, created_at: null, practiced: false },
  { id: 24, subject_key: 'data_structure', source_type: 'chapter', visibility: 'public', knowledge_point_id: null, knowledge_point_name: null, knowledge_point_path: null, knowledge_points: [], chapter_id: '1', chapter_name: '线性表', year: null, question_number: 2, question_type: 'big', stem: '说明顺序表插入操作的主要步骤。', options: {}, difficulty: null, quality_status: null, created_at: null, practiced: false },
];
let attemptDetail: components['schemas']['ExamPracticeAttemptDetailResponse'] | undefined;
// Set by the attempt-recovery cases: an attempt the learner opened by URL that cannot be read.
let attemptFailed = false;
let attemptPending = false;

// The chapter chooser reads THIS, so a case can hand the page the chapters it wants to test
// without touching the rest of the harness.
let outlineData: components['schemas']['ExamChapterPracticeOutlineResponse'] = {
  subject_key: 'data_structure', knowledge_points: {}, total: 2,
  chapters: [{ chapter_code: '1', chapter_no: 1, chapter_title: '线性表', question_count: 2 }],
};

const createAttempt = vi.fn((_input: unknown, options?: { onSuccess?: (value: { attempt_id: number }) => void }) => options?.onSuccess?.({ attempt_id: 91 }));
const saveAnswers = vi.fn();
const submit = vi.fn((_input: unknown, options?: { onSuccess?: (value: components['schemas']['ExamPracticeSubmitResponse']) => void }) => options?.onSuccess?.({ total_questions: 2, choice_total: 1, big_count: 1, correct_count: 1, wrong_count: 0, accuracy: 1, mistake_saved_count: 0, results: [{ question_id: 11, correct: true, standard_answer: 'B', user_answer: 'B', stem: questions[0]!.stem, options: questions[0]!.options, analysis: '提交后可见。', question_type: 'choice' }, { question_id: 24, correct: null, judge: 'self_review', standard_answer: '略', user_answer: '我的答案', stem: questions[1]!.stem, options: {}, analysis: '提交后可见。', question_type: 'big', hint: '' }] }));
const explain = vi.fn((_input: unknown, options?: ExplainOptions) => options?.onSuccess?.({ analysis: '这里是针对已提交作答的讲解。', generated_at: null, model: 'hidden-model', request_id: 'hidden-request' }));

// Records the arguments the workspace asked the question list for, so the concept it was
// given can be observed at the call boundary rather than inferred from the render.
const questionsArgs = vi.fn();
// Set by the concept-refusal test so the mocked create mutation reports the failure a real
// 422 would produce. Module-level because the hook is mocked, not the transport.
let createAttemptError: unknown;

vi.mock('@/features/exam/api/chapter-practice', () => ({
  useChapterPracticeOutline: () => ({ data: outlineData, isPending: false, isError: false, refetch: vi.fn() }),
  useChapterPracticeQuestions: (moduleKey: string, chapterCode: string, conceptCode?: string) => { questionsArgs(moduleKey, chapterCode, conceptCode); return { data: { items: questions, total: questions.length }, isPending: false, isError: false, refetch: vi.fn() }; },
  useChapterPracticeAttempt: () => ({ data: attemptDetail, isPending: attemptPending, isError: attemptFailed, refetch: vi.fn() }),
  useCreateChapterPracticeAttempt: () => ({ mutate: createAttempt, isPending: false, isError: createAttemptError !== undefined, error: createAttemptError }),
  useSaveChapterPracticeAnswers: () => ({ mutate: saveAnswers, isPending: false, isError: false }),
  useSubmitChapterPractice: () => ({ mutate: submit, isPending: false, isError: false }),
}));

vi.mock('@/features/exam/api/question-explain', () => ({
  useQuestionExplain: () => ({ mutate: explain, isPending: false }),
}));

vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

function renderWorkspace() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" /></QueryClientProvider>);
}

describe('Cs408PracticeWorkspace', () => {
  beforeEach(() => {
    attemptDetail = undefined;
    attemptFailed = false;
    attemptPending = false;
    explain.mockClear();
    feedbackProps.mockClear();
  });
  it('keeps explain unavailable before submission and renders only server-authoritative feedback afterwards', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    expect(screen.getByRole('heading', { name: '章节练习' })).toBeInTheDocument();
    expect(screen.getByText('第 1 章 · 线性表')).toBeInTheDocument();
    expect(screen.getByText('第 1 / 2 题')).toBeInTheDocument();
    expect(await screen.findByRole('group', { name: questions[0]!.stem })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'AI 讲解这道题' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: /元素之间的前后关系/ }));
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    expect(createAttempt).toHaveBeenCalledWith({ moduleKey: 'data_structure', questionIds: [11, 24] }, expect.anything());
    await user.click(screen.getByRole('button', { name: '保存答案' }));
    expect(saveAnswers).toHaveBeenCalledWith(expect.objectContaining({ attemptId: 91, answers: { '11': 'B' } }));
    await user.click(screen.getByRole('button', { name: '下一题' }));
    expect(screen.getByRole('textbox', { name: '你的作答' })).toBeInTheDocument();
    expect(screen.getByText('本题提交后可自行对照参考答案。')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '提交本章答案' }));
    expect(screen.getByRole('alertdialog')).toHaveTextContent('还有 1 题未作答');
    await user.click(screen.getByRole('button', { name: '仍然提交' }));
    expect(screen.getByRole('heading', { name: '本次练习完成' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '查看本次题目' }));
    expect(screen.getByText('自行复盘')).toBeInTheDocument();
    expect(screen.getAllByText('你的作答')).toHaveLength(2);
    expect(screen.getByText('参考答案')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /第 1 题/ }));
    expect(screen.getByText('回答正确')).toBeInTheDocument();
    expect(screen.getByText('判定')).toBeInTheDocument();
    expect(screen.getByText('你的答案：B')).toBeInTheDocument();
    expect(screen.getByText('正确答案：B')).toBeInTheDocument();
    expect(screen.getByText('题目解析')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'AI 讲解这道题' }));
    expect(explain).toHaveBeenCalledWith({
      moduleKey: 'data_structure',
      input: {
        stem: questions[0]!.stem, options: questions[0]!.options, standard_answer: 'B',
        user_answer: 'B', question_type: 'choice',
        // The product's own 解析 travels with the request (so a follow-up cannot contradict the
        // text the learner just read) and the point the question examines is NAMED — never its
        // code, which means nothing to a model.
        analysis: '提交后可见。', knowledge_point: '线性表的顺序存储',
      },
    }, expect.anything());
    expect(screen.getByText('这里是针对已提交作答的讲解。')).toBeInTheDocument();
    expect(screen.queryByText('hidden-model')).not.toBeInTheDocument();
    expect(screen.queryByText('hidden-request')).not.toBeInTheDocument();
    expect(screen.queryByText(/AI判分|自动评分/)).not.toBeInTheDocument();
    expect(feedbackProps).toHaveBeenCalledWith({ requestId: 'hidden-request', workflowId: 'exam_practice_ai_explain' });
  });

  it('replays submitted feedback by question id after reload without comparing answers', () => {
    attemptDetail = {
      attempt: { id: 91, status: 'submitted', total_questions: 2, knowledge_point_path: null, started_at: null },
      questions: [{ ...questions[1]!, standard_answer: '略', analysis: '' }, { ...questions[0]!, standard_answer: 'B', analysis: '提交后可见。' }],
      saved_answers: { '11': 'B', '24': '我的答案' },
      results: [
        { question_id: 24, correct: null, judge: 'self_review', standard_answer: '略', user_answer: '我的答案', stem: questions[1]!.stem, options: {}, analysis: '', question_type: 'big', hint: '' },
        { question_id: 11, correct: false, standard_answer: 'B', user_answer: 'A', stem: questions[0]!.stem, options: questions[0]!.options, analysis: '提交后可见。', question_type: 'choice' },
      ],
    };
    render(<QueryClientProvider client={new QueryClient()}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" attemptId={91} /></QueryClientProvider>);
    expect(screen.getByRole('heading', { name: '本次练习完成' })).toBeInTheDocument();
    expect(screen.getByText(/答错 1/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重练本次错题' })).toBeInTheDocument();
    
  });

  it('defaults a submitted attempt to its summary but lets review return to it', async () => {
    attemptDetail = {
      attempt: { id: 91, status: 'submitted', total_questions: 1, knowledge_point_path: null, started_at: null },
      questions: [{ ...questions[0]!, standard_answer: 'B', analysis: '提交后可见。' }],
      saved_answers: { '11': 'B' },
      results: [{ question_id: 11, correct: true, standard_answer: 'B', user_answer: 'B', stem: questions[0]!.stem, options: questions[0]!.options, analysis: '提交后可见。', question_type: 'choice' }],
    };
    const user = userEvent.setup();
    render(<QueryClientProvider client={new QueryClient()}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" attemptId={91} /></QueryClientProvider>);

    expect(screen.getByRole('heading', { name: '本次练习完成' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: '题目导航' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '上一题' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '下一题' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '查看本次题目' }));
    expect(screen.getByRole('group', { name: questions[0]!.stem })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: '题目导航' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /元素之间的前后关系/ })).toBeDisabled();
    expect(screen.getByText('回答正确')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '本次练习总结' }));
    expect(screen.getByRole('heading', { name: '本次练习完成' })).toBeInTheDocument();
  });

  it.each([
    { correct: null, userAnswer: '', reference: 'B', expected: '未作答' },
    { correct: true, userAnswer: 'A', reference: 'B', expected: '回答正确' },
    { correct: false, userAnswer: 'B', reference: 'B', expected: '回答错误' },
  ] as const)('uses the authoritative choice result for $expected without comparing answers', async ({ correct, userAnswer, reference, expected }) => {
    attemptDetail = {
      attempt: { id: 91, status: 'submitted', total_questions: 1, knowledge_point_path: null, started_at: null },
      questions: [{ ...questions[0]!, standard_answer: reference, analysis: '' }],
      saved_answers: { '11': userAnswer },
      results: [{ question_id: 11, correct, standard_answer: reference, user_answer: userAnswer, stem: questions[0]!.stem, options: questions[0]!.options, analysis: '', question_type: 'choice' }],
    };
    const user = userEvent.setup();
    render(<QueryClientProvider client={new QueryClient()}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" attemptId={91} /></QueryClientProvider>);

    await user.click(screen.getByRole('button', { name: '查看本次题目' }));
    expect(screen.getByText(expected)).toBeInTheDocument();
    if (expected === '未作答') {
      expect(screen.queryByText('回答正确')).not.toBeInTheDocument();
      expect(screen.queryByText('回答错误')).not.toBeInTheDocument();
    }
  });

  it('moves focus to the unanswered confirmation and returns it to the submit control', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole('radio', { name: /元素之间的前后关系/ }));
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    const submitControl = screen.getByRole('button', { name: '提交本章答案' });
    await user.click(submitControl);

    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    const continueButton = screen.getByRole('button', { name: '继续作答' });
    expect(continueButton).toHaveFocus();
    await user.click(continueButton);
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(submitControl).toHaveFocus();
  });

  it('renders only the question identities owned by an active retry attempt', async () => {
    attemptDetail = {
      attempt: { id: 91, status: 'in_progress', total_questions: 1, knowledge_point_path: null, started_at: null },
      questions: [{ ...questions[1]! }],
      saved_answers: {},
    };
    render(<QueryClientProvider client={new QueryClient()}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="1" attemptId={91} /></QueryClientProvider>);

    expect(screen.getByRole('heading', { name: questions[1]!.stem })).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: questions[0]!.stem })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '第 1 题' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '第 2 题' })).not.toBeInTheDocument();
  });

  it('keeps an AI explanation failure local to its submitted question', async () => {
    explain.mockImplementationOnce((_input: unknown, options?: ExplainOptions) => {
      options?.onError?.(new ApiRequestError(429, 'budget'));
      options?.onSettled?.();
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole('radio', { name: /元素之间的前后关系/ }));
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    await user.click(screen.getByRole('button', { name: '提交本章答案' }));
    await user.click(screen.getByRole('button', { name: '仍然提交' }));
    await user.click(screen.getByRole('button', { name: '查看本次题目' }));
    await user.click(screen.getByRole('button', { name: /第 1 题/ }));
    await user.click(screen.getByRole('button', { name: 'AI 讲解这道题' }));
    expect(screen.getByRole('alert')).toHaveTextContent('AI 讲解额度暂不可用');
    expect(screen.getByText('回答正确')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '下一题' }));
    expect(screen.getByText('自行复盘')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- ACCEL_PRODUCT_S9
//
// The learner arrived from a canonical knowledge leaf, so the concept the product already
// knows travels with the attempt. Direct entry must send NOTHING — a concept that was never
// known stays unknown rather than being filled in from the chapter, the title or the list.

describe('Cs408PracticeWorkspace concept identity', () => {
  beforeEach(() => { attemptDetail = undefined; createAttemptError = undefined; createAttempt.mockClear(); questionsArgs.mockClear(); });

  it('asks for the concept the learner came from, on both the list and the attempt', async () => {
    const user = userEvent.setup();
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="3" conceptCode="3.6" /></QueryClientProvider>);

    // the LIST is filtered by the canonical concept
    expect(questionsArgs).toHaveBeenCalledWith('data_structure', '3', '3.6');
    expect(screen.getByText(/知识点 3\.6/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    // the ATTEMPT carries the same identity, in the slot the attempt and its event store
    expect(createAttempt).toHaveBeenCalledWith(
      expect.objectContaining({ moduleKey: 'data_structure', knowledgePointId: '3.6' }),
      expect.anything(),
    );
    // and the questions it selected are exactly the ones the concept-filtered list served
    const payload = createAttempt.mock.calls[0]![0] as { questionIds: number[] };
    expect(payload.questionIds).toEqual(questions.map((question) => question.id));
  });

  it('sends NO concept from direct entry, and says nothing about a concept', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    expect(questionsArgs).toHaveBeenCalledWith('data_structure', '1', undefined);
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    const payload = createAttempt.mock.calls[0]![0] as { knowledgePointId?: string };
    expect(payload.knowledgePointId).toBeUndefined();
    expect(screen.queryByText(/知识点/)).not.toBeInTheDocument();
  });

  it('explains a refused concept instead of inviting a retry that cannot succeed', async () => {
    // A 422 is the server refusing the canonical concept: the question set no longer carries
    // it, or the id is not a leaf of this module. "请稍后重试" would be a lie — retrying
    // cannot succeed — so the copy sends the learner back to the knowledge tree.
    createAttemptError = new ApiRequestError(422, { code: 'CONCEPT_QUESTION_SET_MISMATCH' });
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Cs408PracticeWorkspace moduleKey="data_structure" chapterCode="3" conceptCode="3.6" /></QueryClientProvider>);
    expect(screen.getByRole('alert')).toHaveTextContent('本知识点的练习内容已变化，请返回知识脉络重新进入。');
  });
});

// ---------------------------------------------------------------- the chapter chooser

/**
 * 章节练习 with no chapter open: the page is the paper's real chapters and nothing else.
 *
 * The counts here are the ones the product actually reports for data_structure (the module's
 * real, active chapter bank), because a chooser is only honest if the numbers on it are the
 * numbers the questions behind it add up to.
 */
describe('Cs408PracticeWorkspace chapter chooser', () => {
  const REAL_CHAPTERS = [
    { chapter_code: '1', chapter_no: 1, chapter_title: '总览', question_count: 55 },
    { chapter_code: '2', chapter_no: 2, chapter_title: '线性表', question_count: 140 },
    { chapter_code: '3', chapter_no: 3, chapter_title: '栈、队列和数组', question_count: 135 },
  ];

  beforeEach(() => {
    outlineData = {
      subject_key: 'data_structure', knowledge_points: {}, total: 330, chapters: REAL_CHAPTERS,
    };
  });

  function renderChooser() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(<QueryClientProvider client={client}><Cs408PracticeWorkspace moduleKey="data_structure" /></QueryClientProvider>);
  }

  it('offers the paper real chapters, each with its real question count and one way in', () => {
    renderChooser();

    expect(screen.getByRole('heading', { name: '选择章节' })).toBeInTheDocument();
    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(3);
    expect(rows[0]?.textContent).toContain('总览');
    expect(rows[0]?.textContent).toContain('55 道题');
    expect(rows[1]?.textContent).toContain('140 道题');
    expect(rows[2]?.textContent).toContain('135 道题');

    // Every row is one link into that chapter's questions, carrying the module and the chapter.
    for (const [index, chapter] of REAL_CHAPTERS.entries()) {
      const link = within(rows[index] as HTMLElement).getByRole('link');
      expect(link).toHaveAttribute(
        'href',
        `/exam/cs408/practice?module=data_structure&chapter=${chapter.chapter_code}`,
      );
      expect(link).toHaveAccessibleName(expect.stringContaining('开始练习'));
    }
    expect(screen.getByText('共 330 道章节练习题')).toBeInTheDocument();
  });

  it('counts what the questions add up to, and states no progress nobody recorded', () => {
    renderChooser();

    // The total is the sum of the chapters, not the server's knowledge-point total (which counts
    // a question once per point it is tagged with).
    expect(screen.getByText('共 330 道章节练习题')).toBeInTheDocument();
    // This learner has recorded no chapter attempt here, so there is no 已做 / 正确率 to state —
    // and no 0% standing in for one.
    expect(screen.queryByText(/正确率|已做|完成度|%/)).not.toBeInTheDocument();
  });

  it('keeps the chooser to the chapters: no deep-reasoning panel and no recommendation strip', () => {
    renderChooser();

    // Both belong to a chapter that has been chosen. On the chooser they were a bigger entry
    // point than the chapter list, which is what this page is for.
    expect(screen.queryByText(/深度思考/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '推荐练习' })).not.toBeInTheDocument();
    // And nothing about the chapter being the CURRENT one: no chapter is open.
    expect(screen.queryByText(/选择章节后开始练习/)).not.toBeInTheDocument();
  });

  it('says a paper with no chapter questions is empty rather than showing a blank list', () => {
    outlineData = { subject_key: 'data_structure', knowledge_points: {}, total: 0, chapters: [] };
    renderChooser();

    expect(screen.getByText('这门科目还没有章节练习题。')).toBeInTheDocument();
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- the question's own AI

/**
 * 题目 AI: an entry that exists only after the learner has answered, is asked about THAT
 * question, and can be followed up without carrying the question somewhere else.
 */
describe('Cs408PracticeWorkspace question AI', () => {
  beforeEach(() => { attemptDetail = undefined; explain.mockClear(); });

  /** Answer the first question and submit, which is the state the AI entry belongs to. */
  async function answerAndSubmit(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('radio', { name: /元素之间的前后关系/ }));
    await user.click(screen.getByRole('button', { name: '开始本章练习' }));
    await user.click(screen.getByRole('button', { name: '提交本章答案' }));
    await user.click(screen.getByRole('button', { name: '仍然提交' }));
    await user.click(screen.getByRole('button', { name: '查看本次题目' }));
    await user.click(screen.getByRole('button', { name: /第 1 题/ }));
  }

  it('offers no AI answer before the learner has answered', () => {
    renderWorkspace();

    // The product's own 解析 and the AI entry are both for a SUBMITTED answer: showing either
    // before the learner has chosen would hand them the answer they were being asked for.
    expect(screen.queryByRole('button', { name: 'AI 讲解这道题' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'AI 讲解' })).not.toBeInTheDocument();
    expect(screen.queryByText('题目解析')).not.toBeInTheDocument();
    expect(screen.queryByText('正确答案：B')).not.toBeInTheDocument();
  });

  it('asks about the question the learner is on, and gets the product analysis to build on', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await answerAndSubmit(user);

    await user.click(screen.getByRole('button', { name: 'AI 讲解这道题' }));

    const [call] = explain.mock.calls.at(-1) as [ { moduleKey: string; input: Record<string, unknown> } ];
    expect(call.moduleKey).toBe('data_structure');
    // Everything the model is told comes from this question — it is not a generic explanation.
    expect(call.input).toMatchObject({
      stem: questions[0]!.stem, options: questions[0]!.options,
      standard_answer: 'B', user_answer: 'B', question_type: 'choice',
      analysis: '提交后可见。', knowledge_point: '线性表的顺序存储',
    });
    expect(screen.getByText('这里是针对已提交作答的讲解。')).toBeInTheDocument();
  });

  it('answers a follow-up about the SAME question, in place', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await answerAndSubmit(user);

    await user.click(screen.getByRole('button', { name: 'AI 讲解这道题' }));
    const url = window.location.href;

    await user.type(screen.getByLabelText('继续追问这道题'), '为什么 B 不对？');
    await user.click(screen.getByRole('button', { name: '追问' }));

    const [call] = explain.mock.calls.at(-1) as [ { input: Record<string, unknown> } ];
    // The same question, plus the learner's own follow-up — and nothing typed again by them.
    expect(call.input).toMatchObject({
      stem: questions[0]!.stem, standard_answer: 'B', analysis: '提交后可见。',
      knowledge_point: '线性表的顺序存储', follow_up: '为什么 B 不对？',
    });
    expect(screen.getByText('为什么 B 不对？')).toBeInTheDocument();
    expect(screen.getAllByText('这里是针对已提交作答的讲解。').length).toBeGreaterThan(1);
    // It stayed on the question: the follow-up is not a trip to another page.
    expect(window.location.href).toBe(url);
  });

  it('keeps the chapter desk free of a deep-reasoning panel and a recommendation strip', async () => {
    const user = userEvent.setup();
    renderWorkspace();
    await answerAndSubmit(user);

    expect(screen.queryByText(/深度思考/)).not.toBeInTheDocument();
    expect(screen.queryByText(/强推理/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '推荐练习' })).not.toBeInTheDocument();
    expect(screen.queryByText(/为什么推荐这一题/)).not.toBeInTheDocument();
    expect(screen.queryByText(/按你已记录的学习情况推荐/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------- an attempt that cannot be read

/**
 * The page an ATTEMPT URL opens when that attempt cannot be read — gone, or somebody else's
 * (the API answers 404 for both, on purpose, so this page never says which).
 *
 * It used to render nothing at all: the chapter line, then an empty body, no way back.
 */
describe('Cs408PracticeWorkspace attempt recovery', () => {
  beforeEach(() => { attemptDetail = undefined; attemptFailed = false; attemptPending = false; });

  /** Opened by URL, like the stale deep link a learner actually follows. */
  function renderAttempt(attemptId: number) {
    return renderApp(`/exam/cs408/practice?module=data_structure&chapter=1&attempt=${attemptId}`);
  }

  it('says the record is unavailable, and offers the chapter again', async () => {
    attemptFailed = true;
    renderAttempt(999999999);

    expect(await screen.findByRole('heading', { name: '练习记录不可用' })).toBeInTheDocument();
    expect(screen.getByText('这次练习记录不存在或已过期。')).toBeInTheDocument();
    // A real destination, not a history move: the same page opened by URL has no history.
    expect(screen.getByRole('link', { name: '返回本章练习' })).toHaveAttribute(
      'href',
      '/exam/cs408/practice?module=data_structure&chapter=1',
    );
    // And nothing of the question desk is drawn behind it.
    expect(screen.queryByRole('button', { name: '开始本章练习' })).not.toBeInTheDocument();
    expect(screen.queryByText(/判定/)).not.toBeInTheDocument();
  });

  it('waits rather than showing an empty body while the attempt is still loading', async () => {
    attemptPending = true;
    renderAttempt(91);

    await screen.findByRole('heading', { name: '章节练习' });
    expect(screen.queryByRole('heading', { name: '练习记录不可用' })).not.toBeInTheDocument();
    expect(document.querySelector('.cs408-practice__loading')).not.toBeNull();
  });
});
