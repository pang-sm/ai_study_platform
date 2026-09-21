import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408StudentTwinWorkspace } from './cs408-student-twin-workspace';

type Preview = components['schemas']['StudentTwinPreviewResponse'];
const hooks = vi.hoisted(() => ({ useStudentTwinPreview: vi.fn(), useScientificCapabilities: vi.fn() }));
vi.mock('@/features/exam/api/student-twin', () => ({ useStudentTwinPreview: hooks.useStudentTwinPreview, useScientificCapabilities: hooks.useScientificCapabilities }));
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: globalThis.Record<string, string | undefined> }) => <a href={`${to}${search?.module ? `?module=${search.module}` : ''}`}>{children}</a> }));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

const preview = (mode = 'PREVIEW'): Preview => ({
  metadata: { component: 'student_twin', mode, controls_product_decision: false, writes_learner_fact: false, generated_at: '2026-09-19T14:32:00+00:00', blockers: mode === 'UNAVAILABLE' ? ['SCIENTIFIC_RUNTIME_UNAVAILABLE'] : [] },
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
    { component: 'learner_state', mode: 'SHADOW_NOT_USER_VISIBLE', available: false, user_visible: false, controls_product_decision: false, writes_learner_fact: false, blockers: ['ONTOLOGY_MISMATCH'], semantics: 'next-response probability' },
    { component: 'misconception_v2', mode: 'SHADOW', available: false, user_visible: false, controls_product_decision: false, writes_learner_fact: false, blockers: ['MISSING_INPUT'], semantics: 'shadow diagnostic' },
  ],
});

describe('Cs408StudentTwinWorkspace', () => {
  it('renders Student Twin as the sole visible experiment, with the typed factual evidence count and records link', () => {
    hooks.useScientificCapabilities.mockReturnValue({ isPending: false, isError: false, data: capabilities() });
    hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: false, data: preview(), refetch: vi.fn() });
    render(<Cs408StudentTwinWorkspace moduleKey="operating_system" />);
    expect(hooks.useStudentTwinPreview).toHaveBeenCalledWith('operating_system', true);
    expect(screen.getByRole('heading', { name: '学习状态实验视图' })).toBeInTheDocument();
    expect(screen.getByText('自研确定性学习状态引擎')).toBeInTheDocument();
    expect(screen.getByText('基于真实作答与学习事件')).toBeInTheDocument();
    expect(screen.getByText('基于真实学习记录计算；仅用于实验性展示；不控制判分，不修改知识状态、错题或学习计划。')).toBeInTheDocument();
    expect(screen.getByText('本次计算使用的事实依据')).toBeInTheDocument();
    expect(screen.getByText('2 条')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看学习记录' })).toHaveAttribute('href', '/exam/cs408/records?module=operating_system');
    // The summary is read through the product's own labels, so the runtime's field names, the
    // learner's reference and the engine's internal quantity never reach the page.
    expect(screen.getByText('本次计算使用的事件数')).toBeInTheDocument();
    expect(screen.getByText('涉及知识点')).toBeInTheDocument();
    expect(screen.getByText('2 个')).toBeInTheDocument();
    expect(screen.queryByText(/events_seen|concepts|user_ref|global_ability|0\.8125/)).not.toBeInTheDocument();
    expect(screen.queryByText(/掌握度|能力预测|掌握概率|神经网络|learner_state|misconception_v2|SHADOW|ONTOLOGY_MISMATCH/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /保存|更新|修改|提交/ })).not.toBeInTheDocument();
  });

  it('shows the scientific unavailable state without internal runtime blockers', () => {
    hooks.useScientificCapabilities.mockReturnValue({ isPending: false, isError: false, data: capabilities() });
    hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: false, data: preview('UNAVAILABLE'), refetch: vi.fn() });
    render(<Cs408StudentTwinWorkspace />);
    expect(screen.getByText('学习状态服务暂时不可用')).toBeInTheDocument();
    expect(screen.queryByText('SCIENTIFIC_RUNTIME_UNAVAILABLE')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '计算机网络' })).toHaveAttribute('href', '/exam/cs408/state?module=computer_network');
  });

  it('keeps the shell bounded and does not request or expose Student Twin when capabilities do not make it visible', () => {
    hooks.useScientificCapabilities.mockReturnValue({ isPending: false, isError: false, data: capabilities(false) });
    hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: false, data: preview(), refetch: vi.fn() });
    render(<Cs408StudentTwinWorkspace />);
    expect(screen.getByText('学习状态实验暂时不可展示')).toBeInTheDocument();
    expect(screen.queryByText('状态引擎输出')).not.toBeInTheDocument();
    expect(screen.queryByText(/learner_state|misconception_v2|SHADOW|MISSING_INPUT/)).not.toBeInTheDocument();
  });

  it('uses bounded failure handling when the capabilities directory fails', () => {
    hooks.useScientificCapabilities.mockReturnValue({ isPending: false, isError: true, data: undefined });
    hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: false, data: undefined, refetch: vi.fn() });
    render(<Cs408StudentTwinWorkspace />);
    expect(screen.getByText('暂时无法确认学习状态实验是否可展示')).toBeInTheDocument();
    expect(screen.queryByText(/Error|blocker|runtime|learner_state|misconception_v2/i)).not.toBeInTheDocument();
  });
});
