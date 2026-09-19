import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryHistory, createRootRoute, createRouter } from '@tanstack/react-router';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '@/types/api';
import { Cs408Workspace } from './cs408-workspace';

type DashboardSummary = components['schemas']['ExamSubjectDashboardSummaryResponse'];

const summary = (subject_key: string, subject_name: string): DashboardSummary => ({
  subject_key,
  subject_name,
  overview: { total_chapters: 8, total_knowledge_points: 64, learned_percent: 25, study_minutes: 20 },
  today_plan: [],
  materials: { lecture_notes: 0, exercises: 0, references: 0, code_examples: 0, total_materials: 0 },
  quota: {
    ai_chat: { used: 0, limit: 1, remaining: 1, unit: '次' },
    ai_question: { used: 0, limit: 1, remaining: 1, unit: '次' },
    material_upload: { used: 0, limit: 1, remaining: 1, unit: 'MB' },
  },
});

const retry = vi.fn();
vi.mock('@/features/exam/api/dashboard-summary', () => ({
  cs408Modules: [
    { key: 'data_structure', number: '01', name: '数据结构' },
    { key: 'computer_organization', number: '02', name: '计算机组成原理' },
    { key: 'operating_system', number: '03', name: '操作系统' },
    { key: 'computer_network', number: '04', name: '计算机网络' },
  ],
  useCs408DashboardSummaries: () => [
    { isPending: false, isError: false, data: summary('data_structure', '数据结构'), refetch: retry },
    { isPending: false, isError: false, data: summary('computer_organization', '计算机组成原理'), refetch: retry },
    { isPending: false, isError: true, data: undefined, refetch: retry },
    { isPending: false, isError: false, data: summary('computer_network', '计算机网络'), refetch: retry },
  ],
}));

describe('Cs408Workspace', () => {
  it('keeps successful modules visible when one module summary fails and offers local retry', async () => {
    const router = createRouter({ routeTree: createRootRoute({ component: Cs408Workspace }), history: createMemoryHistory() });
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole('heading', { name: '数据结构' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '计算机组成原理' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '操作系统' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '计算机网络' })).toBeInTheDocument();
    expect(screen.getByText('此模块暂时无法加载。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重试操作系统模块' })).toBeInTheDocument();
    expect(screen.getAllByText('知识点已学习比例 25%')).toHaveLength(3);
    expect(screen.getByRole('navigation', { name: 'CS408 工作区工具' })).not.toHaveAttribute('tabindex');
    expect(screen.getByRole('link', { name: '知识脉络' })).toHaveAttribute('href', '/exam/cs408/knowledge?module=data_structure');
    expect(screen.getByRole('link', { name: '学习记录' })).toHaveAttribute('href', '/exam/cs408/records');
    expect(screen.getByRole('link', { name: '学习状态' })).toHaveAttribute('href', '/exam/cs408/state');
    expect(screen.queryByText(/额度|ai_chat|资料总数/i)).not.toBeInTheDocument();
  });
});
