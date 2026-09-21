import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { POST: post, GET: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

beforeEach(() => {
  post.mockReset();
  post.mockImplementation(async (url: string) => {
    if (url === '/logout') return { data: {}, error: undefined, response: { ok: true, status: 200 } };
    return { data: { user: null }, error: undefined, response: { ok: false, status: 401 } };
  });
});

describe('app shell navigation', () => {
  it('presents one product with three learning spaces and the shared capabilities', async () => {
    renderApp('/review');
    const nav = await screen.findByRole('navigation', { name: '主导航' });

    for (const label of ['首页', '考研学习', '课程学习', '编程学习', '复习', '学习报告', '会员']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
  });

  it('marks only the current destination as the active page', async () => {
    renderApp('/exam/cs408/practice');
    const nav = await screen.findByRole('navigation', { name: '主导航' });

    expect(within(nav).getByRole('link', { name: '考研学习' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(nav).getByRole('link', { name: '课程学习' })).not.toHaveAttribute('aria-current');
    // Home is exact-match, so it must not claim to be current on a nested route.
    expect(within(nav).getByRole('link', { name: '首页' })).not.toHaveAttribute('aria-current');
  });

  it('opens a real navigation panel on the small-screen control and closes it on Escape', async () => {
    renderApp('/review');
    await screen.findByRole('navigation', { name: '主导航' });

    expect(screen.queryByRole('navigation', { name: '主导航（移动）' })).not.toBeInTheDocument();
    const toggle = screen.getByRole('button', { name: '打开导航菜单' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(toggle);
    expect(screen.getByRole('button', { name: '关闭导航菜单' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
    const mobileNav = screen.getByRole('navigation', { name: '主导航（移动）' });
    expect(within(mobileNav).getByRole('link', { name: '编程学习' })).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('navigation', { name: '主导航（移动）' })).not.toBeInTheDocument();
  });

  it('offers no control that has nothing behind it', async () => {
    renderApp('/review');
    await screen.findByRole('navigation', { name: '主导航' });

    // The previous shell rendered a search button with no search behind it.
    expect(screen.queryByRole('button', { name: '搜索学习内容' })).not.toBeInTheDocument();
  });

  it('names the signed-in learner in the account menu instead of a placeholder letter', async () => {
    renderApp('/review');
    await screen.findByRole('navigation', { name: '主导航' });

    const trigger = screen.getByRole('button', { name: /测试学习者/ });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(trigger);
    const panel = document.getElementById(trigger.getAttribute('aria-controls') ?? '');
    expect(panel).not.toBeNull();
    expect(within(panel as HTMLElement).getByText(/账号：test_learner/)).toBeInTheDocument();
    expect(within(panel as HTMLElement).getByRole('link', { name: '学习档案' })).toBeInTheDocument();
  });

  it('logs out through the real endpoint and clears the session on the way out', async () => {
    const { router, queryClient } = renderApp('/review');
    await screen.findByRole('navigation', { name: '主导航' });

    await userEvent.click(screen.getByRole('button', { name: /测试学习者/ }));
    await userEvent.click(screen.getByRole('button', { name: '退出登录' }));

    await waitFor(() => expect(post).toHaveBeenCalledWith('/logout', {}));
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(queryClient.getQueryData(['auth', 'session'])).toBeNull();
  });
});

/**
 * Focus, on the one surface a phone depends on to navigate at all.
 *
 * The panel is a disclosure, so it has no focus trap — but "no trap" is not "no focus handling".
 * A keyboard user has to arrive somewhere useful when it opens, and come back to the control
 * that opened it when it closes, or the next Tab starts from the top of the document.
 */
describe('navigation panel focus', () => {
  const openPanel = async () => {
    renderApp('/review');
    await screen.findByRole('navigation', { name: '主导航' });
    const toggle = screen.getByRole('button', { name: '打开导航菜单' });
    await userEvent.click(toggle);
    return { toggle, panel: screen.getByRole('navigation', { name: '主导航（移动）' }) };
  };

  it('moves focus into the navigation when it opens', async () => {
    const { panel } = await openPanel();
    expect(within(panel).getByRole('link', { name: '首页' })).toHaveFocus();
  });

  it('returns focus to the control that opened it, on Escape', async () => {
    const { toggle } = await openPanel();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('navigation', { name: '主导航（移动）' })).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it('returns focus to the control that opened it, on the close button', async () => {
    const { toggle } = await openPanel();
    await userEvent.click(screen.getByRole('button', { name: '关闭导航菜单' }));
    expect(screen.queryByRole('navigation', { name: '主导航（移动）' })).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it('returns focus to the control that opened it, on a click outside', async () => {
    const { toggle } = await openPanel();
    await userEvent.click(screen.getByRole('heading', { name: /待复习|复习/ }));
    expect(screen.queryByRole('navigation', { name: '主导航（移动）' })).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it('returns focus to the control that opened it, after following a destination', async () => {
    const { toggle } = await openPanel();
    await userEvent.click(within(screen.getByRole('navigation', { name: '主导航（移动）' })).getByRole('link', { name: '编程学习' }));

    // Following a link removes the panel and the link inside it, so without an explicit return
    // the browser would drop focus onto the document body.
    expect(screen.queryByRole('navigation', { name: '主导航（移动）' })).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
  });

  it('does not pull focus on a first render', async () => {
    renderApp('/review');
    await screen.findByRole('navigation', { name: '主导航' });
    expect(screen.getByRole('button', { name: '打开导航菜单' })).not.toHaveFocus();
  });
});
