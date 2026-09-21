import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { get, put, post } = vi.hoisted(() => ({ get: vi.fn(), put: vi.fn(), post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: get, PUT: put, POST: post },
  resolveApiResourceUrl: (value: string) => value,
}));

const ok = (data: unknown) => ({ data, error: undefined, response: { ok: true, status: 200 } });

const PROFILE = {
  id: 1,
  username: 'test_learner',
  nickname: '测试学习者',
  grade: '大三',
  major: '计算机科学与技术',
  semester: '上学期',
  learning_direction: '计算机考研 408',
  focus_courses: '数据结构、操作系统',
  email: 'learner@example.com',
  email_verified: true,
  phone: '',
  phone_verified: false,
  onboarding_completed: true,
  needs_onboarding: false,
  // Present in the response but read by nothing in the product — the page must not offer them.
  ai_answer_style: 'concise',
  answer_detail_level: 'brief',
  material_reference_preference: 'none',
  learning_stage: 'basic',
  school: '示例大学',
  daily_study_minutes: 90,
};

beforeEach(() => {
  get.mockReset();
  put.mockReset();
  post.mockReset();
  get.mockImplementation(async (url: string) => {
    if (url === '/me/profile') return ok({ profile: PROFILE });
    // The learning-settings section reads each space's own current state rather than keeping a
    // copy, so these three are what the page actually shows for it.
    if (url === '/course-learning/courses') {
      return ok({ courses: [{ course_id: 'data_structure', course_name: '数据结构' }], total: 1 });
    }
    if (url === '/exam/prep/profile') {
      return ok({ configured: true, subjects: [{ id: 'cs_408', display_name: '计算机学科专业基础' }], selected_subjects: ['cs_408'], selected_track: 'cs_408', target_exam_year: 2027 });
    }
    if (url === '/programming/onboarding') {
      return ok({ selected_languages: ['Python'], main_language: 'Python', level: 'basic', onboarding_completed: true, plan: 'free' });
    }
    if (url === '/subscription') return ok({ tier: 'standard', policy_version: 'v1' });
    if (url === '/subscription/plans') {
      return ok({
        policy_version: 'v1',
        plans: {
          standard: { label: '标准版', daily_budget: 30, weekly_budget: 150, capabilities: [] },
          advanced: { label: '高级版', daily_budget: null, weekly_budget: 900, capabilities: [] },
        },
      });
    }
    if (url === '/usage/summary') {
      return ok({
        tier: 'standard',
        periods: {
          daily: { budget: 30, reserved: 0, settled: 12, remaining: 18 },
          weekly: { budget: 150, reserved: 2, settled: 40, remaining: 108 },
        },
      });
    }
    throw new Error(`unexpected GET ${url}`);
  });
  put.mockImplementation(async () => ok({ profile: PROFILE }));
  post.mockImplementation(async () => ok({}));
});

describe('profile page', () => {
  it('shows the learner’s own stored profile values', async () => {
    renderApp('/profile');

    expect(await screen.findByDisplayValue('测试学习者')).toBeInTheDocument();
    expect(screen.getByLabelText('专业')).toHaveValue('计算机科学与技术');
    expect(screen.getByLabelText('年级')).toHaveValue('大三');
    expect(screen.getByText('账号：test_learner')).toBeInTheDocument();
  });

  it('offers only learning settings the backend actually reads', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    expect(screen.getByLabelText('学习方向')).toHaveValue('计算机考研 408');

    // These fields exist in `PUT /me/profile` but are read by nothing in the backend, so the
    // product must not present them as settings that do something.
    for (const dead of ['AI 回答风格', '回答详细程度', '资料引用偏好', '学习阶段', '学校', '每日学习时长']) {
      expect(screen.queryByLabelText(dead)).not.toBeInTheDocument();
    }

    // `关注课程` was one of them in the other direction: it *is* read, as a fallback source of
    // the course list, which made it a second write path for the same fact. The course list is
    // edited in the course setup flow, and the section links there instead.
    expect(screen.queryByLabelText('关注课程')).not.toBeInTheDocument();
  });

  it('reports each learning space from that space’s own state, not from a copy', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const section = screen.getByRole('region', { name: '学习设置' });
    expect(await within(section).findByText(/已声明 1 门课程：数据结构/)).toBeInTheDocument();
    expect(within(section).getByText(/已确认 1 个科目 · 目标 2027 年/)).toBeInTheDocument();
    expect(within(section).getByText('练习语言：Python')).toBeInTheDocument();

    // Every row leads into the setup flow that owns that space, and asks to come back here.
    expect(within(section).getByRole('link', { name: '管理课程' })).toHaveAttribute(
      'href',
      '/course/setup?returnTo=%2Fprofile',
    );
    expect(within(section).getByRole('link', { name: '编辑备考设置' })).toHaveAttribute(
      'href',
      '/exam/setup?returnTo=%2Fprofile',
    );
    expect(within(section).getByRole('link', { name: '编辑编程设置' })).toHaveAttribute(
      'href',
      '/programming/setup?returnTo=%2Fprofile',
    );
  });

  it('saves an edit through the real endpoint', async () => {
    renderApp('/profile');
    const nickname = await screen.findByLabelText('昵称');

    await userEvent.clear(nickname);
    await userEvent.type(nickname, '新昵称');
    await userEvent.click(
      within(screen.getByRole('region', { name: '个人信息' })).getByRole('button', { name: '保存' }),
    );

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith('/me/profile', {
        body: {
          nickname: '新昵称',
          grade: '大三',
          major: '计算机科学与技术',
          semester: '上学期',
        },
      }),
    );
  });

  it('reports the real tier and the ledger’s own numbers', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const membership = screen.getByRole('region', { name: '会员' });
    expect(await within(membership).findByText('标准版')).toBeInTheDocument();

    const usage = await screen.findByRole('region', { name: '用量' });
    expect(await within(usage).findByText('18')).toBeInTheDocument();
    expect(within(usage).getByText('108')).toBeInTheDocument();
  });

  it('prints an uncapped tier as uncapped rather than as a zero', async () => {
    get.mockImplementation(async (url: string) => {
      if (url === '/me/profile') return ok({ profile: PROFILE });
      if (url === '/subscription') return ok({ tier: 'advanced', policy_version: 'v1' });
      if (url === '/subscription/plans') {
        return ok({
          policy_version: 'v1',
          plans: {
            advanced: { label: '高级版', daily_budget: null, weekly_budget: 900, capabilities: [] },
          },
        });
      }
      return ok({
        tier: 'advanced',
        periods: {
          daily: { budget: null, reserved: null, settled: null, remaining: null },
          weekly: { budget: 900, reserved: 0, settled: 10, remaining: 890 },
        },
      });
    });

    renderApp('/profile');
    const membership = await screen.findByRole('region', { name: '会员' });
    expect(await within(membership).findByText('无上限')).toBeInTheDocument();

    const usage = await screen.findByRole('region', { name: '用量' });
    // An uncapped period reports `null` for all four figures, and each prints as uncapped.
    expect(await within(usage).findAllByText('无上限')).toHaveLength(4);
  });

  it('states the email binding rule instead of offering a change that the backend refuses', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    expect(screen.getByText('已绑定邮箱：learner@example.com')).toBeInTheDocument();
    expect(screen.getByText('当前版本不支持更换已绑定的邮箱。')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '发送验证码' })).toBeInTheDocument(); // phone only
    expect(screen.getByRole('button', { name: '绑定手机号' })).toBeInTheDocument();
  });

  it('says plainly that no legal documents are published rather than linking to a fake page', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const legal = screen.getByRole('region', { name: '法务' });
    expect(within(legal).getByText(/尚未发布用户协议与隐私政策/)).toBeInTheDocument();
    expect(within(legal).queryByRole('link')).not.toBeInTheDocument();
  });

  it('logs out from the profile page through the real endpoint', async () => {
    const { router, queryClient } = renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    await userEvent.click(screen.getByRole('button', { name: '退出登录' }));

    await waitFor(() => expect(post).toHaveBeenCalledWith('/logout', {}));
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(queryClient.getQueryData(['auth', 'session'])).toBeNull();
  });
});
