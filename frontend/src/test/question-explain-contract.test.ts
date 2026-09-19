/**
 * FRONTEND_BLOCKER_BC5B — compile-level contract probe for the Exam `question.explain` route.
 *
 * The exam post-submit explanation UI (F1C2C) is built on
 * `POST /exam/11408/{subject_key}/question-analysis`. This file is the regression guard that the
 * GENERATED client still describes that route concretely: if someone regenerates `api.ts` from a
 * spec where the body or the 2xx went back to `unknown`, these assertions stop compiling.
 *
 * It reads the generated types only — no handwritten DTO stands in for the transport.
 */
import { describe, expect, expectTypeOf, it } from 'vitest';
import type { components, paths } from '@/types/api';

type QuestionAnalysisRequest =
  components['schemas']['ExamQuestionAnalysisRequest'];
type QuestionAnalysisResponse =
  components['schemas']['ExamQuestionAnalysisResponse'];

type RouteOperation =
  paths['/exam/11408/{subject_key}/question-analysis']['post'];

describe('exam question.explain transport contract', () => {
  it('exposes a concrete request body in the generated client', () => {
    const body: QuestionAnalysisRequest = {
      stem: '线性表的顺序存储与链式存储，哪个支持 O(1) 随机访问？',
      options: { A: '顺序存储', B: '链式存储' },
      standard_answer: 'A',
      user_answer: 'B',
      question_type: 'choice',
      context: '错题复盘',
    };

    // `options` is a closed letter → text map, not an arbitrary bag.
    expectTypeOf(body.options).toEqualTypeOf<
      { [key: string]: string } | undefined
    >();
    expectTypeOf(body.stem).toEqualTypeOf<string | null | undefined>();
    expect(body.options).toEqual({ A: '顺序存储', B: '链式存储' });
  });

  it('keeps every request field optional so an omitted stem still reaches the handler', () => {
    const minimal: QuestionAnalysisRequest = {};
    expect(minimal).toEqual({});
  });

  it('exposes the explanation content on the success response', () => {
    type ResponseBody =
      RouteOperation['responses'][200]['content']['application/json'];
    expectTypeOf<ResponseBody>().toEqualTypeOf<QuestionAnalysisResponse>();

    // The field F1C2C renders: human-readable explanation text, always present.
    expectTypeOf<ResponseBody['analysis']>().toEqualTypeOf<string>();

    const response: QuestionAnalysisResponse = {
      analysis: '本题考查线性表的存储结构……',
      generated_at: '2026-09-18T00:00:00Z',
      model: null,
      request_id: 'abc123',
    };
    expect(response.analysis).toContain('本题考查');
  });

  it('does not expose provider-internal routing as part of the request', () => {
    // A caller cannot ask for a specific model/provider through this contract.
    expectTypeOf<QuestionAnalysisRequest>().not.toHaveProperty('model');
    expectTypeOf<QuestionAnalysisRequest>().not.toHaveProperty('provider');
  });
});
