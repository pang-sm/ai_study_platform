import { QueryClient } from '@tanstack/react-query';

/**
 * Conservative, web-app-appropriate defaults.
 * Avoid aggressive retry/refetch — let explicit invalidation drive freshness.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: 0,
    },
  },
});
