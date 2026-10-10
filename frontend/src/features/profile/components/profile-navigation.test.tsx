import { screen, within } from '@testing-library/react';
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
};

beforeEach(() => {
  vi.unstubAllGlobals();
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
  it('does not replace a deep-linked section while the profile is still loading', async () => {
    let resolveProfile: ((value: ReturnType<typeof ok>) => void) | undefined;
    get.mockImplementation((url: string) => {
      if (url === '/me/profile') {
        return new Promise((resolve) => {
          resolveProfile = resolve;
        });
      }
      throw new Error(`unexpected GET ${url}`);
    });
    const callbacks: ((entries: IntersectionObserverEntry[]) => void)[] = [];
    const Observer = vi.fn(class {
      constructor(callback: IntersectionObserverCallback) {
        callbacks.push((entries) => callback(entries, {} as IntersectionObserver));
      }
      observe = vi.fn();
      disconnect = vi.fn();
    });
    vi.stubGlobal('IntersectionObserver', Observer);

    const { router } = renderApp('/profile?section=profile-security');
    await screen.findByRole('link', { name: '智学平台首页' });

    expect(Observer).not.toHaveBeenCalled();
    expect(router.state.location.search).toEqual({ section: 'profile-security' });

    resolveProfile?.(ok({ profile: PROFILE }));
    await screen.findByDisplayValue('测试学习者');

    expect(Observer).toHaveBeenCalledTimes(1);
    expect(router.state.location.search).toEqual({ section: 'profile-security' });

    const entry = (id: string, top: number) => ({
      isIntersecting: true,
      target: document.getElementById(id) as Element,
      boundingClientRect: { top } as DOMRectReadOnly,
    }) as IntersectionObserverEntry;
    const sectionTops = new Map<string, number>([
      ['profile-personal', 0],
      ['profile-learning', 500],
      ['profile-security', 1200],
    ]);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
      const top = sectionTops.get(this.id);
      return { top: top ?? 0 } as DOMRect;
    });
    const observerCallback = callbacks[0];
    expect(observerCallback).toBeDefined();
    observerCallback?.([entry('profile-personal', 0)]);
    expect(router.state.location.search).toEqual({ section: 'profile-security' });

    sectionTops.set('profile-personal', -1000);
    sectionTops.set('profile-learning', -500);
    sectionTops.set('profile-security', 96);
    observerCallback?.([entry('profile-security', 96)]);

    sectionTops.set('profile-learning', 96);
    sectionTops.set('profile-security', 600);
    observerCallback?.([entry('profile-learning', 96)]);
    expect(router.state.location.search).toEqual({ section: 'profile-learning' });
  });

  it('links the four remaining entries to their real section or existing page', async () => {
    const { router } = renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const nav = screen.getByRole('navigation', { name: '学习档案分区' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((link) => link.textContent)).toEqual([
      '个人资料',
      '学习设置',
      '账号安全',
      '法务',
    ]);

    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/profile?section=profile-personal',
      '/profile?section=profile-learning',
      '/profile?section=profile-security',
      '/terms',
    ]);
    for (const id of ['profile-personal', 'profile-learning', 'profile-security']) {
      expect(document.getElementById(id)).not.toBeNull();
    }

    await userEvent.click(within(nav).getByRole('link', { name: '学习设置' }));
    expect(router.state.location.search).toEqual({ section: 'profile-learning' });
    expect(within(nav).getByRole('link', { name: '学习设置' })).toHaveAttribute('aria-current', 'location');
    await userEvent.click(within(nav).getByRole('link', { name: '账号安全' }));
    expect(router.state.location.search).toEqual({ section: 'profile-security' });
    expect(within(nav).getByRole('link', { name: '账号安全' })).toHaveAttribute('aria-current', 'location');

    await userEvent.click(within(nav).getByRole('link', { name: '法务' }));
    expect(router.state.location.pathname).toBe('/terms');
    expect(await screen.findByRole('heading', { name: /用户协议/ })).toBeInTheDocument();
  });

  it('uses one page title and omits redundant navigation group headings', async () => {
    renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    expect(screen.getByRole('heading', { level: 1, name: '个人中心' })).toBeInTheDocument();
    for (const group of ['身份与学习设置', '学习记录']) {
      expect(screen.queryByRole('heading', { name: group })).not.toBeInTheDocument();
    }
    for (const section of ['个人资料', '学习设置', '账号安全']) {
      expect(screen.getByRole('heading', { name: section })).toBeInTheDocument();
    }
    expect(screen.queryByRole('heading', { name: '会员与额度' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '学习数据' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '法务' })).not.toBeInTheDocument();
  });

  it('navigates the mobile selector to the same real destinations', async () => {
    const { router } = renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');

    const selector = screen.getByLabelText('跳转到');
    const options = within(selector).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      '个人资料',
      '学习设置',
      '账号安全',
      '法务',
    ]);
    await userEvent.selectOptions(selector, 'terms');
    expect(router.state.location.pathname).toBe('/terms');
    expect(await screen.findByRole('heading', { name: /用户协议/ })).toBeInTheDocument();
  });

  it('opens the existing legal page from the desktop navigation', async () => {
    const { router } = renderApp('/profile');
    await screen.findByDisplayValue('测试学习者');
    const nav = screen.getByRole('navigation', { name: '学习档案分区' });

    await userEvent.click(within(nav).getByRole('link', { name: '法务' }));
    expect(router.state.location.pathname).toBe('/terms');
    expect(await screen.findByRole('heading', { name: /用户协议/ })).toBeInTheDocument();
  });

  it('restores section selection on direct URL and browser history navigation', async () => {
    const { router } = renderApp('/profile?section=profile-learning');
    await screen.findByDisplayValue('测试学习者');
    const nav = screen.getByRole('navigation', { name: '学习档案分区' });
    expect(within(nav).getByRole('link', { name: '学习设置' })).toHaveAttribute('aria-current', 'location');

    await router.navigate({ to: '/profile', search: { section: 'profile-security' } });
    expect(within(nav).getByRole('link', { name: '账号安全' })).toHaveAttribute('aria-current', 'location');
    await router.history.back();
    await screen.findByDisplayValue('计算机考研 408');
    expect(within(nav).getByRole('link', { name: '学习设置' })).toHaveAttribute('aria-current', 'location');
  });

  it('scrolls to 学习设置 even when its section is already selected in the URL', async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', { configurable: true, value: scrollIntoView });
    const { router } = renderApp('/profile?section=profile-learning');
    await screen.findByDisplayValue('测试学习者');
    scrollIntoView.mockClear();

    const nav = screen.getByRole('navigation', { name: '学习档案分区' });
    await userEvent.click(within(nav).getByRole('link', { name: '学习设置' }));

    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'start', behavior: 'auto' });
    expect(router.state.location.search).toEqual({ section: 'profile-learning' });
    expect(document.getElementById('profile-learning')).toHaveClass('scroll-mt-24');
  });
});
