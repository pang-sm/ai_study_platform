import { createFileRoute } from '@tanstack/react-router';
import { Cs408PracticeWorkspace } from '@/features/exam/components/cs408-practice-workspace';

export const Route = createFileRoute('/exam/cs408/practice')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
    chapter: typeof search.chapter === 'string' || typeof search.chapter === 'number' ? String(search.chapter) : undefined,
    attempt: typeof search.attempt === 'number' && Number.isInteger(search.attempt) && search.attempt > 0 ? search.attempt : undefined,
  }),
  component: PracticeRoute,
});

function PracticeRoute() {
  const { module, chapter, attempt } = Route.useSearch();
  const navigate = Route.useNavigate();
  return <Cs408PracticeWorkspace moduleKey={module} chapterCode={chapter} attemptId={attempt} onAttemptChange={(attemptId) => void navigate({ search: (current) => ({ ...current, attempt: attemptId }) })} />;
}
