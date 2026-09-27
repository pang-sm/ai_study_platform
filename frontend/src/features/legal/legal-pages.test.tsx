import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderApp, TEST_USER } from '@/test/render-app';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/lib/api/client', () => ({
  apiClient: { POST: post, GET: vi.fn(), PUT: vi.fn() },
  resolveApiResourceUrl: (value: string) => value,
}));

beforeEach(() => {
  post.mockReset();
  post.mockImplementation(async () => ({
    data: undefined,
    error: { detail: '未登录' },
    response: { ok: false, status: 401 },
  }));
});

describe('legal documents', () => {
  it('publishes the user agreement at /terms, readable while signed out', async () => {
    renderApp('/terms', { user: null });

    expect(await screen.findByRole('heading', { level: 1, name: '用户协议' })).toBeInTheDocument();
    expect(screen.getByText(/版本 V1/)).toBeInTheDocument();
    // Both ends of the clause list are present, so the document is the whole document.
    expect(screen.getByRole('heading', { name: /1\. 协议适用范围/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /11\. 联系方式/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /8\. 责任限制/ })).toBeInTheDocument();
  });

  it('publishes the privacy policy at /privacy, readable while signed out', async () => {
    renderApp('/privacy', { user: null });

    expect(await screen.findByRole('heading', { level: 1, name: '隐私政策' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /7\. Cookie 与本地存储/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /12\. 联系方式/ })).toBeInTheDocument();
  });

  it('stays readable for a signed-in reader instead of sending them to the app', async () => {
    // `/terms` is public, not signed-out-only: reading the terms while signed in is normal, and
    // the guard must not bounce a learner away from it.
    renderApp('/terms', { user: TEST_USER });

    expect(await screen.findByRole('heading', { level: 1, name: '用户协议' })).toBeInTheDocument();
  });

  it('links the two documents to each other', async () => {
    renderApp('/privacy', { user: null });
    await screen.findByRole('heading', { level: 1, name: '隐私政策' });

    expect(screen.getByRole('link', { name: '用户协议' })).toHaveAttribute('href', '/terms');
  });
});
