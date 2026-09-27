import { createFileRoute } from '@tanstack/react-router';
import { Cs408PracticeWorkspace } from '@/features/exam/components/cs408-practice-workspace';
import { searchIdentifier } from '@/lib/router';

/**
 * `chapter`, `concept` and `attempt` are IDENTIFIERS the URL carries, and they are kept in the
 * type the router parsed them into — see `searchIdentifier`. The page converts them to the
 * strings its API needs; coercing them here is what used to rewrite `?chapter=1` as
 * `?chapter=%221%22`.
 */
export const Route = createFileRoute('/exam/cs408/practice')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
    chapter: searchIdentifier(search.chapter),
    // The canonical knowledge leaf this practice was entered FROM. Set only by a surface
    // that holds it as a canonical id (the knowledge tree's own node code) — never derived
    // from a title, a path, a list position or the question text. Absent for every other
    // entry point, where no canonical concept is known.
    concept: searchIdentifier(search.concept),
    attempt: typeof search.attempt === 'number' && Number.isInteger(search.attempt) && search.attempt > 0 ? search.attempt : undefined,
  }),
  component: PracticeRoute,
});

function PracticeRoute() {
  const { module, chapter, concept, attempt } = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <Cs408PracticeWorkspace
      moduleKey={module}
      chapterCode={chapter === undefined ? undefined : String(chapter)}
      conceptCode={concept === undefined ? undefined : String(concept)}
      attemptId={attempt}
      onAttemptChange={(attemptId) => void navigate({ search: (current) => ({ ...current, attempt: attemptId }) })}
    />
  );
}
