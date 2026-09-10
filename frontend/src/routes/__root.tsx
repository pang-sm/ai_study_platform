import { createRootRoute, Outlet } from '@tanstack/react-router';
import { AppShell } from '@/components/layout/app-shell';
import { NotFound } from '@/components/layout/not-found';
import { ErrorState } from '@/components/layout/error-state';

export const Route = createRootRoute({
  component: RootComponent,
  notFoundComponent: NotFound,
  errorComponent: ErrorState,
});

function RootComponent() {
  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
