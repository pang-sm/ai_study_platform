import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '@/test/render-app';

describe('route guard', () => {
  it('sends an unauthenticated visitor to /login, carrying the destination it blocked', async () => {
    const { router } = renderApp('/exam/cs408/practice?module=data_structure', { user: null });

    expect(await screen.findByRole('heading', { name: '登录' })).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
    expect(router.state.location.search).toMatchObject({
      returnTo: '/exam/cs408/practice?module=data_structure',
    });
  });

  it('guards the learning spaces, the review queue and the learning report alike', async () => {
    for (const path of ['/course', '/programming', '/review', '/membership', '/profile']) {
      const { router, unmount } = renderApp(path, { user: null });
      await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
      unmount();
    }
  });

  it('does not show a sign-in form to a visitor who already has a valid session', async () => {
    const { router } = renderApp('/login');

    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
    expect(screen.queryByRole('heading', { name: '登录' })).not.toBeInTheDocument();
  });

  it('honours returnTo for an already-signed-in visitor sent to /login', async () => {
    const { router } = renderApp('/login?returnTo=%2Freview');

    await waitFor(() => expect(router.state.location.pathname).toBe('/review'));
  });

  it('keeps the protected route for a restored session instead of bouncing to login', async () => {
    const { router } = renderApp('/review');

    await waitFor(() => expect(router.state.location.pathname).toBe('/review'));
    expect(screen.queryByRole('heading', { name: '登录' })).not.toBeInTheDocument();
  });
});
