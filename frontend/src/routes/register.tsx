import { createFileRoute } from '@tanstack/react-router';
import { RegisterPage } from '@/features/auth/components/register-page';
import { sanitizeReturnTo } from '@/features/auth/return-to';

export const Route = createFileRoute('/register')({
  staticData: { layout: 'bare' },
  // Validated where it enters the app, exactly like `/login`'s: the two screens hand the same
  // destination back and forth, so both have to accept it under the same rule.
  validateSearch: (search: Record<string, unknown>) => {
    const returnTo = sanitizeReturnTo(search.returnTo);
    return returnTo ? { returnTo } : {};
  },
  component: RegisterRoute,
});

function RegisterRoute() {
  const { returnTo } = Route.useSearch();
  return <RegisterPage returnTo={returnTo} />;
}
