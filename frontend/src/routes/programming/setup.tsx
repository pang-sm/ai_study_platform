import { createFileRoute } from '@tanstack/react-router';
import { ProgrammingSetupPage } from '@/features/programming/components/programming-setup-page';
import { sanitizeReturnTo } from '@/features/auth/return-to';

export const Route = createFileRoute('/programming/setup')({
  // The destination is validated where it enters the app, under the same rule `/login` uses;
  // nothing downstream has to remember that it came from the address bar.
  validateSearch: (search: Record<string, unknown>) => {
    const returnTo = sanitizeReturnTo(search.returnTo);
    return returnTo ? { returnTo } : {};
  },
  component: ProgrammingSetupRoute,
});

function ProgrammingSetupRoute() {
  const { returnTo } = Route.useSearch();
  return <ProgrammingSetupPage returnTo={returnTo} />;
}
