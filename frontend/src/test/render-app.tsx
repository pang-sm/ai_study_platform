import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router';
import { routeTree } from '@/routeTree.gen';
import { AuthProvider } from '@/features/auth/auth-context';
import { authKeys } from '@/features/auth/query-keys';
import type { AuthUser } from '@/features/auth/api/auth';

export const TEST_USER: AuthUser = {
  id: 1,
  username: 'test_learner',
  nickname: '测试学习者',
  plan: 'free',
  onboarding_completed: true,
};

function makeRouter(queryClient: QueryClient, initialPath: string) {
  return createRouter({
    routeTree,
    context: { queryClient },
    history: createMemoryHistory({ initialEntries: [initialPath] }),
  });
}

export type TestRouter = ReturnType<typeof makeRouter>;

/**
 * Seeds the session cache instead of letting the route guard fetch it.
 *
 * The guard reads `auth/session` through this same query client, so seeding it is what decides
 * whether the app under test is signed in — no network stub is involved, and a route that forgot
 * to consult the guard would still be caught by the cases that seed `null`.
 */
export function renderApp(
  initialPath = '/',
  { user = TEST_USER as AuthUser | null }: { user?: AuthUser | null } = {},
): ReturnType<typeof render> & { queryClient: QueryClient; router: TestRouter } {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(authKeys.session, user);

  const router = makeRouter(queryClient, initialPath);

  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );

  return { ...result, queryClient, router };
}
