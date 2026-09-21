import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderApp } from './render-app';

/**
 * LEARNER_METADATA_LEAKAGE_GUARD — the runtime half.
 *
 * Every route this product serves belongs to a learner, so no screen may render the transport it
 * was built from. This suite proves that by feeding each surface a *hostile* payload: every
 * leakage class the product must never show is planted inside it under a recognisable marker, and
 * the assertion is that the marker never reaches the document while the real fact beside it does.
 *
 * Markers, so a failure names what leaked:
 *   LEAK_OBJECT      a field name the product cannot say — must be dropped, not dumped
 *   LEAK_ENUM        an unmapped code in a coded field    — must become `其他` / `未设置`
 *   LEAK_REF         an internal identity (ids, refs)     — must not appear at all
 *   LEAK_REQUEST     AI request / agent-run identity      — internal, never rendered
 *   LEAK_PROVIDER    a provider or capability name        — never rendered
 *
 * The companion source guard lives in `learner-copy.guard.test.ts`.
 */

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: post, PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

/** Each surface settles several dependent queries before it can render; the default is too tight. */
const SETTLE = { timeout: 5000 } as const;

/**
 * Waits for the surface to reach the state under test.
 *
 * Polling rather than a one-shot `findBy`: a router re-renders as its dependent queries land, so
 * an element resolved mid-flight can belong to a pass React has already replaced — a detached
 * node, which `toBeInTheDocument` correctly rejects. `waitFor` re-queries on every poll, so it
 * only settles on a node that is still mounted.
 */
async function settle(assertion: () => void) {
  await waitFor(assertion, SETTLE);
}

/** Values no learner may ever read, planted in every payload below. */
const LEAK_OBJECT = 'LEAK_OBJECT';
const LEAK_ENUM = 'LEAK_ENUM';
const LEAK_REF = 'LEAK_REF';
const LEAK_REQUEST = 'LEAK_REQUEST';
const LEAK_PROVIDER = 'LEAK_PROVIDER';

const LEAKED = [LEAK_OBJECT, LEAK_ENUM, LEAK_REF, LEAK_REQUEST, LEAK_PROVIDER];

/** The structural shapes of a backend payload, which must not appear either. */
const STRUCTURAL = ['后端原文', '原始返回数据', '接口原文', 'request_id', 'agent_run_id', 'service_key', '{"', '":', '['];

function expectNothingLeaked(container: HTMLElement) {
  const text = container.textContent ?? '';
  for (const marker of [...LEAKED, ...STRUCTURAL]) {
    expect(text, `leaked into the learner's reading surface: ${marker}`).not.toContain(marker);
  }
  // A JSON body is the shape of the transport, not a fact: no rendered node may be a payload.
  const jsonish = Array.from(container.querySelectorAll('*')).filter(
    (element) => element.children.length === 0 && /^\s*[{[]/.test(element.textContent ?? '') && /[":]\s/.test(element.textContent ?? ''),
  );
  expect(jsonish.map((element) => element.textContent), 'a payload was rendered as JSON').toEqual([]);
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockImplementation(async (url: string) => {
    // --- shared context ---
    if (url === '/course-learning/courses') return ok([{ id: 'cs101', name: '数据结构' }]);
    if (url === '/exam/prep/profile') return ok({ configured: true, subjects: [{ id: 'cs408' }] });
    if (url === '/programming/onboarding') return ok({ main_language: 'Python', selected_languages: ['Python'], level: 'basic', onboarding_completed: true });

    // --- Home agenda: an unmapped reason must not surface as a code ---
    if (url === '/learning/agenda') {
      return ok({
        items: [
          {
            action_type: 'review',
            service_namespace: 'course_learning',
            domain_context: { course_id: LEAK_REF },
            source_type: 'review',
            source_id: LEAK_REF,
            title: '先订正线性表的错题',
            summary: '这门课程里有到期未订正的错题。',
            priority_reason: LEAK_ENUM,
            deep_link: '/review',
            due_at: null,
            facts: {
              wrong_count: 3,
              attempts: 5,
              [LEAK_OBJECT]: LEAK_OBJECT,
              internal_ref: { [LEAK_OBJECT]: LEAK_OBJECT },
              schedule: { [LEAK_OBJECT]: LEAK_OBJECT },
            },
            status: LEAK_ENUM,
            resolved_by: '订正错题',
          },
        ],
      });
    }
    if (url === '/learning/agenda/explain') {
      return ok({ priority_rules: {}, policy_version: LEAK_ENUM, agenda: { [LEAK_OBJECT]: LEAK_OBJECT } });
    }

    // --- Course materials: an unmapped parse_status / file_type must not print ---
    if (url === '/course-learning/courses/{course_id}/materials') {
      return ok({
        course_id: LEAK_REF,
        total: 1,
        items: [
          {
            id: LEAK_REF,
            original_filename: '线性表.pdf',
            file_size: 2048,
            file_type: LEAK_ENUM,
            parse_status: LEAK_ENUM,
            chunk_count: 12,
            [LEAK_OBJECT]: LEAK_OBJECT,
          },
        ],
      });
    }

    // --- Course wrong answers: internal ids and an unmapped status ---
    if (url === '/course-learning/courses/{course_id}/wrong-answers') {
      return ok({
        total: 1,
        items: [
          {
            wrong_record_id: 9,
            status: LEAK_ENUM,
            stem: '顺序表的插入复杂度？',
            user_answer: 'O(n)',
            reference_answer: 'O(n)',
            source_attempt_id: LEAK_REF,
            [LEAK_OBJECT]: LEAK_OBJECT,
          },
        ],
      });
    }

    // --- Course state: a nested object full of names the product cannot say ---
    if (url === '/course-learning/courses/{course_id}/state') {
      return ok({
        knowledge_progress: { total_points: 12, [LEAK_OBJECT]: LEAK_OBJECT },
        practice: { attempts: 4, [LEAK_OBJECT]: LEAK_OBJECT },
        wrong_answers: { active: 2, [LEAK_OBJECT]: LEAK_OBJECT },
        review: { due: 1, [LEAK_OBJECT]: LEAK_OBJECT },
        plan: { open: 3, [LEAK_OBJECT]: LEAK_OBJECT },
        recent_activity: [{ event_id: LEAK_REF, event_type: 'question_answered', occurred_at: '2026-09-20T08:00:00Z' }],
        [LEAK_OBJECT]: LEAK_OBJECT,
      });
    }
    if (url === '/course-dashboard') return ok({ course_name: '数据结构', next_action: '继续线性表练习' });
    if (url === '/knowledge-points') return ok({ items: [{ id: LEAK_REF, title: '线性表', [LEAK_OBJECT]: LEAK_OBJECT }] });
    if (url === '/knowledge-map') return ok({ total_points: 3, [LEAK_OBJECT]: LEAK_OBJECT });
    if (url === '/course-learning/study-plan') return ok({ tasks: [] });
    if (url === '/course-learning/entitlements') return ok({ service_key: LEAK_REF });
    if (url === '/membership/entitlements') return ok({ service_key: LEAK_REF });

    // --- 11408: the runtime state object, including its internal references ---
    if (url === '/exam/prep/scientific/capabilities') {
      return ok({ components: [{ component: 'student_twin', user_visible: true, mode: 'USER_VISIBLE_PREVIEW' }] });
    }
    if (url === '/exam/prep/scientific/student-twin') {
      return ok({
        metadata: { component: 'student_twin', mode: 'PREVIEW', blockers: [], semantics: LEAK_OBJECT },
        input_summary: { event_count: 4, excluded_reasons: { [LEAK_ENUM]: 1 }, eligibility_rule: LEAK_OBJECT },
        state: {
          events_seen: 4,
          concepts: [`${LEAK_REF}.one`, `${LEAK_REF}.two`],
          user_id: LEAK_REF,
          global_ability: 0.8125,
          [LEAK_OBJECT]: LEAK_OBJECT,
        },
      });
    }
    if (url === '/exam/11408/subjects/{subject_key}/dashboard-summary') {
      return ok({ subject_key: 'data_structure', subject_name: '数据结构', overview: { total_chapters: 8, total_knowledge_points: 64, learned_percent: 25, study_minutes: 20 }, today_plan: [], materials: { total_materials: 0 }, quota: {} });
    }
    if (url === '/exam/11408/chapter-practice/outline') return ok({ module_key: 'data_structure', chapters: [] });
    if (url === '/exam/11408/subjects/data_structure/study-plan') return ok({ tasks: [] });

    // --- Programming: exercise payloads and their internal references ---
    if (url === '/programming/home') return ok({ stats: { streak_days: 3, momentum: '今日已学习', [LEAK_OBJECT]: LEAK_OBJECT, last_activity_date: '2026-09-20' } });
    if (url === '/programming/exercises') {
      return ok({
        items: [
          {
            id: 7,
            title: '两数之和',
            difficulty: '入门',
            source_label: '原创题目',
            source_type: LEAK_ENUM,
            [LEAK_OBJECT]: LEAK_OBJECT,
          },
        ],
      });
    }
    if (url === '/programming/exercises/{exercise_id}') {
      return ok({
        exercise: {
          id: 7,
          title: '两数之和',
          statement: '给定一个整数数组，返回两个数的下标。',
          difficulty: '入门',
          language: 'Python',
          source_label: '原创题目',
          source_type: LEAK_ENUM,
          provider: LEAK_PROVIDER,
          [LEAK_OBJECT]: LEAK_OBJECT,
        },
        [LEAK_OBJECT]: LEAK_OBJECT,
      });
    }
    if (url === '/programming/records') {
      return ok({
        items: [
          {
            event_id: LEAK_REF,
            event_type: 'code_submitted',
            occurred_at: '2026-09-20T08:00:00Z',
            context: { exercise_id: LEAK_REF },
            source: { type: 'programming_exercise', id: LEAK_REF },
            summary: { correct: true, passed_count: 5, total_count: 5, capability: LEAK_PROVIDER, question_source_id: LEAK_REF },
          },
        ],
      });
    }
    if (url === '/programming/records/summary') return ok({ runs: 2, tests: 3, [LEAK_OBJECT]: LEAK_OBJECT });
    if (url === '/programming/state') return ok({ runs: 2, [LEAK_OBJECT]: LEAK_OBJECT, [LEAK_ENUM]: 1 });
    if (url === '/programming/plan') return ok({ tasks: [], [LEAK_OBJECT]: LEAK_OBJECT });

    // --- membership / usage: real ledger columns only, never tokens or provider cost ---
    if (url === '/subscription') return ok({ tier: 'free', [LEAK_OBJECT]: LEAK_OBJECT });
    if (url === '/subscription/plans') return ok({ plans: { free: { label: 'Free' } } });
    if (url === '/usage/summary') {
      return ok({ periods: { daily: { budget: 20, remaining: 18, reserved: 0, settled: 2 }, weekly: { budget: 100, remaining: 98, reserved: 0, settled: 2 } } });
    }
    if (url === '/me/profile') return ok({ username: 'test_learner', [LEAK_OBJECT]: LEAK_OBJECT });

    // --- reports ---
    if (url === '/reports') return ok({ report_period: { days: 7 }, structured_metrics: {}, data_coverage: {} });
    if (url === '/exam/prep/scientific/learner-state') return ok({ metadata: { mode: 'UNAVAILABLE' } });

    // Anything else is a route this guard has not been taught; an empty object keeps the surface
    // renderable without pretending it received a payload it did not.
    return ok({});
  });
  post.mockImplementation(async () => ok({}));
});

describe('LEARNER_METADATA_LEAKAGE_GUARD · Home', () => {
  it('states an unmapped agenda reason as unavailable instead of printing the code', async () => {
    const { container } = renderApp('/');

    await settle(() => expect(screen.getByText('先订正线性表的错题')).toBeInTheDocument());
    expect(screen.getByText('推荐依据暂不可显示')).toBeInTheDocument();
    expectNothingLeaked(container);
  });

  it('shows the agenda facts it can name and drops the rest', async () => {
    const { container } = renderApp('/');

    await settle(() => expect(screen.getByText('先订正线性表的错题')).toBeInTheDocument());
    expect(within(container).getByText('错误次数')).toBeInTheDocument();
    expectNothingLeaked(container);
  });
});

describe('LEARNER_METADATA_LEAKAGE_GUARD · Course', () => {
  it('renders materials without the payload or its unmapped codes', async () => {
    const { container } = renderApp('/course/cs101/materials');

    expect(await screen.findByText('线性表.pdf')).toBeInTheDocument();
    expectNothingLeaked(container);
  });

  it('renders wrong answers with the real facts and none of the internal references', async () => {
    const { container } = renderApp('/course/cs101/wrong');

    expect(await screen.findByText('顺序表的插入复杂度？')).toBeInTheDocument();
    expectNothingLeaked(container);
  });

  it('renders the course state without dumping its nested objects', async () => {
    const { container } = renderApp('/course/cs101/state');

    expect(await screen.findByRole('heading', { name: '已记录的学习事实' })).toBeInTheDocument();
    expectNothingLeaked(container);
  });
});

describe('LEARNER_METADATA_LEAKAGE_GUARD · 11408', () => {
  it('renders the state preview without the runtime’s internal fields', async () => {
    const { container } = renderApp('/exam/cs408/state');

    expect(await screen.findByRole('heading', { name: '学习状态实验视图' })).toBeInTheDocument();
    expect(await screen.findByText('本次计算使用的事件数')).toBeInTheDocument();
    // The internal quantity and the learner's reference are absent even though the payload had them.
    expect(container.textContent).not.toContain('0.8125');
    expectNothingLeaked(container);
  });
});

describe('LEARNER_METADATA_LEAKAGE_GUARD · Programming', () => {
  it('lists exercises without an unmapped type or the payload behind them', async () => {
    const { container } = renderApp('/programming/python');

    expect(await screen.findByText('两数之和')).toBeInTheDocument();
    expectNothingLeaked(container);
  });

  it('renders the workbench statement without the raw response', async () => {
    const { container } = renderApp('/programming/python/projects/7');

    expect(await screen.findByText('给定一个整数数组，返回两个数的下标。')).toBeInTheDocument();
    expectNothingLeaked(container);
  });

  it('renders the records event without its source references or capability name', async () => {
    const { container } = renderApp('/programming/python/records');

    expect(await screen.findByText('提交代码')).toBeInTheDocument();
    expect(within(container).getByText('通过测试数')).toBeInTheDocument();
    expectNothingLeaked(container);
  });
});

describe('LEARNER_METADATA_LEAKAGE_GUARD · Workbench AI result', () => {
  it('shows the settled credit cost in product language and never the request identity', async () => {
    post.mockImplementation(async (url: string) => {
      if (url === '/code/analyze') {
        return ok({
          answer: '这里的问题在于循环边界少了一次。',
          request_id: LEAK_REQUEST,
          usage: { actual_credits: 2, input_tokens: 4000, output_tokens: 900, provider: LEAK_PROVIDER },
          [LEAK_OBJECT]: LEAK_OBJECT,
        });
      }
      return ok({});
    });

    const user = userEvent.setup();
    const { container } = renderApp('/programming/python/projects/7');

    const code = await screen.findByLabelText('代码');
    await user.type(code, 'for i in range(0): pass');
    const question = await screen.findByLabelText('要分析的问题');
    await user.type(question, '为什么不对？');
    await user.click(screen.getByRole('button', { name: 'AI Debug' }));

    expect(await screen.findByText('这里的问题在于循环边界少了一次。')).toBeInTheDocument();
    expect(screen.getByText('本次使用 2 点 AI 额度')).toBeInTheDocument();
    // tokens, the provider's own bookkeeping and the request id are not the learner's to read.
    expect(container.textContent).not.toContain('4000');
    expectNothingLeaked(container);
  });
});
