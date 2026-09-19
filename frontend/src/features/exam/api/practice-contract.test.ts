import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '@/types/api';

const { GET, POST } = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, POST } }));

import { apiClient } from '@/lib/api/client';

// BC5A — compile-level proof that the chapter-practice success transport is concrete.
// Every alias below resolves through the generated `paths` / `components`, so a regeneration that
// drops or loosens one of these operations fails `npm run typecheck` instead of silently becoming
// `unknown` again. No cast, no handwritten transport DTO, no `any`.

type OutlineResponse = paths['/exam/11408/{subject_key}/chapter-practice/outline']['get']['responses'][200]['content']['application/json'];
type QuestionsResponse = paths['/exam/11408/{subject_key}/chapter-practice/questions']['get']['responses'][200]['content']['application/json'];
type QuestionsQuery = NonNullable<paths['/exam/11408/{subject_key}/chapter-practice/questions']['get']['parameters']['query']>;
type AttemptCreateBody = paths['/exam/11408/{subject_key}/chapter-practice/attempts']['post']['requestBody']['content']['application/json'];
type AttemptCreateResponse = paths['/exam/11408/{subject_key}/chapter-practice/attempts']['post']['responses'][200]['content']['application/json'];
type AttemptDetailResponse = paths['/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}']['get']['responses'][200]['content']['application/json'];
type AnswerSaveBody = paths['/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/answers']['post']['requestBody']['content']['application/json'];
type AnswerSaveResponse = paths['/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/answers']['post']['responses'][200]['content']['application/json'];
type SubmitBody = paths['/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/submit']['post']['requestBody']['content']['application/json'];
type SubmitResponse = paths['/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}/submit']['post']['responses'][200]['content']['application/json'];

type Chapter = components['schemas']['ExamPracticeChapter'];
type Question = components['schemas']['ExamPracticeQuestion'];
type AttemptQuestion = components['schemas']['ExamPracticeAttemptQuestion'];
type SubmitResult = components['schemas']['ExamPracticeSubmitResponse']['results'][number];

// BC5C — the submitted-attempt replay. `results` is the authoritative per-question verdict the
// backend already persisted at submit time, replayed on reload. Same generated unions as the submit
// response, so the frontend never compares `user_answer` against `standard_answer` itself.
//
// `AttemptDetailResponse` is the generated schema; `AttemptDetailRead` is what the typed client
// actually delivers. The two differ in exactly one place: `Readable` in openapi-typescript-helpers
// drops `null`-only properties on read, which is `correct` on a big question — always `null`, and
// never read, because a big question is identified by `question_type` and carried by `judge`.
type AttemptResult = NonNullable<AttemptDetailResponse['results']>[number];
type AttemptDetailRead = Awaited<ReturnType<typeof readAttemptDetail>>;
type ReadAttemptResult = NonNullable<AttemptDetailRead['results']>[number];
type ChoiceResult = components['schemas']['ExamChoicePracticeResult'];
type BigResult = components['schemas']['ExamBigPracticeResult'];

// Read the replayed verdict keyed by `question_id` — never by array position, so a changed question
// order after reload cannot rebind an answer. No cast, no handwritten DTO, no `unknown`.
function replayByQuestionId(detail: AttemptDetailRead) {
  const byQuestionId: Record<number, ReadAttemptResult> = {};
  for (const result of detail.results ?? []) byQuestionId[result.question_id] = result;
  return byQuestionId;
}

// The reloaded card. `correct` is only consulted for choice questions: a big question is never
// auto-graded, so the frontend reads `judge` instead of inferring anything from the answer.
function replayCard(result: ReadAttemptResult) {
  const shared = {
    questionId: result.question_id,
    userAnswer: result.user_answer,
    reference: result.standard_answer,
    analysis: result.analysis,
  };
  if (result.question_type === 'big') {
    return { ...shared, questionType: 'big' as const, headline: '自行复盘' as const, judge: result.judge, hint: result.hint };
  }
  return { ...shared, questionType: 'choice' as const, correct: result.correct, headline: result.correct ? ('回答正确' as const) : ('回答错误' as const) };
}

async function readAttemptDetail() {
  const { data, error, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/attempts/{attempt_id}', {
    params: { path: { subject_key: 'data_structure', attempt_id: 7 } },
  });
  if (!response.ok || data === undefined) throw new Error(String(error));
  return data;
}

// Every field the Answer Desk needs, read without a cast. `standard_answer` is deliberately NOT
// part of the pre-submit question, and `@ts-expect-error` is what proves that: if a future contract
// puts the answer back on the pre-submit payload, these directives stop erroring and typecheck
// fails loudly.
function answerDeskProjection(chapter: Chapter, question: Question, detail: AttemptDetailResponse, submitted: SubmitResponse) {
  const chapterTarget = {
    attemptId: detail.attempt.id,
    chapterCode: chapter.chapter_code,
    chapterNo: chapter.chapter_no,
    chapterTitle: chapter.chapter_title,
    questionCount: chapter.question_count,
  };
  const card = {
    questionId: question.id,
    questionType: question.question_type,
    stem: question.stem,
    options: Object.entries(question.options).map(([letter, text]) => ({ letter, text })),
    chapterId: question.chapter_id,
    practiced: question.practiced,
  };
  const restored = {
    attemptId: detail.attempt.id,
    status: detail.attempt.status,
    savedAnswer: detail.saved_answers[String(question.id)],
    questionType: detail.questions[0]?.question_type,
  };
  const graded = {
    correctCount: submitted.correct_count,
    wrongCount: submitted.wrong_count,
    accuracy: submitted.accuracy,
    mistakeSavedCount: submitted.mistake_saved_count,
  };
  const perQuestion = submitted.results.map((result) => {
    const base = { questionId: result.question_id, correct: result.correct, userAnswer: result.user_answer };
    if (result.question_type === 'big') {
      return { ...base, judge: result.judge, reference: result.standard_answer, hint: result.hint };
    }
    return { ...base, isCorrect: result.correct, answer: result.standard_answer, analysis: result.analysis };
  });
  return { chapterTarget, card, restored, graded, perQuestion };
}

function postSubmitAnalysis(question: AttemptQuestion): string | null {
  return question.analysis ?? null;
}

describe('BC5A chapter-practice generated contract', () => {
  it('exposes the canonical chapter identity on the outline response', async () => {
    const payload: OutlineResponse = {
      subject_key: 'data_structure',
      knowledge_points: { '1.1': 40 },
      total: 40,
      chapters: [{ chapter_code: '1', chapter_no: 1, chapter_title: '绪论', question_count: 40 }],
    };
    GET.mockResolvedValue({ data: payload, error: undefined, response: { ok: true, status: 200 } as Response });

    const { data, response } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/outline', {
      params: { path: { subject_key: 'data_structure' } },
    });
    if (!response.ok || data === undefined) throw new Error('unreachable');
    expect(data.chapters[0]?.chapter_code).toBe('1');
    expect(GET).toHaveBeenCalledWith('/exam/11408/{subject_key}/chapter-practice/outline', {
      params: { path: { subject_key: 'data_structure' } },
    });
  });

  it('accepts the canonical chapter filter and reads a pre-submit question without an answer', async () => {
    const query: QuestionsQuery = { chapter_code: '1', include_children: true };
    const payload: QuestionsResponse = {
      items: [
        {
          id: 7234,
          subject_key: 'data_structure',
          source_type: 'chapter',
          visibility: 'public',
          knowledge_point_id: '1.1',
          knowledge_point_name: '数据结构的基本概念',
          knowledge_point_path: null,
          knowledge_points: [],
          chapter_id: '1',
          chapter_name: '第1章',
          year: null,
          question_number: null,
          question_type: 'choice',
          stem: '题干',
          options: { A: '甲', B: '乙' },
          difficulty: 'medium',
          quality_status: 'unchecked',
          created_at: '2026-09-17T00:00:00Z',
          practiced: false,
        },
      ],
      total: 1,
    };
    GET.mockResolvedValue({ data: payload, error: undefined, response: { ok: true, status: 200 } as Response });

    const { data } = await apiClient.GET('/exam/11408/{subject_key}/chapter-practice/questions', {
      params: { path: { subject_key: 'data_structure' }, query },
    });
    expect(data?.items[0]?.id).toBe(7234);
    expect(data?.items[0]?.question_type).toBe('choice');
    // @ts-expect-error the pre-submit question must not carry the correct answer
    void data?.items[0]?.standard_answer;
    // @ts-expect-error the pre-submit question must not carry the explanation
    void data?.items[0]?.analysis;
    // @ts-expect-error the pre-submit question carries no grading result
    void data?.items[0]?.correct;
  });

  it('types the attempt lifecycle write bodies and responses', async () => {
    const createBody: AttemptCreateBody = { question_ids: [7234, 7235] };
    const saveBody: AnswerSaveBody = { answers: { '7234': 'A' } };
    const submitBody: SubmitBody = { answers: { '7234': 'A' } };
    expect([createBody, saveBody, submitBody]).toHaveLength(3);

    const created: AttemptCreateResponse = { attempt_id: 7, status: 'in_progress', total_questions: 2 };
    expect(created.status).toBe('in_progress');

    POST.mockResolvedValue({ data: created, error: undefined, response: { ok: true, status: 200 } as Response });
    const { data } = await apiClient.POST('/exam/11408/{subject_key}/chapter-practice/attempts', {
      params: { path: { subject_key: 'data_structure' } },
      body: createBody,
    });
    expect(data?.attempt_id).toBe(7);

    const saved: AnswerSaveResponse = { success: true };
    expect(saved.success).toBe(true);

    const detail: AttemptDetailResponse = {
      attempt: { id: 7, status: 'in_progress', total_questions: 2, knowledge_point_path: null, started_at: '2026-09-17T00:00:00Z' },
      questions: [],
      saved_answers: { '7234': 'A' },
    };
    // The attempt-scoped question keeps `standard_answer` / `analysis` optional: the server omits
    // them while the attempt is `in_progress` and includes them once it is `submitted`.
    expect(detail.questions[0]?.analysis ?? null).toBeNull();
    expect(detail.saved_answers['7234']).toBe('A');

    const submitted: SubmitResponse = {
      total_questions: 2,
      choice_total: 1,
      big_count: 1,
      correct_count: 1,
      wrong_count: 0,
      accuracy: 100,
      mistake_saved_count: 0,
      results: [
        { question_id: 7234, correct: true, standard_answer: 'A', user_answer: 'A', stem: '题干', options: { A: '甲' }, analysis: '', question_type: 'choice' },
        { question_id: 7235, correct: null, judge: 'self_review', standard_answer: '参考答案', user_answer: '', stem: '题干', options: {}, analysis: '', question_type: 'big', hint: '请自行对照参考答案' },
      ],
    };
    const big = submitted.results.filter((result) => result.question_type === 'big');
    expect(big[0]?.question_type === 'big' && big[0].judge).toBe('self_review');
    const choice: SubmitResult = submitted.results[0]!;
    expect(choice.question_type).toBe('choice');
  });

  it('projects the answer-desk view and post-submit explanation without a cast', () => {
    const outlineChapter: Chapter = { chapter_code: '1', chapter_no: 1, chapter_title: '绪论', question_count: 40 };
    const question: Question = {
      id: 7234,
      subject_key: 'data_structure',
      source_type: 'chapter',
      visibility: 'public',
      knowledge_point_id: null,
      knowledge_point_name: null,
      knowledge_point_path: null,
      knowledge_points: [],
      chapter_id: '1',
      chapter_name: '第1章',
      year: null,
      question_number: null,
      question_type: 'big',
      stem: '题干',
      options: {},
      difficulty: null,
      quality_status: null,
      created_at: null,
      practiced: true,
    };
    const detail: AttemptDetailResponse = {
      attempt: { id: 7, status: 'submitted', total_questions: 1, knowledge_point_path: null, started_at: null },
      questions: [{ ...question, standard_answer: '参考答案', analysis: '解析文本' }],
      saved_answers: {},
    };
    const submitted: SubmitResponse = {
      total_questions: 1, choice_total: 0, big_count: 1, correct_count: 0, wrong_count: 0,
      accuracy: 0, mistake_saved_count: 0,
      results: [{ question_id: 7234, correct: null, judge: 'self_review', standard_answer: '参考答案', user_answer: '', stem: '题干', options: {}, analysis: '解析文本', question_type: 'big', hint: '请自行对照参考答案' }],
    };

    const view = answerDeskProjection(outlineChapter, question, detail, submitted);
    expect(view.chapterTarget.chapterCode).toBe('1');
    expect(view.card.questionType).toBe('big');
    expect(view.restored.attemptId).toBe(7);
    expect(view.graded.accuracy).toBe(0);
    expect(view.perQuestion[0]).toMatchObject({ judge: 'self_review' });
    expect(postSubmitAnalysis(detail.questions[0]!)).toBe('解析文本');
  });
});

describe('BC5C submitted-attempt result replay contract', () => {
  const submittedDetail: AttemptDetailResponse = {
    attempt: { id: 7, status: 'submitted', total_questions: 2, knowledge_point_path: null, started_at: null },
    questions: [
      { ...attemptQuestion(7234), standard_answer: 'A', analysis: '解析' },
      { ...attemptQuestion(7235, 'big'), standard_answer: '参考答案', analysis: '' },
    ],
    saved_answers: {},
    results: [
      { question_id: 7234, correct: true, standard_answer: 'A', user_answer: 'a', stem: '题干', options: { A: '甲' }, analysis: '解析', question_type: 'choice' },
      { question_id: 7235, correct: null, judge: 'self_review', standard_answer: '参考答案', user_answer: '手写作答', stem: '题干', options: {}, analysis: '', question_type: 'big', hint: '请自行对照参考答案' },
    ],
  };

  it('reads the replayed verdict by question_id with no cast and no comparison', () => {
    const byQuestionId = replayByQuestionId(submittedDetail);

    expect(Object.keys(byQuestionId)).toEqual(['7234', '7235']);
    expect(byQuestionId[7234]?.user_answer).toBe('a');
    expect(byQuestionId[7234]?.standard_answer).toBe('A');
    expect(byQuestionId[7234]?.analysis).toBe('解析');
    const choice = byQuestionId[7234]!;
    if (choice.question_type !== 'choice') throw new Error('unreachable');
    expect(choice.correct).toBe(true);
    expect(replayCard(choice).headline).toBe('回答正确');
    expect(replayCard(choice).questionType).toBe('choice');
  });

  it('replays a 自行复盘 big question with no AI judging and no boolean verdict', () => {
    const big = replayByQuestionId(submittedDetail)[7235];

    expect(big?.question_type).toBe('big');
    if (big?.question_type !== 'big') throw new Error('unreachable');
    // a big question carries no boolean verdict to read — only the self-review marker
    expect(big.judge).toBe('self_review');
    expect(big.user_answer).toBe('手写作答');
    expect(big.standard_answer).toBe('参考答案');

    const card = replayCard(big);
    expect(card.headline).toBe('自行复盘');
    expect(card.questionType).toBe('big');
    expect(card.userAnswer).toBe('手写作答');
  });

  it('survives a reordered question list: binding follows question_id, not position', () => {
    const reloaded: AttemptDetailResponse = {
      ...submittedDetail,
      questions: [...submittedDetail.questions].reverse(),
    };

    expect(replayByQuestionId(reloaded)[7234]?.user_answer).toBe('a');
    expect(replayByQuestionId(reloaded)[7235]?.user_answer).toBe('手写作答');
  });

  it('keeps the pre-submit detail free of any grading result at the type level', () => {
    const inProgress: AttemptDetailResponse = {
      attempt: { id: 7, status: 'in_progress', total_questions: 1, knowledge_point_path: null, started_at: null },
      questions: [attemptQuestion(7234)],
      saved_answers: { '7234': 'A' },
    };
    expect(inProgress.results).toBeUndefined();

    // @ts-expect-error the pre-submit attempt question carries no grading verdict
    void inProgress.questions[0]?.correct;
    // @ts-expect-error the pre-submit attempt question carries no self-review marker
    void inProgress.questions[0]?.judge;
    // `standard_answer` / `analysis` stay OPTIONAL on the attempt question by design: the server
    // omits them while `in_progress` and includes them once `submitted`.
    expect(inProgress.questions[0]?.standard_answer).toBeUndefined();
    expect(inProgress.questions[0]?.analysis).toBeUndefined();
  });

  it('keeps the replayed result concrete instead of unknown or any', () => {
    // A concrete shape assigns without a cast; `unknown` would not.
    const concrete: { question_id: number; correct: boolean | null } = submittedDetail.results![0]!;
    expect(concrete.question_id).toBe(7234);
    // @ts-expect-error a concrete result type rejects an invented field; `any` would accept it
    void submittedDetail.results![0]!.invented_field;
    // @ts-expect-error a choice result must not grow a `judge` enum of its own
    void (submittedDetail.results![0] as ChoiceResult).judge;
    const choice: ChoiceResult = { question_id: 7234, correct: true, standard_answer: 'A', user_answer: 'A', stem: '题干', options: {}, analysis: '', question_type: 'choice' };
    const big: BigResult = { question_id: 7235, correct: null, judge: 'self_review', standard_answer: '参考答案', user_answer: '', stem: '题干', options: {}, analysis: '', question_type: 'big', hint: '请自行对照参考答案' };
    expect([choice.correct, big.correct]).toEqual([true, null]);
  });

  it('exposes every replayed field on the generated schema, keyed by question_id', () => {
    // The generated contract itself carries all five facts the reload needs, for both types.
    const resumed = new Map<number, { user_answer: string; correct: boolean | null; reference: string; analysis: string }>();
    for (const result of submittedDetail.results ?? []) {
      resumed.set(result.question_id, {
        user_answer: result.user_answer,
        correct: result.correct,
        reference: result.standard_answer,
        analysis: result.analysis,
      });
    }

    expect(resumed.get(7234)).toEqual({ user_answer: 'a', correct: true, reference: 'A', analysis: '解析' });
    expect(resumed.get(7235)).toEqual({ user_answer: '手写作答', correct: null, reference: '参考答案', analysis: '' });

    const big: AttemptResult = submittedDetail.results![1]!;
    if (big.question_type !== 'big') throw new Error('unreachable');
    expect(big.judge).toBe('self_review');
    // @ts-expect-error `correct` on a big result is `null`, not an unflagged boolean verdict
    const neverTrue: true = big.correct;
    void neverTrue;
  });

  it('carries the replayed results through the generated GET operation', async () => {
    GET.mockResolvedValue({ data: submittedDetail, error: undefined, response: { ok: true, status: 200 } as Response });

    const detail = await readAttemptDetail();
    const byQuestionId = replayByQuestionId(detail);

    expect(Object.keys(byQuestionId)).toEqual(['7234', '7235']);
    expect(replayCard(byQuestionId[7235]!).headline).toBe('自行复盘');
    expect(replayCard(byQuestionId[7234]!).headline).toBe('回答正确');
    // the client-delivered type narrows on `question_type`, so the big branch exposes `judge`
    const big = byQuestionId[7235]!;
    if (big.question_type !== 'big') throw new Error('unreachable');
    expect(big.judge).toBe('self_review');
    expect(big.user_answer).toBe('手写作答');
    expect(big.standard_answer).toBe('参考答案');
  });
});

// A submitted-attempt question as the server serves it after submission.
function attemptQuestion(id: number, questionType: 'choice' | 'big' = 'choice'): AttemptQuestion {
  return {
    id,
    subject_key: 'data_structure',
    source_type: 'chapter',
    visibility: 'public',
    knowledge_point_id: null,
    knowledge_point_name: null,
    knowledge_point_path: null,
    knowledge_points: [],
    chapter_id: '1',
    chapter_name: '第1章',
    year: null,
    question_number: null,
    question_type: questionType,
    stem: '题干',
    options: { A: '甲' },
    difficulty: null,
    quality_status: null,
    created_at: null,
  };
}
