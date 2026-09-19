import { describe, expect, it, vi } from 'vitest';
import type { components, paths } from '@/types/api';

const { GET, POST } = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));
vi.mock('@/lib/api/client', () => ({ apiClient: { GET, POST } }));

import { apiClient } from '@/lib/api/client';

// BC6 — compile-level proof that the normalized past-paper transport is concrete. Every alias
// resolves through the generated `paths` / `components`, so a regeneration that drops or loosens
// one of these operations fails `npm run typecheck` instead of silently becoming `unknown`.
// No cast, no handwritten transport DTO, no `any`.

type IndexResponse = paths['/exam/11408/{subject_key}/past-papers']['get']['responses'][200]['content']['application/json'];
type QuestionsResponse = paths['/exam/11408/{subject_key}/past-paper-questions']['get']['responses'][200]['content']['application/json'];
type QuestionsQuery = NonNullable<paths['/exam/11408/{subject_key}/past-paper-questions']['get']['parameters']['query']>;
type CreateBody = paths['/exam/11408/{subject_key}/past-paper-attempts']['post']['requestBody']['content']['application/json'];
type CreateResponse = paths['/exam/11408/{subject_key}/past-paper-attempts']['post']['responses'][200]['content']['application/json'];
type DetailResponse = paths['/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}']['get']['responses'][200]['content']['application/json'];
type SaveBody = paths['/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers']['post']['requestBody']['content']['application/json'];
type SaveResponse = paths['/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/answers']['post']['responses'][200]['content']['application/json'];
type SubmitBody = paths['/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit']['post']['requestBody']['content']['application/json'];
type SubmitResponse = paths['/exam/11408/{subject_key}/past-paper-attempts/{attempt_id}/submit']['post']['responses'][200]['content']['application/json'];

type PaperSummary = components['schemas']['PastPaperSummary'];
type NormalizedQuestion = components['schemas']['PastPaperQuestion'];
type QuestionResult = components['schemas']['PastPaperQuestionResult'];
type Resource = components['schemas']['PastPaperResource'];

// The public identity is the paper/question tuple — never a source id, never an array index.
function paperKey(summary: PaperSummary, subjectKey: string) {
  return { subjectKey, year: summary.year };
}

function questionKey(question: NormalizedQuestion) {
  return `${question.subject_key}:${question.year}:${question.question_number}`;
}

function indexResultsByQuestionKey(results: QuestionResult[]) {
  const byKey: Record<string, QuestionResult> = {};
  for (const result of results) {
    byKey[`${result.subject_key}:${result.year}:${result.question_number}`] = result;
  }
  return byKey;
}

function resourceUrl(resource: Resource) {
  return resource.url;
}

describe('BC6 past-paper generated contract', () => {
  it('types the paper index without a hardcoded year list', async () => {
    const payload: IndexResponse = {
      subject_key: 'operating_system',
      subject_name: '操作系统',
      papers: [
        { year: 2022, question_count: 12, choice_count: 10, big_count: 2, source: 'bank' },
        { year: 2023, question_count: 12, choice_count: 10, big_count: 2, source: 'document' },
      ],
    };
    GET.mockResolvedValue({ data: payload, error: undefined, response: { ok: true, status: 200 } as Response });

    const { data } = await apiClient.GET('/exam/11408/{subject_key}/past-papers', {
      params: { path: { subject_key: 'operating_system' } },
    });
    if (!data) throw new Error('unreachable');
    const keys = data.papers.map((paper) => paperKey(paper, data.subject_key));
    expect(keys).toEqual([
      { subjectKey: 'operating_system', year: 2022 },
      { subjectKey: 'operating_system', year: 2023 },
    ]);
    // availability is read from the payload, never inferred from a fixed 2022–2026 range
    expect(data.papers.every((paper) => paper.question_count > 0)).toBe(true);
  });

  it('accepts the year filter and reads a normalized question with no answer fields', async () => {
    const query: QuestionsQuery = { year: 2022 };
    const payload: QuestionsResponse = {
      subject_key: 'data_structure',
      subject_name: '数据结构',
      year: 2022,
      source: 'document',
      questions: [
        {
          subject_key: 'data_structure',
          year: 2022,
          question_number: 1,
          question_type: 'choice',
          stem: '下列程序段的时间复杂度是（ ）。',
          options: { A: 'O(log n)', B: 'O(n)' },
          resources: [{ url: '/exam/11408/past-paper-images/data_structure/2022/img_0.jpg' }],
          full_score: 2,
        },
      ],
    };
    GET.mockResolvedValue({ data: payload, error: undefined, response: { ok: true, status: 200 } as Response });

    const { data } = await apiClient.GET('/exam/11408/{subject_key}/past-paper-questions', {
      params: { path: { subject_key: 'data_structure' }, query },
    });
    const question = data?.questions[0];
    if (!question) throw new Error('unreachable');
    expect(questionKey(question)).toBe('data_structure:2022:1');
    expect(resourceUrl(question.resources[0]!)).toBe('/exam/11408/past-paper-images/data_structure/2022/img_0.jpg');
    // @ts-expect-error a normalized pre-submit question carries no standard answer
    void question.standard_answer;
    // @ts-expect-error a normalized pre-submit question carries no explanation
    void question.analysis;
    // @ts-expect-error a normalized pre-submit question carries no grading result
    void question.correct;
    // @ts-expect-error the public contract never exposes a source-specific id
    void question.id;
  });

  it('types attempt create, save and submit keyed by the public question number', async () => {
    const createBody: CreateBody = { year: 2022 };
    const created: CreateResponse = {
      attempt_id: 12, attempt_no: 1, subject_key: 'operating_system', year: 2022,
      status: 'in_progress', total_questions: 12,
    };
    const saveBody: SaveBody = { answers: { '23': 'A' } };
    const saved: SaveResponse = { success: true, attempt_id: 12 };
    const submitBody: SubmitBody = { answers: { '23': 'A', '45': '我的作答' } };
    expect([createBody, saveBody, submitBody]).toHaveLength(3);
    expect(created.status).toBe('in_progress');
    expect(saved.attempt_id).toBe(12);

    POST.mockResolvedValue({ data: created, error: undefined, response: { ok: true, status: 200 } as Response });
    const { data } = await apiClient.POST('/exam/11408/{subject_key}/past-paper-attempts', {
      params: { path: { subject_key: 'operating_system' } },
      body: createBody,
    });
    expect(data?.attempt_id).toBe(12);
  });

  it('distinguishes deterministic, self-review and ai-graded results without inventing a score', () => {
    const submitted: SubmitResponse = {
      attempt_id: 12, attempt_no: 1, subject_key: 'operating_system', year: 2022,
      total_questions: 3, choice_total: 1, choice_correct: 1,
      self_review_count: 1, ai_graded_count: 1, total_score: 2, max_score: 22,
      answer_grade: { applied: true, reason: null },
      results: [
        {
          subject_key: 'operating_system', year: 2022, question_number: 23, question_type: 'choice',
          user_answer: 'A', correct: true, judge: null,
          standard_answer: 'A', analysis: '解析', score: 2, full_score: 2, feedback: null,
        },
        {
          subject_key: 'operating_system', year: 2022, question_number: 45, question_type: 'big',
          user_answer: '我的作答', correct: null, judge: 'self_review',
          standard_answer: '参考答案', analysis: null, score: null, full_score: 10,
          feedback: '请自行对照参考答案',
        },
        {
          subject_key: 'operating_system', year: 2022, question_number: 46, question_type: 'big',
          user_answer: '我的作答', correct: null, judge: 'ai_graded',
          standard_answer: '参考答案', analysis: null, score: 8, full_score: 10,
          feedback: '思路正确',
        },
      ],
    };

    const byKey = indexResultsByQuestionKey(submitted.results);
    expect(byKey['operating_system:2022:23']?.correct).toBe(true);
    expect(byKey['operating_system:2022:23']?.judge).toBeNull();

    const selfReview = byKey['operating_system:2022:45'];
    expect(selfReview?.judge).toBe('self_review');
    expect(selfReview?.correct).toBeNull();
    expect(selfReview?.score).toBeNull();

    const graded = byKey['operating_system:2022:46'];
    expect(graded?.judge).toBe('ai_graded');
    expect(graded?.correct).toBeNull();
    expect(graded?.score).toBe(8);

    // an unavailable grade never carries a score
    const unavailable: SubmitResponse = { ...submitted, answer_grade: { applied: false, reason: 'answer_grade_unavailable_403' } };
    expect(unavailable.answer_grade.applied).toBe(false);
  });

  it('replays a submitted attempt keyed by the public identity with no server id', () => {
    const detail: DetailResponse = {
      attempt: {
        id: 12, attempt_no: 1, subject_key: 'operating_system', year: 2022,
        status: 'submitted', total_questions: 1, started_at: null, submitted_at: '2026-09-19T00:00:00Z',
      },
      questions: [{
        subject_key: 'operating_system', year: 2022, question_number: 23, question_type: 'choice',
        stem: '题干', options: { A: '甲' }, resources: [], full_score: 2,
      }],
      saved_answers: { '23': 'A' },
      results: [{
        subject_key: 'operating_system', year: 2022, question_number: 23, question_type: 'choice',
        user_answer: 'A', correct: true, judge: null,
        standard_answer: 'A', analysis: null, score: 2, full_score: 2, feedback: null,
      }],
    };

    const byKey = indexResultsByQuestionKey(detail.results ?? []);
    expect(Object.keys(byKey)).toEqual(['operating_system:2022:23']);
    expect(byKey['operating_system:2022:23']?.user_answer).toBe('A');
    // the in-progress shape carries no results at all
    const inProgress: DetailResponse = { ...detail, attempt: { ...detail.attempt, status: 'in_progress' }, results: [] };
    expect(inProgress.results).toEqual([]);
  });
});
