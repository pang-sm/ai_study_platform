import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, POST: post, PUT: put },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });
const fail = (status: number, detail: unknown) => ({
  data: undefined,
  error: { detail },
  response: { ok: false, status },
});

/** The declared context the setup flow wrote last time, and the courses the space holds now. */
let declared = {
  major: '',
  grade: '',
  semester: '',
  selected_courses: [] as string[],
  material_types: [] as string[],
  course_goals: {} as Record<string, string>,
};
let held: unknown[] = [];

beforeEach(() => {
  declared = { major: '', grade: '', semester: '', selected_courses: [], material_types: [], course_goals: {} };
  held = [];
  get.mockReset();
  post.mockReset();
  put.mockReset();
  get.mockImplementation(async (url: string) => {
    if (url === '/me') return ok({ user: { id: 1, username: 'test_learner', nickname: '测试学习者' } });
    if (url === '/course-learning/onboarding') return ok(declared);
    if (url === '/course-learning/courses') return ok({ courses: held, total: held.length });
    if (url === '/course-dashboard') return ok({ course_name: '数据结构', items: [], tasks: [] });
    if (url === '/learning/agenda' || url === '/learning/agenda/explain') return ok({ items: [], total_items: 0 });
    if (url === '/learning-records') return ok({ records: [], has_more: false, next_cursor: null });
    if (url === '/review/summary') return ok({ total: 0, has_stored_due_dates: false });
    throw new Error(`unexpected GET ${url}`);
  });
  post.mockImplementation(async (url: string) => {
    if (url !== '/course-learning/onboarding') throw new Error(`unexpected POST ${url}`);
    return ok({ message: 'course learning onboarding saved', onboarding: declared });
  });
});

describe('course setup', () => {
  it('opens on the courses the space already holds when nothing has been declared yet', async () => {
    // The declared list and the courses the space reads are two views of one fact; the course
    // space also honours an account-level course list that predates the setup flow. Opening on
    // the narrower of the two would show a learner who has courses an empty screen.
    held = [{ course_id: 'data_structure', course_name: '数据结构' }];
    renderApp('/course/setup');

    // It is in the editor's own list, not only in the read-only section below it. The page waits
    // for two reads before it can draw the editor, so this one is given room to settle.
    expect(
      await screen.findByRole('button', { name: '移除课程 数据结构' }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/下面的课程来自课程学习空间当前已有的课程/),
    ).toBeInTheDocument();
  });

  it('saves the declared courses through the real endpoint', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', semester: '上学期' };
    renderApp('/course/setup');
    await screen.findByLabelText('添加课程');

    await userEvent.type(screen.getByLabelText('添加课程'), '数据结构');
    await userEvent.click(screen.getByRole('button', { name: '添加到课程' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/course-learning/onboarding', {
        body: {
          major: '计算机科学与技术',
          grade: '大三',
          semester: '上学期',
          selected_courses: ['数据结构'],
          material_types: [],
          course_goals: { 数据结构: '平日学习' },
          onboarding_completed: true,
        },
      }),
    );
  });

  it('carries the per-course learning mode with the course it belongs to', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三' };
    renderApp('/course/setup');
    await screen.findByLabelText('添加课程');

    await userEvent.type(screen.getByLabelText('添加课程'), '数据结构');
    await userEvent.click(screen.getByRole('button', { name: '添加到课程' }));
    await userEvent.selectOptions(screen.getByLabelText('学习方式'), '考前突击');
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/course-learning/onboarding',
        expect.objectContaining({ body: expect.objectContaining({ course_goals: { 数据结构: '考前突击' } }) }),
      ),
    );
  });

  it('applies the endpoint’s own requirements before spending a request', async () => {
    renderApp('/course/setup');
    await screen.findByLabelText('添加课程');

    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));
    expect(await screen.findByText('请选择至少一门想学习的课程')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('添加课程'), '数据结构');
    await userEvent.click(screen.getByRole('button', { name: '添加到课程' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));
    expect(await screen.findByText('请选择专业')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('专业'), '计算机科学与技术');
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));
    expect(await screen.findByText('请选择年级')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it('surfaces the server’s refusal rather than reporting success', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三' };
    post.mockImplementation(async () => fail(400, { detail: '课程学习套餐不支持降级，请保持当前套餐或升级' }));
    renderApp('/course/setup');
    await screen.findByLabelText('添加课程');

    await userEvent.type(screen.getByLabelText('添加课程'), '数据结构');
    await userEvent.click(screen.getByRole('button', { name: '添加到课程' }));
    await userEvent.click(screen.getByRole('button', { name: '保存并开始' }));

    expect(await screen.findByText('课程学习套餐不支持降级，请保持当前套餐或升级')).toBeInTheDocument();
  });

  it('removes a course from the set it will save', async () => {
    declared = {
      major: '计算机科学与技术',
      grade: '大三',
      semester: '',
      selected_courses: ['数据结构', '操作系统'],
      material_types: [],
      course_goals: {},
    };
    renderApp('/course/setup');
    await screen.findByText('操作系统');

    await userEvent.click(screen.getByRole('button', { name: '移除课程 数据结构' }));
    await userEvent.click(screen.getByRole('button', { name: '保存课程设置' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/course-learning/onboarding',
        expect.objectContaining({ body: expect.objectContaining({ selected_courses: ['操作系统'] }) }),
      ),
    );
  });

  it('returns to the requested destination, which is the space it came from', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    const { router } = renderApp('/course/setup?returnTo=%2Fprofile');
    await screen.findByRole('button', { name: '保存课程设置' });

    await userEvent.click(screen.getByRole('button', { name: '保存课程设置' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'));
  });

  it('refuses to leave this origin when the destination says to', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    // The route's own validator drops a protocol-relative target before the page ever sees it.
    const { router } = renderApp('/course/setup?returnTo=%2F%2Fevil.example');
    await screen.findByRole('button', { name: '保存课程设置' });

    await userEvent.click(screen.getByRole('button', { name: '保存课程设置' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/course'));
  });

  it('shows what the space holds once it has been saved, and links into it', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    held = [
      {
        course_id: 'data_structure',
        course_name: '数据结构',
        primary_mode: 'exam',
        primary_mode_label: '考前突击',
        material_count: 3,
        pending_task_count: 1,
      },
    ];
    renderApp('/course/setup');

    const section = await screen.findByRole('region', { name: '课程空间中已建立的课程' });
    expect(within(section).getByRole('link', { name: '数据结构' })).toHaveAttribute(
      'href',
      '/course/data_structure',
    );
    expect(within(section).getByText('考前突击 · 资料 3 · 待办任务 1')).toBeInTheDocument();
  });
});

describe('course switcher', () => {
  it('moves to another course on the same section', async () => {
    held = [
      { course_id: 'data_structure', course_name: '数据结构' },
      { course_id: 'operating_system', course_name: '操作系统' },
    ];
    const { router } = renderApp('/course/data_structure/practice');

    const switcher = await screen.findByLabelText('切换课程');
    await waitFor(() => expect(within(switcher).getAllByRole('option')).toHaveLength(2));
    await userEvent.selectOptions(switcher, 'operating_system');

    await waitFor(() => expect(router.state.location.pathname).toBe('/course/operating_system/practice'));
  });

  it('is not offered when the learner has only the one course open', async () => {
    held = [{ course_id: 'data_structure', course_name: '数据结构' }];
    renderApp('/course/data_structure/practice');

    await screen.findByLabelText('切换课程').catch(() => undefined);
    expect(screen.queryByLabelText('切换课程')).not.toBeInTheDocument();
    // The way to change the set is still there.
    expect(await screen.findByRole('link', { name: '管理课程' })).toHaveAttribute(
      'href',
      '/course/setup?returnTo=%2Fcourse%2Fdata_structure%2Fpractice',
    );
  });
});
