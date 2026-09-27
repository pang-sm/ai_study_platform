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
    if (url === '/membership/recommendation') return ok({ suggested_courses: ['数据结构', '操作系统'] });
    throw new Error(`unexpected GET ${url}`);
  });
  post.mockImplementation(async (url: string) => {
    if (url !== '/course-learning/onboarding') throw new Error(`unexpected POST ${url}`);
    return ok({ message: 'course learning onboarding saved', onboarding: declared });
  });
  put.mockImplementation(async () => ok({ message: 'profile updated' }));
});

describe('course setup', () => {
  it('opens on the courses the space already holds when nothing has been declared yet', async () => {
    // The declared list and the courses the space reads are two views of one fact; the course
    // space also honours an account-level course list that predates the setup flow. Opening on
    // the narrower of the two would show a learner who has courses an empty screen.
    held = [{ course_id: 'data_structure', course_name: '数据结构' }];
    renderApp('/course/setup');

    // The page waits for two reads before it can draw the editor, so this one is given room to
    // settle.
    expect(
      await screen.findByRole('button', { name: '移除课程 数据结构' }, { timeout: 5000 }),
    ).toBeInTheDocument();
  });

  it('is the one screen for the three settings areas, with no fourth', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    renderApp('/course/setup');

    expect(await screen.findByRole('heading', { level: 1, name: '学习设置' })).toBeInTheDocument();
    for (const title of ['专业与年级', '我的课程', '学习框架']) {
      expect(screen.getByRole('heading', { level: 2, name: title })).toBeInTheDocument();
    }
    // The read-only copy of the space's courses is gone, and with it its counters.
    expect(screen.queryByRole('region', { name: '课程空间中已建立的课程' })).not.toBeInTheDocument();
    expect(screen.queryByText(/资料 \d/)).not.toBeInTheDocument();
    expect(screen.queryByText(/待办/)).not.toBeInTheDocument();
  });

  it('edits major, grade and semester through the same save', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    renderApp('/course/setup');
    await screen.findByLabelText('学期');

    await userEvent.selectOptions(screen.getByLabelText('年级'), '大四');
    await userEvent.selectOptions(screen.getByLabelText('学期'), '下学期');
    await userEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/course-learning/onboarding',
        expect.objectContaining({ body: expect.objectContaining({ grade: '大四', semester: '下学期' }) }),
      ),
    );
  });

  it('bands what the learner holds, and adds the recommendation to the same save', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    renderApp('/course/setup');
    await screen.findByRole('heading', { level: 2, name: '学习框架' });

    // The declared course is in the framework already, banded by name, and its box is the one
    // already ticked — no second label says so.
    const framework = screen.getByRole('region', { name: '学习框架' });
    expect(within(framework).getByRole('checkbox', { name: '数据结构' })).toBeChecked();
    expect(within(framework).getByRole('checkbox', { name: '数据结构' })).toBeDisabled();
    expect(within(framework).getByText('专业核心')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /生成推荐学习框架/ }));
    expect(await within(framework).findByRole('checkbox', { name: '操作系统' })).toBeChecked();
    expect(put).toHaveBeenCalledWith('/me/profile', {
      body: { major: '计算机科学与技术', grade: '大三' },
    });

    await userEvent.click(screen.getByRole('button', { name: '加入我的课程' }));
    await userEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/course-learning/onboarding',
        expect.objectContaining({
          body: expect.objectContaining({
            selected_courses: ['数据结构', '操作系统'],
            recommended_courses: ['操作系统'],
          }),
        }),
      ),
    );
  });

  it('saves the declared courses through the real endpoint', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', semester: '上学期' };
    renderApp('/course/setup');
    await screen.findByLabelText('添加课程');

    await userEvent.type(screen.getByLabelText('添加课程'), '数据结构');
    await userEvent.click(screen.getByRole('button', { name: '添加到课程' }));
    await userEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/course-learning/onboarding', {
        body: {
          major: '计算机科学与技术',
          grade: '大三',
          semester: '上学期',
          selected_courses: ['数据结构'],
          material_types: [],
          course_goals: { 数据结构: '平日学习' },
          // A course typed by hand carries NO recommendation provenance — this is what keeps the
          // landing page from labelling the learner's own choice as something the framework gave them.
          recommended_courses: [],
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
    await userEvent.click(screen.getByRole('button', { name: '保存' }));

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

    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    expect(await screen.findByText('请选择至少一门想学习的课程')).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('添加课程'), '数据结构');
    await userEvent.click(screen.getByRole('button', { name: '添加到课程' }));
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
    expect(await screen.findByText('请选择专业')).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('专业'), '计算机科学与技术');
    await userEvent.click(screen.getByRole('button', { name: '保存' }));
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
    await userEvent.click(screen.getByRole('button', { name: '保存' }));

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
    // Scoped to the editor: the same course is also banded in 学习框架, which is what the framework
    // shows rather than a second editor.
    const mine = await screen.findByRole('region', { name: '我的课程' });
    expect(within(mine).getByText('操作系统')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '移除课程 数据结构' }));
    await userEvent.click(screen.getByRole('button', { name: '保存' }));

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
    await screen.findByRole('button', { name: '保存' });

    await userEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/profile'));
  });

  it('refuses to leave this origin when the destination says to', async () => {
    declared = { ...declared, major: '计算机科学与技术', grade: '大三', selected_courses: ['数据结构'] };
    // The route's own validator drops a protocol-relative target before the page ever sees it.
    const { router } = renderApp('/course/setup?returnTo=%2F%2Fevil.example');
    await screen.findByRole('button', { name: '保存' });

    await userEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/course'));
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

  it('stays as the course identity when there is nothing to switch to', async () => {
    held = [{ course_id: 'data_structure', course_name: '数据结构' }];
    renderApp('/course/data_structure/practice');

    // The selector is how the page names the course, so it is present with a single course too.
    const switcher = await screen.findByLabelText('切换课程');
    await waitFor(() => expect(switcher).toHaveValue('data_structure'));
    expect(within(switcher).getAllByRole('option')).toHaveLength(1);
    // Switching courses is not a way into the settings, so the course space offers none here:
    // changing the set happens in 学习设置, which the home page links to once.
    for (const label of ['管理课程', '调整课程', '学习设置']) {
      expect(screen.queryByRole('link', { name: label })).not.toBeInTheDocument();
    }
  });
});
