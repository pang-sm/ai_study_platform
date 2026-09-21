import { createFileRoute } from '@tanstack/react-router';
import { LoginPage } from '@/features/auth/components/login-page';
import { sanitizeReturnTo } from '@/features/auth/return-to';

export const Route = createFileRoute('/login')({
  staticData: { layout: 'bare' },
  // The destination is validated where it enters the app, so nothing downstream has to
  // remember that it came from the address bar.
  validateSearch: (search: Record<string, unknown>) => {
    const returnTo = sanitizeReturnTo(search.returnTo);
    return returnTo ? { returnTo } : {};
  },
  component: LoginRoute,
});

function LoginRoute() {
  const { returnTo } = Route.useSearch();
  return <LoginPage returnTo={returnTo} />;
}
