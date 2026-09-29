import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408StudentTwinWorkspace, statusSentence } from './cs408-student-twin-workspace';

type Preview = components['schemas']['StudentTwinPreviewResponse'];

const hooks = vi.hoisted(() => ({
  useStudentTwinPreview: vi.fn(),
  useScientificCapabilities: vi.fn(),
  useCs408DashboardSummaries: vi.fn(),
  useWrongAnswers: vi.fn(),
  useExamReviewSummary: vi.fn(),
}));

vi.mock('@/features/exam/api/student-twin', () => ({
  useStudentTwinPreview: hooks.useStudentTwinPreview,
  useScientificCapabilities: hooks.useScientificCapabilities,
}));
vi.mock('@/features/exam/api/dashboard-summary', () => ({
  useCs408DashboardSummaries: hooks.useCs408DashboardSummaries,
  cs408Modules: [
    { key: 'data_structure', number: '01', name: '数据结构' },
    { key: 'computer_organization', number: '02', name: '计算机组成原理' },
    { key: 'operating_system', number: '03', name: '操作系统' },
    { key: 'computer_network', number: '04', name: '计算机网络' },
  ],
}));
vi.mock('@/features/exam/api/wrong-answers', () => ({ useWrongAnswers: hooks.useWrongAnswers }));
vi.mock('@/features/exam/api/review-summary', () => ({ useExamReviewSummary: hooks.useExamReviewSummary }));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

const preview = (mode = 'PREVIEW'): Preview => ({
  metadata: { component: 'student_twin', mode, controls_product_decision: false, writes_learner_fact: false, generated_at: '2026-09-19T14:32:00+00:00', blockers: mode === 'UNAVAILABLE' ? ['NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE'] : [] },
  input_summary: { event_count: 2, event_types: { question_answered: 2 }, excluded_event_count: 0, excluded_reasons: {}, scanned_events: 2, bounded_to: 500, scope: { exam_module_id: 'operating_system' }, eligibility_rule: 'answered factual events only', semantics: 'deterministic state replay' },
  // The runtime's own keys: a count the product can say, the concepts it saw, and two fields the
  // product must never show — the learner's internal reference and the engine's own quantity.
  state: mode === 'UNAVAILABLE' ? null : { events_seen: 2, concepts: ['os.paging', 'os.scheduling'], user_ref: 'user_ab12', global_ability: 0.8125 },
});

const capabilities = (studentTwinVisible = true) => ({
  generated_at: '2026-09-19T14:32:00+00:00',
  source_class: 'product-facing',
  terminology: {},
  totals: { components: 5, available: 1, user_visible: studentTwinVisible ? 1 : 0, controls_product_decision: 0, writes_learner_fact: 0 },
  components: [
    { component: 'student_twin', mode: 'PREVIEW', available: true, user_visible: studentTwinVisible, controls_product_decision: false, writes_learner_fact: false, blockers: [], semantics: 'deterministic state replay' },
  ],
});

/** One paper's dashboard summary, with only the fields this page reads set to something real. */
function summary(overrides: { points?: number; learned?: number; plan?: number } = {}) {
  return {
    subject_key: 'operating_system', subject_name: '操作系统',
    overview: { total_chapters: 8, total_knowledge_points: overrides.points ?? 100, learned_percent: overrides.learned ?? 30, study_minutes: 120 },
    today_plan: Array.from({ length: overrides.plan ?? 0 }, (_, index) => ({ task_id: index + 1, title: `任务 ${index + 1}`, task_type: 'knowledge', status: 'not_started', due_date: '2026-10-01' })),
    materials: { lecture_notes: 0, exercises: 0, references: 0, code_examples: 0, total_materials: 0 },
    quota: { ai_chat: { used: 0, limit: 5, remaining: 5, unit: '次' }, ai_question: { used: 0, limit: 5, remaining: 5, unit: '次' }, material_upload: { used: 0, limit: 1, remaining: 1, unit: 'MB' } },
  };
}

const ok = (data: unknown) => ({ isPending: false, isError: false, data });
const empty = { isPending: false, isError: false, data: undefined };
const noReview = ok({ total: 0, by_status: {}, by_namespace: {}, by_source: {}, has_stored_due_dates: false, semantics: '' });

interface Setup {
  studentTwinVisible?: boolean;
  engine?: Preview;
  engineFailed?: boolean;
  paper?: ReturnType<typeof summary>;
  due?: number;
  wrong?: number;
  summariesFailed?: boolean;
}

/** Every hook's answer for a learner who has a little real history, before any case overrides one. */
function setup({ studentTwinVisible = true, engine, engineFailed = false, paper, due = 0, wrong = 0, summariesFailed = false }: Setup = {}) {
  hooks.useScientificCapabilities.mockReturnValue(ok(capabilities(studentTwinVisible)));
  hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: engineFailed, data: engineFailed ? undefined : engine ?? preview(), refetch: vi.fn() });
  // index 2 is operating_system: the hook answers for the four papers in a fixed order
  const failed = { isPending: false, isError: true, data: undefined };
  hooks.useCs408DashboardSummaries.mockReturnValue(summariesFailed
    ? [failed, failed, failed, failed]
    : [empty, empty, ok(paper ?? summary({ learned: 30 })), empty]);
  hooks.useWrongAnswers.mockReturnValue(ok({ total: wrong, items: [] }));
  hooks.useExamReviewSummary.mockReturnValue(due > 0
    ? ok({ total: due, by_status: { due }, by_namespace: {}, by_source: {}, has_stored_due_dates: true, semantics: '' })
    : noReview);
}

function mount(options: Setup = {}) {
  setup(options);
  return render(<Cs408StudentTwinWorkspace moduleKey="operating_system" />);
}

/** The strings this page must never carry again — see the round that removed them. */
const REMOVED = [
  '基于你的真实学习记录计算',
  '最近学习',
  '查看学习记录',
  '查看学习报告',
  '学习状态摘要',
  '学习状态服务暂时不可用',
  '你的学习概况',
  '学习记录还不够',
  '还没有学习记录',
  '学习时长',
  '还没有开始学习这个科目',
];

describe('Cs408StudentTwinWorkspace', () => {
  it('states where the learner stands, and nothing else', () => {
    const { container } = mount({ paper: summary({ points: 100, learned: 18 }), due: 3, wrong: 2 });

    expect(screen.getByRole('heading', { name: '学习状态' })).toBeInTheDocument();
    expect(screen.getByText('已学习')).toBeInTheDocument();
    expect(screen.getByText('/ 100')).toBeInTheDocument();
    expect(screen.getByText('待复习')).toBeInTheDocument();
    expect(screen.getByText('错题')).toBeInTheDocument();
    expect(screen.getByText('今日计划')).toBeInTheDocument();

    for (const removed of REMOVED) {
      expect(container.textContent, `still shows ${removed}`).not.toContain(removed);
    }
    expect(container.textContent).not.toMatch(/实验|实验视图|自研|student.?twin|scientific.?runtime|状态引擎|确定性/);
  });

  it('says what needs attention first, from the figures it is showing', () => {
    mount({ paper: summary({ points: 100, learned: 18 }), due: 3, wrong: 2 });
    expect(screen.getByRole('heading', { name: '当前状态' })).toBeInTheDocument();
    expect(screen.getByText('有 3 项复习已经到期，建议先完成复习。')).toBeInTheDocument();
  });

  it('leads with the wrong answers when no review is due', () => {
    mount({ paper: summary({ points: 100, learned: 18 }), wrong: 2 });
    expect(screen.getByText('当前有 2 道错题待处理。')).toBeInTheDocument();
  });

  it("names today's plan when nothing needs fixing", () => {
    mount({ paper: summary({ points: 100, learned: 0, plan: 2 }) });
    expect(screen.getByText('今天的计划里有 2 项任务。')).toBeInTheDocument();
  });

  it('states progress when there is nothing outstanding', () => {
    mount({ paper: summary({ points: 100, learned: 18 }) });
    expect(screen.getByText('已完成 18 个知识点的学习，暂时没有到期的复习或待处理的错题。')).toBeInTheDocument();
  });

  it('says the zero state once, and shows no other section at all', () => {
    // The clean account: nothing learned, nothing due, no mistakes, no plan.
    const { container } = mount({
      paper: summary({ points: 809, learned: 0, plan: 0 }), due: 0, wrong: 0,
      engine: preview('UNAVAILABLE'),
    });

    expect(screen.getByText('完成一次练习后，这里会更新你的学习状态。')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '当前状态' })).not.toBeInTheDocument();
    // one statement of "no data", not five differently-worded ones
    for (const removed of REMOVED) {
      expect(container.textContent, `still shows ${removed}`).not.toContain(removed);
    }
    expect(screen.getByText('/ 809')).toBeInTheDocument();
  });

  it('keeps every figure when the engine has nothing to replay', () => {
    // REGRESSION GUARD. This is the production state that shipped as "学习状态服务暂时不可用":
    // the account had no eligible practice facts, the engine honestly answered UNAVAILABLE, and
    // the page turned that into an outage message for a record that was simply empty.
    const { container } = mount({ engine: preview('UNAVAILABLE'), paper: summary({ points: 100, learned: 18 }), due: 3 });

    expect(screen.getByText('有 3 项复习已经到期，建议先完成复习。')).toBeInTheDocument();
    expect(screen.getByText('/ 100')).toBeInTheDocument();
    expect(container.textContent).not.toContain('学习状态服务暂时不可用');
    expect(container.textContent).not.toContain('NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE');
    // and it contributes no clause it has nothing to say about
    expect(container.textContent).not.toContain('本次状态参考了');
  });

  it('keeps every figure when the engine request fails', () => {
    const { container } = mount({ engineFailed: true, paper: summary({ points: 100, learned: 18 }), due: 3 });

    expect(screen.getByText('有 3 项复习已经到期，建议先完成复习。')).toBeInTheDocument();
    expect(container.textContent).not.toContain('学习状态服务暂时不可用');
    expect(container.textContent).not.toMatch(/实验|自研|student.?twin|scientific.?runtime/);
  });

  it('does not request the engine when the capability does not make it visible', () => {
    mount({ studentTwinVisible: false, paper: summary({ points: 100, learned: 18 }) });
    expect(hooks.useStudentTwinPreview).toHaveBeenCalledWith('operating_system', false);
  });

  it('adds the engine clause only when the engine actually replayed something', () => {
    mount({ paper: summary({ points: 100, learned: 18 }), due: 3 });
    expect(screen.getByText('本次状态参考了你最近的 2 条作答记录。')).toBeInTheDocument();
  });

  it('never shows a runtime field, even though the payload carried two', () => {
    const { container } = mount({ paper: summary({ points: 100, learned: 18 }), due: 3 });
    expect(container.textContent).not.toContain('0.8125');
    expect(container.textContent).not.toContain('user_ab12');
    expect(container.textContent).not.toMatch(/events_seen|concepts|user_ref|global_ability/);
  });

  it('says it could not read the status instead of failing the page', () => {
    mount({ summariesFailed: true });
    expect(screen.getByText('暂时读不到学习状态，请稍后重试。')).toBeInTheDocument();
  });
});

describe('statusSentence', () => {
  it('never invents a sentence when there is nothing to say', () => {
    expect(statusSentence({ due: 0, wrong: 0, today: 0, learned: 0 })).toBe('');
  });

  it('prefers the thing the learner should act on first', () => {
    // review beats mistakes, which beat today's plan, which beats plain progress
    expect(statusSentence({ due: 1, wrong: 9, today: 9, learned: 9 })).toContain('复习');
    expect(statusSentence({ due: 0, wrong: 9, today: 9, learned: 9 })).toContain('错题');
    expect(statusSentence({ due: 0, wrong: 0, today: 9, learned: 9 })).toContain('计划');
    expect(statusSentence({ due: 0, wrong: 0, today: 0, learned: 9 })).toContain('知识点');
  });
});
