import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp } from '@/test/render-app';

vi.mock('@/lib/api/client', () => ({
  apiClient: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

beforeEach(() => {
  vi.clearAllMocks();
});

/**
 * The bottom bar is the phone's navigation, so it has to be a real set of destinations derived
 * from the same declaration the sidebar reads — not a second list that can quietly fall behind.
 */
describe('bottom navigation', () => {
  it('gives a phone the five destinations it moves between most', async () => {
    renderApp('/review');

    const bar = await screen.findByRole('navigation', { name: '主导航（底部）' });
    const hrefs = within(bar).getAllByRole('link').map((link) => link.getAttribute('href'));
    expect(hrefs).toEqual(['/', '/exam', '/course', '/programming', '/profile']);
  });

  it('keeps the full destination as the accessible name while showing the short label', async () => {
    renderApp('/review');
    const bar = await screen.findByRole('navigation', { name: '主导航（底部）' });

    // Short on screen, complete to a screen reader — and the visible word is part of that name.
    expect(within(bar).getByText('我的')).toBeInTheDocument();
    expect(within(bar).getByRole('link', { name: '我的学习档案' })).toHaveAttribute(
      'href',
      '/profile',
    );
    expect(within(bar).getByRole('link', { name: '编程学习' })).toHaveAttribute(
      'href',
      '/programming',
    );
  });

  it('marks the current destination and leaves the rest unmarked', async () => {
    renderApp('/programming');

    const bar = await screen.findByRole('navigation', { name: '主导航（底部）' });
    expect(within(bar).getByRole('link', { name: '编程学习' })).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(within(bar).getByRole('link', { name: '课程学习' })).not.toHaveAttribute('aria-current');
    expect(within(bar).getByRole('link', { name: '首页' })).not.toHaveAttribute('aria-current');
  });
});
