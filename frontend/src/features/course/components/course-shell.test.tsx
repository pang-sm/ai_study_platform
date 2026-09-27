import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
}));

const aiHooks = vi.hoisted(() => ({
  useAiChat: vi.fn(),
  useScopedAiSessions: vi.fn(),
  fetchAiSessionTurns: vi.fn(),
  useModelOptions: vi.fn(),
  useCourseMaterialsForChat: vi.fn(),
}));

vi.mock('@/features/course/api/course', () => ({ ...hooks }));
vi.mock('@/features/ai/api/ai-chat', () => ({
  ...aiHooks,
  answerOf: (value: { answer?: string }) => value.answer ?? '',
  citationsOf: () => [],
  sessionIdOf: () => undefined,
}));

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });

beforeEach(() => {
  hooks.useCourseCatalog.mockReturnValue(
    settled({ courses: [{ course_id: 'cs101', course_name: '数据结构' }] }),
  );
  hooks.useCourseDashboard.mockReturnValue(settled({ course_name: '数据结构' }));
  aiHooks.useAiChat.mockReturnValue({ isPending: false, mutate: vi.fn() });
  aiHooks.useScopedAiSessions.mockReturnValue({
    isPending: false,
    data: [{ id: 11, title: '数据结构课程会话', createdAt: new Date().toISOString() }],
  });
  aiHooks.fetchAiSessionTurns.mockResolvedValue([]);
  aiHooks.useModelOptions.mockReturnValue({
    data: [{ id: 'qwen3.8-flash', label: 'qwen3.8-flash', provider: 'qwen', thinking: false }],
  });
  aiHooks.useCourseMaterialsForChat.mockReturnValue({ data: [{ id: 27, filename: '课程讲义.pdf' }] });
});

describe('course shell', () => {
  it('has no 概览 tab, and the bare course path lands on a working tab', async () => {
    const { router } = renderApp('/course/cs101');

    // The retired overview path redirects to the course's own first surface.
    expect(await screen.findByRole('navigation', { name: '专业学习导航' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/course/cs101/ask');

    const nav = screen.getByRole('navigation', { name: '专业学习导航' });
    expect(within(nav).queryByRole('link', { name: '概览' })).not.toBeInTheDocument();
    expect(within(nav).getByRole('link', { name: '课程问答' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    // Every other surface is still reachable.
    for (const label of ['资料', '知识结构', '学习', '练习', '错题与复习', '计划', '记录', '学习状态']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('names the open course once, through the selector it can be changed from', async () => {
    renderApp('/course/cs101/ask');
    await screen.findByRole('navigation', { name: '专业学习导航' });

    const switcher = screen.getByRole('combobox', { name: '切换课程' });
    expect(switcher).toHaveValue('cs101');
    // The selector is the only place the course is named: no title beside it repeats it.
    expect(screen.getAllByText('数据结构')).toHaveLength(1);
    expect(screen.queryByRole('heading', { name: '数据结构' })).not.toBeInTheDocument();
  });

  it('keeps the identity visible when the learner has only one course', async () => {
    renderApp('/course/cs101/ask');
    await screen.findByRole('navigation', { name: '专业学习导航' });

    // Nothing to switch TO, and the course is still named — the same control either way.
    expect(screen.getAllByRole('option')).toHaveLength(1);
    expect(screen.getByRole('combobox', { name: '切换课程' })).toHaveValue('cs101');
  });

  it('still names a course the list does not hold', async () => {
    hooks.useCourseCatalog.mockReturnValue(
      settled({ courses: [{ course_id: 'os', course_name: '操作系统' }] }),
    );
    renderApp('/course/cs101/ask');
    await screen.findByRole('navigation', { name: '专业学习导航' });

    const switcher = await screen.findByRole('combobox', { name: '切换课程' });
    // The open course keeps its identity — from the dashboard, since the list cannot name it —
    // and the other course is what the selector can move to.
    expect(await within(switcher).findByRole('option', { name: '数据结构' })).toBeInTheDocument();
    expect(within(switcher).getByRole('option', { name: '操作系统' })).toBeInTheDocument();
    expect(switcher).toHaveValue('');
  });

  it('renders the full scoped chat workspace inside the active course Q&A tab', async () => {
    renderApp('/course/cs101/ask');

    const nav = await screen.findByRole('navigation', { name: '专业学习导航' });
    expect(within(nav).getByRole('link', { name: '课程问答' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('complementary', { name: '历史对话' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '新建对话' })).toBeInTheDocument();
    expect(screen.getByText('数据结构课程会话')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: '你的问题' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '选择回答使用的模型' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '深度思考' })).toBeInTheDocument();
    // The course scope is the ONE scope this workspace is built with, and the model list is the
    // course capability's own.
    expect(aiHooks.useModelOptions).toHaveBeenCalledWith('material.qa');
    expect(aiHooks.useScopedAiSessions).toHaveBeenCalledWith({
      kind: 'course',
      courseId: 'cs101',
      label: 'cs101',
    });
    expect(screen.queryByText(/考研.*会话|其他课程会话/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '深度思考' }));
    expect(aiHooks.useModelOptions).toHaveBeenLastCalledWith('tutor.strong_reasoning');
  });
});
