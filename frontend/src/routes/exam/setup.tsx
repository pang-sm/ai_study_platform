import { createFileRoute } from '@tanstack/react-router';
import { ExamSetupPage } from '@/features/exam/components/exam-product-pages';
import { sanitizeReturnTo } from '@/features/auth/return-to';

export const Route = createFileRoute('/exam/setup')({
  // The exam space's setup screen is the one the other two were modelled on, so it takes the
  // same validated `returnTo` — an entry from the first-run Home lands back on Home.
  validateSearch: (search: Record<string, unknown>) => {
    const returnTo = sanitizeReturnTo(search.returnTo);
    return returnTo ? { returnTo } : {};
  },
  component: ExamSetupRoute,
});

function ExamSetupRoute() {
  const { returnTo } = Route.useSearch();
  return <ExamSetupPage returnTo={returnTo} />;
}
