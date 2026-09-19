import { createFileRoute } from '@tanstack/react-router';
import { Cs408PastPaperWorkspace } from '@/features/exam/components/cs408-past-paper-workspace';

export const Route = createFileRoute('/exam/cs408/past-papers')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
    year: typeof search.year === 'number' && Number.isInteger(search.year) ? search.year : undefined,
    attempt: typeof search.attempt === 'number' && Number.isInteger(search.attempt) && search.attempt > 0 ? search.attempt : undefined,
  }),
  component: PastPapersRoute,
});

function PastPapersRoute() {
  const { module, year, attempt } = Route.useSearch(); const navigate = Route.useNavigate();
  return <Cs408PastPaperWorkspace moduleKey={module} year={year} attemptId={attempt} onAttemptChange={(attemptId) => void navigate({ search: (current) => ({ ...current, attempt: attemptId }) })} />;
}
