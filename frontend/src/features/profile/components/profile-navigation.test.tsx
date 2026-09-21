import { screen, within } from '@testing-library/react';
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
};

beforeEach(() => {
  get.mockReset();
  get.mockImplementation(async (url: string) => {
    if (url === '/me/profile') return ok({ profile: PROFILE });
    if (url === '/subscription') return ok({ tier: 'standard', policy_version: 'v1' });
    if (url === '/subscription/plans') {
      return ok({ policy_version: 'v1', plans: { standard: { label: '标准版', daily_budget: 30, weekly_budget: 150, capabilities: [] } } });
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

describe('profile section navigation', () => {
  it('lists every section in the side navigation and points each entry at a section that exists', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const nav = screen.getByRole('navigation', { name: '学习档案分区' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual([
      '个人信息',
      '学习设置',
      '会员',
      '用量',
      '学习数据',
      '账号与安全',
      '法务',
    ]);

    // A listed section and a rendered section cannot drift: every href must resolve.
    for (const link of links) {
      const id = (link.getAttribute('href') ?? '').replace('#', '');
      expect(id).not.toBe('');
      expect(document.getElementById(id)).not.toBeNull();
    }
  });

  it('groups the sections instead of presenting one undifferentiated column', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    // Each group is a heading of its own, and none of them repeats a section's name — otherwise
    // the outline would say the same thing twice at two different levels.
    for (const group of ['身份与学习设置', '会员与额度', '学习记录', '账号']) {
      expect(screen.getByRole('heading', { name: group })).toBeInTheDocument();
    }
    for (const section of ['个人信息', '学习设置', '会员', '用量', '学习数据', '账号与安全', '法务']) {
      expect(screen.getByRole('heading', { name: section })).toBeInTheDocument();
    }
  });

  it('reaches the same sections from a selector on small screens', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const selector = screen.getByLabelText('跳转到分区');
    const options = within(selector).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      '选择要查看的分区…',
      '个人信息',
      '学习设置',
      '会员',
      '用量',
      '学习数据',
      '账号与安全',
      '法务',
    ]);
    // The selector is a control, not a second source of section names: each option addresses a
    // section that is actually in the document.
    for (const option of options.slice(1)) {
      expect(document.getElementById(option.getAttribute('value') ?? '')).not.toBeNull();
    }
  });
});
