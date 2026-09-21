import { createRouter } from '@tanstack/react-router';
import type { QueryClient } from '@tanstack/react-query';
import { routeTree } from './routeTree.gen';
import { queryClient as defaultQueryClient } from '@/lib/query/query-client';

/**
 * The router receives the query client as context so that route guards and rendered components
 * read the SAME cache. A guard that awaited its own session request would be able to disagree
 * with the header about whether the visitor is signed in.
 */
export function createAppRouter(queryClient: QueryClient = defaultQueryClient) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    defaultPreloadStaleTime: 0,
    scrollRestoration: true,
  });
}

export const router = createAppRouter();

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
