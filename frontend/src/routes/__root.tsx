import { createRootRouteWithContext, Outlet, redirect, useMatches } from '@tanstack/react-router';
import type { QueryClient } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/app-shell';
import { NotFound } from '@/components/layout/not-found';
import { ErrorState } from '@/components/layout/error-state';
import { authKeys, fetchSession, type AuthUser } from '@/features/auth/api/auth';
import { resolvePostAuthDestination } from '@/features/auth/return-to';

declare module '@tanstack/react-router' {
  interface StaticDataRouteOption {
    /** `bare` renders the route without the product shell — the sign-in screens. */
    layout?: 'shell' | 'bare';
  }
}

const PUBLIC_PATHS = ['/login', '/register'];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

function readReturnTo(search: unknown): unknown {
  if (search && typeof search === 'object' && 'returnTo' in search) {
    return (search as { returnTo?: unknown }).returnTo;
  }
  return undefined;
}

/**
 * The one place that decides whether a visitor may see a route.
 *
 * Individual routes do NOT check authentication: a second check would be a second opinion, and
 * the two could drift. The session is read through the query cache, so `AuthProvider` and this
 * guard always answer from the same value.
 */
export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  beforeLoad: async ({ location, context }) => {
    const sessionQuery = {
      queryKey: authKeys.session,
      queryFn: fetchSession,
      staleTime: 60_000,
      retry: 0,
    } as const;

    if (isPublicPath(location.pathname)) {
      // A sign-in screen must paint immediately. Awaiting the probe here would hold the whole
      // page behind a network round trip — seconds of blank screen when the API cannot be
      // reached — so the cached answer decides now and the read continues in the background.
      // `LoginPage` sends an already-signed-in visitor onward the moment that read resolves.
      const cached = context.queryClient.getQueryData<AuthUser | null>(authKeys.session);
      if (cached) {
        throw redirect({ href: resolvePostAuthDestination(readReturnTo(location.search)) });
      }
      void context.queryClient.prefetchQuery(sessionQuery);
      return;
    }

    // A protected route cannot render without knowing who the visitor is, so this one waits —
    // but not through a retry ladder: a slow decision is worse than a fast, honest failure.
    const session = await context.queryClient.ensureQueryData(sessionQuery);

    if (!session) {
      throw redirect({ to: '/login', search: { returnTo: location.href } });
    }
  },
  component: RootComponent,
  notFoundComponent: NotFound,
  errorComponent: ErrorState,
  // The guard awaits one session read before any route renders, so without this the first paint
  // of a deep link is a blank page.
  pendingComponent: RootPending,
});

function RootPending() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page-background px-6 text-center">
      <p role="status" className="text-body text-text-secondary">
        正在读取你的学习状态…
      </p>
    </div>
  );
}

function RootComponent() {
  const matches = useMatches();
  if (matches.some((match) => match.staticData.layout === 'bare')) {
    return <Outlet />;
  }
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
