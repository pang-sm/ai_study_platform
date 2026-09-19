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
    // Frozen Hero — the learning question that anchors the page.
    expect(await screen.findByRole('heading', { name: /一个虚拟地址/ })).toBeInTheDocument();
    // Primary content — the three learning worlds.
    expect(screen.getByRole('heading', { name: '选择你的学习方向' })).toBeInTheDocument();
  });

  it('renders the not-found route for unknown paths', async () => {
    renderApp('/does-not-exist');
    expect(await screen.findByText('页面不存在')).toBeInTheDocument();
  });

  it('renders the CS408 home for its exact route and mounts the knowledge child route', async () => {
    const home = renderApp('/exam/cs408');
    expect(await screen.findByRole('heading', { name: '学习工作区' })).toBeInTheDocument();
    home.unmount();

    renderApp('/exam/cs408/knowledge?module=data_structure');
    expect(await screen.findByRole('heading', { name: '数据结构知识脉络' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '学习工作区' })).not.toBeInTheDocument();
  });

  it('resolves the CS408 chapter practice route without inventing a chapter context', async () => {
    renderApp('/exam/cs408/practice');
    expect(await screen.findByRole('heading', { name: '选择学习模块' })).toBeInTheDocument();
    expect(screen.getByText('选择学习模块')).toBeInTheDocument();
  });
});
