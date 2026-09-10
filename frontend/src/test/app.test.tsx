import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  RouterProvider,
  createMemoryHistory,
  createRouter,
} from '@tanstack/react-router';
import { describe, expect, it } from 'vitest';
import { routeTree } from '@/routeTree.gen';

function renderApp(initialPath = '/') {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  });
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe('App', () => {
  it('renders the index route', async () => {
    renderApp('/');
    expect(await screen.findByText('Frontend architecture initialized.')).toBeInTheDocument();
  });

  it('renders the not-found route for unknown paths', async () => {
    renderApp('/does-not-exist');
    expect(await screen.findByText('页面不存在')).toBeInTheDocument();
  });
});
