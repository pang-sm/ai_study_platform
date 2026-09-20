import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408StudyPlanWorkspace } from './cs408-study-plan-workspace';

type Plan = components['schemas']['ExamStudyPlanResponse'];

const plan = (subject_key: string, subject_name: string, tasks: Plan['tasks']): Plan => ({
  course_id: `${subject_key}_11408`, course_name: subject_name, subject_key, subject_name,
  settings: { learning_goal: '', start_date: null, daily_hours: null, weekly_days: null, review_strategy: 'sequential', show_completed: true },
  stats: { total_knowledge_points: 12, mastered: 0, total_sections: 2, sections_completed: 0, sections_learning: 0, sections_not_started: 2, overall_progress: 0, overall_status: 'not_started' },
  review_interval_days: 7, chapters: [], tasks,
});

const task: Plan['tasks'][number] = {
  id: 7, username: 'learner', subject_key: 'operating_system', subject_name: '操作系统', title: '理解虚拟内存', knowledge_point_name: '虚拟内存', scope_type: 'single', task_type: 'knowledge', computed_status: 'in_progress', completion_reason: '已有学习记录', action_target: 'knowledge_map', due_date: '2026-10-01', note: '', created_at: null, updated_at: null, status: 'in_progress', primary_knowledge: '', secondary_knowledge: '',
};

const refetch = vi.fn();
let entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1', features: {} }, refetch };
let plans: Array<{ isPending: boolean; isError: boolean; data?: Plan; refetch: typeof refetch }> = [];
const hooks = vi.hoisted(() => ({ useCs408StudyPlans: vi.fn() }));

vi.mock('@/features/exam/api/cs408-study-plan', () => ({
  useExamPlanEntitlement: () => entitlement,
  useCs408StudyPlans: hooks.useCs408StudyPlans,
}));
vi.mock('@tanstack/react-router', () => ({ Link: ({ children, to, search }: { children: React.ReactNode; to: string; search?: Record<string, string | number | undefined> }) => {
  const parameters = new URLSearchParams(); Object.entries(search ?? {}).forEach(([key, value]) => { if (value !== undefined) parameters.set(key, String(value)); });
  return <a href={`${to}${parameters.size ? `?${parameters}` : ''}`}>{children}</a>;
} }));
vi.mock('./exam-page-shell', () => ({ ExamPageShell: ({ children }: { children: React.ReactNode }) => children }));

describe('Cs408StudyPlanWorkspace', () => {
  hooks.useCs408StudyPlans.mockImplementation(() => plans);
  it('treats a missing learning_plan feature as locked and does not mount plan content', () => {
    plans = [];
    render(<Cs408StudyPlanWorkspace />);
    expect(screen.getByRole('heading', { name: '学习计划' })).toBeInTheDocument();
    expect(screen.getByText('当前档位暂未开放学习计划')).toBeInTheDocument();
    expect(screen.queryByText('理解虚拟内存')).not.toBeInTheDocument();
    expect(hooks.useCs408StudyPlans).toHaveBeenLastCalledWith(false);
  });

  it('names the unified tier the lock requires, not a legacy plan code', () => {
    // ACCEL_PRODUCT_S10 PART D: the locked state has to tell the learner what to change, in
    // the vocabulary the membership page actually offers. `monthly_sprint` named no tier.
    entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'free', policy_version: 'v1', features: { learning_plan: { allowed: false, required_tier: 'standard', required_capability: 'planning.generate' } } }, refetch };
    plans = [];
    render(<Cs408StudyPlanWorkspace />);
    expect(screen.getByText(/需要 Standard 及以上档位/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看会员档位与权益' })).toHaveAttribute('href', '/membership');
    expect(screen.queryByText(/monthly_sprint|备考方案/)).not.toBeInTheDocument();
  });

  it('renders the canonical ledger and factual action without a completion control', () => {
    entitlement = { isPending: false, isError: false, data: { service_key: 'exam_11408', current_tier: 'standard', policy_version: 'v1', features: { learning_plan: { allowed: true, required_tier: 'standard', required_capability: 'planning.generate' } } }, refetch };
    plans = [{ isPending: false, isError: false, data: plan('operating_system', '操作系统', [task, { ...task, id: 8, computed_status: 'not_started', status: 'not_started' }, { ...task, id: 9, computed_status: 'completed', status: 'completed' }]), refetch }];
    render(<Cs408StudyPlanWorkspace />);
    expect(screen.getAllByText('理解虚拟内存')).toHaveLength(3);
    expect(screen.getByText('进行中')).toBeInTheDocument();
    expect(screen.getByText('未开始')).toBeInTheDocument();
    expect(screen.getByText('已完成')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '继续学习' })).toHaveAttribute('href', '/exam/cs408/knowledge?module=operating_system');
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /完成|标记/i })).not.toBeInTheDocument();
  });
});
