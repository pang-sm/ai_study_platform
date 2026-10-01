/**
 * 练习: one scoped set of questions, played one at a time.
 *
 * What this file is really about, because each is a claim the page makes:
 *
 *   * the answer control is a property of the question's TYPE — a choice is radios, a multiple
 *     choice checkboxes, a true/false two radios, and only a short answer is a textarea
 *   * the reference answer and the analysis are NOT on screen until that question is answered
 *   * the set is one thing: the progress, the navigator and the verdicts all come from the same
 *     read, and no question is printed twice
 *   * a point the learner entered from arrives already chosen, so the page never asks again
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
  useCourseKnowledgeStructure: vi.fn(),
  useCoursePracticeSession: vi.fn(),
  useCoursePracticeHistory: vi.fn(),
  useGenerateCoursePractice: vi.fn(),
  useAnswerCoursePractice: vi.fn(),
  useAdaptivePractice: vi.fn(),
}));

vi.mock('@/features/course/api/course', () => hooks);
vi.mock('@/components/learning/p4-api', () => ({ useAdaptivePractice: hooks.useAdaptivePractice }));

const COURSE = '数据结构';
const URL = `/course/${encodeURIComponent(COURSE)}/practice`;

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });
const mutation = () => ({ isPending: false, isError: false, mutate: vi.fn() });

function structure() {
  return settled({
    course_id: COURSE,
    display: 'active',
    active: { id: 7, version: 1, status: 'active', source_mode: 'ai_generated',
              source_file_ids: [], title: '结构', goal: '',
              point_count: 2, chapter_count: 1, created_at: null, confirmed_at: null },
    draft: null,
    chapters: [{
      id: 100, title: '树', description: '',
      points: [{ id: 11, title: '二叉树的遍历', description: '', origin: 'ai_inferred' },
               { id: 12, title: '图的遍历', description: '', origin: 'ai_inferred' }],
    }],
    carry_over: null,
  });
}

type Question = {
  id: number; question_type: string; stem: string; options?: Record<string, string>;
  difficulty?: string; chapter?: string; knowledge_point_id?: string;
  knowledge_point_title?: string; answered?: boolean;
  result?: { question_id: number; user_answer: string; correct: boolean | null; judge: string;
             standard_answer: string; analysis: string; knowledge_point_title: string } | null;
};

function question(id: number, overrides: Partial<Question> = {}): Question {
  return {
    id, question_type: 'single_choice',
    stem: `关于遍历的说法，正确的是（第 ${id} 题）`,
    options: { A: '先访问根', B: '先访问右子树', C: '不需要访问', D: '顺序无关' },
    difficulty: '中等', chapter: '树', knowledge_point_id: 'kp:12',
    knowledge_point_title: '图的遍历', answered: false, result: null,
    ...overrides,
  };
}

function session(questions: Question[], status = 'in_progress') {
  return settled({
    course_id: COURSE,
    session: {
      attempt_id: 500, course_id: COURSE, status,
      total: questions.length,
      answered: questions.filter((item) => item.answered).length,
      correct_count: questions.filter((item) => item.result?.correct === true).length,
      questions,
    },
  });
}

const noSession = () => settled({ course_id: COURSE, session: null });

beforeEach(() => {
  vi.clearAllMocks();
  hooks.useCourseCatalog.mockReturnValue(settled({ courses: [{ id: COURSE, name: COURSE }] }));
  hooks.useCourseDashboard.mockReturnValue(settled({ course_name: COURSE }));
  hooks.useCourseKnowledgeStructure.mockReturnValue(structure());
  hooks.useCoursePracticeSession.mockReturnValue(noSession());
  hooks.useCoursePracticeHistory.mockReturnValue(settled({ course_id: COURSE, items: [], total: 0 }));
  hooks.useGenerateCoursePractice.mockReturnValue(mutation());
  hooks.useAnswerCoursePractice.mockReturnValue(mutation());
  hooks.useAdaptivePractice.mockReturnValue(settled({ candidates: [], reasons: {} }));
});

async function renderPractice(path = URL) {
  renderApp(path);
  await screen.findByRole('heading', { level: 1, name: '练习' });
}

/* ------------------------------------------------------------------ the page's name */

describe('the practice page', () => {
  it('is called 练习, not 课程练习本', async () => {
    await renderPractice();
    expect(screen.getByRole('heading', { level: 1, name: '练习' })).toBeInTheDocument();
    expect(screen.queryByText(/课程练习本/)).not.toBeInTheDocument();
  });

  it('opens on the generation entry when there is no set', async () => {
    await renderPractice();
    expect(screen.getByRole('button', { name: 'AI 生成练习' })).toBeInTheDocument();
  });

  it('shows the generation settings only after the learner asks for them', async () => {
    const user = userEvent.setup();
    await renderPractice();

    expect(screen.queryByRole('button', { name: '生成练习' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'AI 生成练习' }));
    expect(await screen.findByRole('button', { name: '生成练习' })).toBeInTheDocument();
    expect(screen.getByText('练习范围')).toBeInTheDocument();
    expect(screen.getByText('练习目标')).toBeInTheDocument();
    expect(screen.getByText('题量')).toBeInTheDocument();
    expect(screen.getByText('难度')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ scope */

describe('the scope the learner came in with', () => {
  it('arrives chosen when 知识结构 sent a knowledge point', async () => {
    await renderPractice(`${URL}?point=12`);
    expect(await screen.findByText('当前知识点：')).toBeInTheDocument();
    expect(screen.getAllByText('图的遍历').length).toBeGreaterThan(0);
    // the point is the SELECTED scope, not one of three equal choices
    expect(screen.getByRole('button', { name: '当前知识点', pressed: true })).toBeInTheDocument();
  });

  it('generates for exactly that point', async () => {
    const user = userEvent.setup();
    const generate = mutation();
    hooks.useGenerateCoursePractice.mockReturnValue(generate);
    await renderPractice(`${URL}?point=12`);

    await user.click(screen.getByRole('button', { name: '生成练习' }));
    expect(generate.mutate).toHaveBeenCalledTimes(1);
    expect(generate.mutate.mock.calls[0]![0]).toMatchObject({
      scope: 'knowledge_point', knowledge_point_id: 12, count: 5, difficulty: 'adaptive',
    });
  });

  it('offers every point of the active structure when the learner chooses one', async () => {
    const user = userEvent.setup();
    await renderPractice();
    await user.click(screen.getByRole('button', { name: 'AI 生成练习' }));
    await user.click(screen.getByRole('button', { name: '当前知识点' }));

    const select = screen.getByLabelText('知识点');
    expect(Array.from(select.querySelectorAll('option')).map((option) => option.textContent))
      .toEqual(['请选择知识点', '二叉树的遍历', '图的遍历']);
  });
});

/* ------------------------------------------------------------------ rendering by type */

describe('a question is rendered in the control its type calls for', () => {
  it('single choice → radios, with every option present', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([question(1)]));
    await renderPractice();
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(4);
    for (const label of ['A.', 'B.', 'C.', 'D.']) {
      expect(screen.getByText(label, { exact: false })).toBeInTheDocument();
    }
    expect(screen.getByText('先访问根', { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('multiple choice → checkboxes', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, { question_type: 'multiple_choice', options: { A: '甲', B: '乙', C: '丙', D: '丁' } }),
    ]));
    await renderPractice();
    expect(screen.getAllByRole('checkbox')).toHaveLength(4);
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  });

  it('true/false → two radios reading 正确 and 错误', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, { question_type: 'true_false', stem: '判断：遍历需要访问每个结点一次（第 1 题）',
                    options: { A: '正确', B: '错误' } }),
    ]));
    await renderPractice();
    expect(screen.getAllByRole('radio')).toHaveLength(2);
    expect(screen.getByText('正确', { exact: false })).toBeInTheDocument();
    expect(screen.getByText('错误', { exact: false })).toBeInTheDocument();
  });

  it('short answer → a textarea', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, { question_type: 'short_answer', options: {} }),
    ]));
    await renderPractice();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ answer secrecy + verdict */

describe('the answer', () => {
  it('is nowhere on screen before the learner answers', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([question(1)]));
    await renderPractice();
    expect(screen.queryByText('正确答案')).not.toBeInTheDocument();
    expect(screen.queryByText('解析')).not.toBeInTheDocument();
  });

  it('cannot be submitted empty, and is submitted as the chosen key', async () => {
    const user = userEvent.setup();
    const answer = mutation();
    hooks.useAnswerCoursePractice.mockReturnValue(answer);
    hooks.useCoursePracticeSession.mockReturnValue(session([question(1)]));
    await renderPractice();

    const submit = screen.getByRole('button', { name: '提交答案' });
    expect(submit).toBeDisabled();
    await user.click(screen.getAllByRole('radio')[1]!);
    expect(submit).toBeEnabled();
    await user.click(submit);
    expect(answer.mutate.mock.calls[0]![0]).toEqual({ attemptId: 500, questionId: 1, answer: 'B' });
  });

  it('keeps the learner on the finished set when the LAST answer closes it', async () => {
    const user = userEvent.setup();
    const answer = mutation();
    hooks.useAnswerCoursePractice.mockReturnValue(answer);
    hooks.useCoursePracticeSession.mockReturnValue(session([question(1)]));
    const { router } = renderApp(URL);
    await screen.findByRole('heading', { level: 1, name: '练习' });

    await user.click(screen.getAllByRole('radio')[0]!);
    await user.click(screen.getByRole('button', { name: '提交答案' }));
    expect(answer.mutate).toHaveBeenCalledTimes(1);

    // the server answers with a CLOSED set — the page must name it rather than fall back
    const options = answer.mutate.mock.calls[0]![1] as { onSuccess: (r: unknown) => void };
    options.onSuccess({ session: { attempt_id: 500, status: 'submitted' } });
    await waitFor(() => expect(router.state.location.search).toMatchObject({ session: 500 }));
  });

  it('comes back with the verdict, the reference answer and the analysis', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, {
        answered: true,
        result: { question_id: 1, user_answer: 'B', correct: false, judge: 'incorrect',
                  standard_answer: 'A', analysis: '先访问根是最常见的说法。',
                  knowledge_point_title: '图的遍历' },
      }),
    ]));
    await renderPractice();
    expect(screen.getByText('回答错误')).toBeInTheDocument();
    expect(screen.getByText('正确答案')).toBeInTheDocument();
    expect(screen.getByText('先访问根是最常见的说法。')).toBeInTheDocument();
    expect(screen.getByText('相关知识点')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ the set */

describe('the set', () => {
  it('shows progress through it, and only one question at a time', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, { answered: true, stem: '第一题的题干',
                    result: { question_id: 1, user_answer: 'A', correct: true, judge: 'correct',
                              standard_answer: 'A', analysis: '解析一', knowledge_point_title: '图的遍历' } }),
      question(2, { stem: '第二题的题干' }),
      question(3, { stem: '第三题的题干' }),
    ]));
    await renderPractice();

    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getByText('第二题的题干')).toBeInTheDocument();
    // the navigator lists positions, it does not reprint the questions
    expect(screen.queryByText('第一题的题干')).not.toBeInTheDocument();
    expect(screen.queryByText('第三题的题干')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '第 1 题，已答对' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '第 3 题，未作答' })).toBeInTheDocument();
  });

  it('names the knowledge point being practised', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([question(1), question(2)]));
    await renderPractice();
    expect(screen.getByText('正在练习：')).toBeInTheDocument();
    expect(screen.getAllByText('图的遍历').length).toBeGreaterThan(0);
  });

  it('resumes at the first unanswered question and walks forward from there', async () => {
    const user = userEvent.setup();
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, { answered: true, stem: '第一题的题干', result: { question_id: 1, user_answer: 'A',
                  correct: false, judge: 'incorrect', standard_answer: 'A', analysis: '解析一',
                  knowledge_point_title: '图的遍历' } }),
      question(2, { stem: '第二题的题干' }),
    ]));
    await renderPractice();

    // it opens on the question still to be done, not on the one already answered
    expect(screen.getByText('2 / 2')).toBeInTheDocument();
    expect(screen.getByText('第二题的题干')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '下一题' })).not.toBeInTheDocument();

    // going back to the answered one offers the way forward again
    await user.click(screen.getByRole('button', { name: '第 1 题，已答错' }));
    expect(screen.getByText('第一题的题干')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '下一题' }));
    expect(screen.getByText('第二题的题干')).toBeInTheDocument();
  });

  it('finishes with the counts and the points to review', async () => {
    hooks.useCoursePracticeSession.mockReturnValue(session([
      question(1, { answered: true, result: { question_id: 1, user_answer: 'A', correct: true,
                  judge: 'correct', standard_answer: 'A', analysis: '解析一',
                  knowledge_point_title: '图的遍历' } }),
      question(2, { answered: true, knowledge_point_title: '二叉树的遍历',
                  result: { question_id: 2, user_answer: 'C', correct: false,
                            judge: 'incorrect', standard_answer: 'A', analysis: '解析二',
                            knowledge_point_title: '二叉树的遍历' } }),
    ], 'submitted'));
    await renderPractice(`${URL}?session=500`);

    expect(screen.getByText('本次练习完成')).toBeInTheDocument();
    expect(screen.getByText('2 题 · 正确 1 · 错误 1')).toBeInTheDocument();
    expect(screen.getByText('需要复习')).toBeInTheDocument();
    expect(screen.getByText('二叉树的遍历')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看错题' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '再练一组' })).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ secondary content */

describe('recommendations and history', () => {
  it('are absent when there is nothing true to say', async () => {
    await renderPractice();
    expect(screen.queryByText('推荐练习')).not.toBeInTheDocument();
    expect(screen.queryByText('练习历史')).not.toBeInTheDocument();
    expect(screen.queryByText(/现在还没有可以推荐的练习/)).not.toBeInTheDocument();
    expect(screen.queryByText(/还没有练习历史/)).not.toBeInTheDocument();
  });

  it('list finished sets without reprinting their questions', async () => {
    hooks.useCoursePracticeHistory.mockReturnValue(settled({
      course_id: COURSE, total: 1,
      items: [{ session_id: 501, submitted_at: '2026-09-30T02:00:00Z', chapter: '树',
                knowledge_point_title: '图的遍历', total: 5, correct_count: 4 }],
    }));
    await renderPractice();
    expect(screen.getByText('5 题 · 4 正确')).toBeInTheDocument();
    expect(screen.getByText('树 · 图的遍历', { exact: false })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('练习历史')).toBeInTheDocument());
  });
});
