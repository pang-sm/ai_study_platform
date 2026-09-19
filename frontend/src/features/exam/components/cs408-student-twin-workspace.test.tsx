import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408StudentTwinWorkspace } from './cs408-student-twin-workspace';

type Preview = components['schemas']['StudentTwinPreviewResponse'];
const hooks = vi.hoisted(() => ({ useStudentTwinPreview: vi.fn() }));
vi.mock('@/features/exam/api/student-twin', () => ({ useStudentTwinPreview: hooks.useStudentTwinPreview }));
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: globalThis.Record<string, string | undefined> }) => <a href={`${to}${search?.module ? `?module=${search.module}` : ''}`}>{children}</a> }));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

const preview = (mode = 'PREVIEW'): Preview => ({
  metadata: { component: 'student_twin', mode, controls_product_decision: false, writes_learner_fact: false, generated_at: '2026-09-19T14:32:00+00:00', blockers: mode === 'UNAVAILABLE' ? ['SCIENTIFIC_RUNTIME_UNAVAILABLE'] : [] },
  input_summary: { event_count: 2, event_types: { question_answered: 2 }, excluded_event_count: 0, excluded_reasons: {}, scanned_events: 2, bounded_to: 500, scope: { exam_module_id: 'operating_system' }, eligibility_rule: 'answered factual events only', semantics: 'deterministic state replay' },
  state: mode === 'UNAVAILABLE' ? null : { engagement_state: 'steady', evidence_count: 2 },
});

describe('Cs408StudentTwinWorkspace', () => {
  it('renders only the typed experiment preview with deterministic-engine wording and no learner writes', () => {
    hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: false, data: preview(), refetch: vi.fn() });
    render(<Cs408StudentTwinWorkspace moduleKey="operating_system" />);
    expect(hooks.useStudentTwinPreview).toHaveBeenCalledWith('operating_system');
    expect(screen.getByRole('heading', { name: '学习状态实验视图' })).toBeInTheDocument();
    expect(screen.getByText('自研确定性学习状态引擎')).toBeInTheDocument();
    expect(screen.getByText('真实学习事件')).toBeInTheDocument();
    expect(screen.getByText('仅实验展示，不控制学习决策')).toBeInTheDocument();
    expect(screen.getByText('engagement_state')).toBeInTheDocument();
    expect(screen.queryByText(/掌握度|能力预测|掌握概率|神经网络/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /保存|更新|修改|提交/ })).not.toBeInTheDocument();
  });

  it('shows bounded blockers and the dedicated unavailable state without hiding either', () => {
    hooks.useStudentTwinPreview.mockReturnValue({ isPending: false, isError: false, data: preview('UNAVAILABLE'), refetch: vi.fn() });
    render(<Cs408StudentTwinWorkspace />);
    expect(screen.getByText('学习状态服务暂时不可用')).toBeInTheDocument();
    expect(screen.getByText('SCIENTIFIC_RUNTIME_UNAVAILABLE')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '计算机网络' })).toHaveAttribute('href', '/exam/cs408/state?module=computer_network');
  });
});
