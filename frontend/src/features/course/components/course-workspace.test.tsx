import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const hooks = vi.hoisted(() => ({
  useCourseCatalog: vi.fn(),
  useCourseDashboard: vi.fn(),
  useCourseMaterials: vi.fn(),
  useCourseKnowledge: vi.fn(),
  useCoursePracticeHistory: vi.fn(),
  useCourseTodayPlan: vi.fn(),
}));

vi.mock('@/features/course/api/course', () => ({
  ...hooks,
  toCourseIdentity: (value: unknown) => value,
}));

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });

function loaded() {
  // One course, so the switcher has somewhere to go; a second is added in its own case below.
  hooks.useCourseCatalog.mockReturnValue(settled({ courses: [{ course_id: 'cs101', course_name: '数据结构' }] }));
  hooks.useCourseDashboard.mockReturnValue(settled({ course_name: '数据结构' }));
  hooks.useCourseMaterials.mockReturnValue(settled({ items: [{}] }));
  hooks.useCourseKnowledge.mockReturnValue(settled([]));
  hooks.useCoursePracticeHistory.mockReturnValue(settled([]));
  hooks.useCourseTodayPlan.mockReturnValue(settled({ items: [{ id: 1 }] }));
}

beforeEach(() => {
  loaded();
});

function chain() {
  return screen.getByRole('heading', { name: '这门课程是怎么学的' }).closest('section') as HTMLElement;
}

/** The loop's steps are addressed by where they lead, not by a name that repeats elsewhere. */
function chainStep(href: string) {
  const step = within(chain())
    .getAllByRole('link')
    .find((link) => link.getAttribute('href') === href);
  if (!step) throw new Error(`no chain step for ${href}`);
  return step;
}

describe('CourseWorkspace', () => {
  it('names the current course and shows the loop that course is learned through', async () => {
    renderApp('/course/cs101');

    // The course is named by the context strip and the breadcrumb; the title names the page.
    expect(await screen.findByRole('heading', { level: 1, name: '课程概览' })).toBeInTheDocument();
    expect(screen.getByText('当前课程').closest('div')?.textContent).toContain('数据结构');
    expect(within(screen.getByRole('navigation', { name: '面包屑' })).getByText('课程学习')).toBeInTheDocument();

    // Every step of the loop is a real destination, in the order the loop happens in.
    expect(within(chain()).getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
      '/course/cs101/materials',
      '/course/cs101/knowledge',
      '/course/cs101/practice',
      '/course/cs101/wrong',
      '/course/cs101/plan',
      '/course/cs101/records',
    ]);
    // Each step states the count the server returned.
    expect(within(chain()).getByText('1 项今日任务')).toBeInTheDocument();
    expect(within(chain()).getByText('0 条练习记录')).toBeInTheDocument();
  });

  it('marks a step whose count is not known yet as reading, never as zero', async () => {
    hooks.useCourseKnowledge.mockReturnValue({ isPending: true, isError: false, data: undefined });
    renderApp('/course/cs101');
    await screen.findByRole('heading', { name: '这门课程是怎么学的' });

    const knowledge = chainStep('/course/cs101/knowledge');
    expect(within(knowledge).getByText('正在读取…')).toBeInTheDocument();
    expect(within(knowledge).queryByText(/0 个知识点/)).not.toBeInTheDocument();
  });

  it('keeps the course tab bar current for the overview', async () => {
    renderApp('/course/cs101');

    const nav = await screen.findByRole('navigation', { name: '课程学习导航' });
    expect(within(nav).getByRole('link', { name: '概览' })).toHaveAttribute('aria-current', 'page');
    expect(within(nav).getByRole('link', { name: '资料' })).toHaveAttribute('href', '/course/cs101/materials');
  });
});
