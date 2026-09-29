import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408StudentTwinWorkspace } from './cs408-student-twin-workspace';

type Preview = components['schemas']['StudentTwinPreviewResponse'];

const hooks = vi.hoisted(() => ({
  useStudentTwinPreview: vi.fn(),
  useScientificCapabilities: vi.fn(),
  useCs408DashboardSummaries: vi.fn(),
  useCs408LearningRecords: vi.fn(),
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
vi.mock('@/features/exam/api/learning-records', () => ({ useCs408LearningRecords: hooks.useCs408LearningRecords }));
vi.mock('@/features/exam/api/wrong-answers', () => ({ useWrongAnswers: hooks.useWrongAnswers }));
vi.mock('@/features/exam/api/review-summary', () => ({ useExamReviewSummary: hooks.useExamReviewSummary }));
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: globalThis.Record<string, string | undefined> }) => <a href={`${to}${search?.module ? `?module=${search.module}` : ''}`}>{children}</a> }));
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
function summary(overrides: { points?: number; learned?: number; minutes?: number; plan?: number } = {}) {
  return {
    subject_key: 'operating_system', subject_name: '操作系统',
    overview: { total_chapters: 8, total_knowledge_points: overrides.points ?? 100, learned_percent: overrides.learned ?? 30, study_minutes: overrides.minutes ?? 120 },
    today_plan: Array.from({ length: overrides.plan ?? 2 }, (_, index) => ({ task_id: index + 1, title: `任务 ${index + 1}`, task_type: 'knowledge', status: 'not_started', due_date: '2026-10-01' })),
    materials: { lecture_notes: 0, exercises: 0, references: 0, code_examples: 0, total_materials: 0 },
    quota: { ai_chat: { used: 0, limit: 5, remaining: 5, unit: '次' }, ai_question: { used: 0, limit: 5, remaining: 5, unit: '次' }, material_upload: { used: 0, limit: 1, remaining: 1, unit: 'MB' } },
  };
}

const ok = (data: unknown) => ({ isPending: false, isError: false, data });
const empty = { isPending: false, isError: false, data: undefined };
const records = (items: unknown[] = []) => ok({ pages: [{ records: items, has_more: false, next_cursor: null }] });

/** Every hook's answer for a learner who has real records, before any case overrides one. */
function setup({ studentTwinVisible = true, engine, engineFailed = false }: { studentTwinVisible?: boolean; engine?: Preview; engineFailed?: boolean } = {}) {
  hooks.useScientificCapabilities.mockReturnValue(ok(capabilities(studentTwinVisible)));
  hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: engineFailed, data: engineFailed ? undefined : engine ?? preview(), refetch: vi.fn() });
  // index 2 is operating_system: the hook answers for the four papers in a fixed order
  hooks.useCs408DashboardSummaries.mockReturnValue([empty, empty, ok(summary()), empty]);
  hooks.useCs408LearningRecords.mockReturnValue(records([{ event_id: 'e1', event_type: 'question_answered', occurred_at: '2026-09-29T07:00:00Z' }]));
  hooks.useWrongAnswers.mockReturnValue(ok({ total: 3, items: [] }));
  hooks.useExamReviewSummary.mockReturnValue(ok({ total: 4, by_status: { due: 4 }, by_namespace: {}, by_source: {}, has_stored_due_dates: true, semantics: '' }));
}

function mount(options = {}) {
  setup(options);
  return render(<Cs408StudentTwinWorkspace moduleKey="operating_system" />);
}

describe('Cs408StudentTwinWorkspace', () => {
  it('leads with the learner figures their records actually hold', () => {
    const { container } = mount();
    expect(screen.getByRole('heading', { name: '学习状态' })).toHaveClass('sr-only');
    expect(screen.getByText('基于你的真实学习记录计算。它不参与判分，也不会改写你的知识状态、错题或学习计划。')).toBeInTheDocument();

    expect(screen.getByRole('heading', { name: '你的学习概况' })).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();          // 30% of 100 knowledge points
    expect(screen.getByText('120')).toBeInTheDocument();         // minutes studied
    expect(screen.getByText('4')).toBeInTheDocument();           // review due
    expect(screen.getByText('3')).toBeInTheDocument();           // active wrong answers

    expect(screen.getByRole('heading', { name: '最近学习' })).toBeInTheDocument();
    expect(screen.getByText('2026 年 9 月 29 日')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看学习记录' })).toHaveAttribute('href', '/exam/cs408/records?module=operating_system');
    expect(container.textContent).not.toMatch(/实验|实验视图|自研|student.?twin|scientific.?runtime|状态引擎|确定性/);
  });

  it('shows the engine summary as an enhancement when it has something to say', () => {
    mount();
    expect(screen.getByText('本次状态依据的学习记录')).toBeInTheDocument();
    expect(screen.getByText('2 条')).toBeInTheDocument();
    expect(screen.getByText('涉及知识点')).toBeInTheDocument();
    expect(screen.getByText('2 个')).toBeInTheDocument();
    expect(screen.queryByText(/events_seen|concepts|user_ref|global_ability|0\.8125/)).not.toBeInTheDocument();
  });

  it('keeps the learner figures when the engine has nothing to replay', () => {
    // REGRESSION GUARD. This is the production state that shipped as "学习状态服务暂时不可用":
    // the account had no eligible practice facts, the engine honestly answered UNAVAILABLE, and
    // the page turned that into an outage message. It is a statement about the record, not the
    // service, and everything above it must survive.
    const { container } = mount({ engine: preview('UNAVAILABLE') });

    expect(screen.queryByText('学习状态服务暂时不可用')).not.toBeInTheDocument();
    expect(screen.getByText('学习记录还不够。完成一次练习后，这里会根据你的作答更新。')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '你的学习概况' })).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
    expect(container.textContent).not.toContain('NO_ELIGIBLE_PRACTICE_EVENTS_IN_SCOPE');
  });

  it('keeps the learner figures when the engine request fails', () => {
    const { container } = mount({ engineFailed: true });

    expect(screen.queryByText('学习状态服务暂时不可用')).not.toBeInTheDocument();
    expect(screen.getByText('这一部分暂时读不到，上面的学习概况不受影响。')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/实验|自研|student.?twin|scientific.?runtime/);
  });

  it('does not request the engine when the capability does not make it visible', () => {
    mount({ studentTwinVisible: false });
    expect(hooks.useStudentTwinPreview).toHaveBeenCalledWith('operating_system', false);
    expect(screen.getByText('当前暂不展示这一部分。')).toBeInTheDocument();
  });

  it('says so when the learner has not started, instead of showing zeroes as a fact', () => {
    setup({ engine: preview('UNAVAILABLE') });
    hooks.useCs408DashboardSummaries.mockReturnValue([empty, empty, ok(summary({ learned: 0, minutes: 0, plan: 0 })), empty]);
    hooks.useCs408LearningRecords.mockReturnValue(records());
    hooks.useWrongAnswers.mockReturnValue(ok({ total: 0, items: [] }));
    hooks.useExamReviewSummary.mockReturnValue(ok({ total: 0, by_status: {}, by_namespace: {}, by_source: {}, has_stored_due_dates: false, semantics: '' }));
    render(<Cs408StudentTwinWorkspace moduleKey="operating_system" />);

    expect(screen.getByText('还没有开始学习这个科目。选一个知识点开始，这里会记下进度。')).toBeInTheDocument();
    expect(screen.getByText('还没有学习记录。')).toBeInTheDocument();
  });
});
