import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const course = vi.hoisted(() => ({ useCourseCatalog: vi.fn(), useCourseOnboarding: vi.fn() }));
const records = vi.hoisted(() => ({ useRecentRecords: vi.fn() }));

vi.mock('@/features/course/api/course', () => ({ ...course }));
vi.mock('@/features/records/api/learning-records', () => ({ ...records }));

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data });

beforeEach(() => {
  course.useCourseCatalog.mockReturnValue(
    settled({
      courses: [
        { course_id: '数据结构', course_name: '数据结构' },
        { course_id: '高等数学', course_name: '高等数学' },
      ],
    }),
  );
  course.useCourseOnboarding.mockReturnValue(
    settled({
      major: '计算机科学与技术',
      grade: '大二',
      selected_courses: ['数据结构', '高等数学'],
      recommended_courses: ['数据结构'],
    }),
  );
  records.useRecentRecords.mockReturnValue(settled([]));
});

/** The four labels that used to be separate settings entries on this page. */
const RETIRED_ENTRIES = ['调整专业与年级', '调整课程', '管理课程', '查看完整学习框架'];

describe('CourseIndex', () => {
  it('offers one settings entry, and no entry per setting', async () => {
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    const entries = screen.getAllByRole('link', { name: '学习设置' });
    expect(entries).toHaveLength(1);
    expect(entries[0]).toHaveAttribute('href', '/course/setup?returnTo=%2Fcourse');

    for (const label of RETIRED_ENTRIES) {
      expect(screen.queryByRole('link', { name: label })).not.toBeInTheDocument();
    }
  });

  it('states the declared major and grade, and nothing else about them', async () => {
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    expect(screen.getByText('计算机科学与技术 · 大二')).toBeInTheDocument();
    expect(screen.queryByText('当前专业')).not.toBeInTheDocument();
    expect(screen.queryByText('当前年级')).not.toBeInTheDocument();
  });

  it('lists every course as a way into its own workspace', async () => {
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    const mine = screen.getByRole('region', { name: '我的课程' });
    for (const name of ['数据结构', '高等数学']) {
      const href = within(mine).getByRole('link', { name }).getAttribute('href') ?? '';
      expect(decodeURIComponent(href)).toBe(`/course/${name}`);
    }
  });

  it('does not repeat the courses as a second, recommended list', async () => {
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    expect(screen.queryByRole('region', { name: '推荐课程' })).not.toBeInTheDocument();
    // 数据结构 is recommended AND declared; it is listed once, in 我的课程.
    expect(screen.getAllByRole('link', { name: '数据结构' })).toHaveLength(1);
  });

  it('claims no progress the server has not reported', async () => {
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    // With no record, the rows are bare names: no 继续学习 / 进入课程 and no counters.
    const mine = screen.getByRole('region', { name: '我的课程' });
    expect(within(mine).queryByText('继续学习')).not.toBeInTheDocument();
    expect(within(mine).queryByText('进入课程')).not.toBeInTheDocument();
    expect(within(mine).queryByText(/资料|待办/)).not.toBeInTheDocument();
    expect(screen.queryByText('智学AI推荐')).not.toBeInTheDocument();
  });

  it('names the course the learner was last active in', async () => {
    records.useRecentRecords.mockReturnValue(settled([{ id: 1, context: { course_id: '高等数学' } }]));
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    const mine = screen.getByRole('region', { name: '我的课程' });
    expect(within(mine).getByRole('link', { name: /高等数学.*继续学习/ })).toBeInTheDocument();
    expect(within(mine).getByRole('link', { name: /数据结构.*进入课程/ })).toBeInTheDocument();
  });

  it('keeps course Q&A inside the course workspace', async () => {
    renderApp('/course');
    await screen.findByRole('heading', { level: 1, name: '专业学习' });

    expect(screen.queryByRole('region', { name: '问 AI' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '问 AI' })).not.toBeInTheDocument();
  });
});
