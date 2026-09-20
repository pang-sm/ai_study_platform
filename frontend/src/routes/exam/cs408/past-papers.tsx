import { createFileRoute } from '@tanstack/react-router';
import { Cs408PastPaperWorkspace } from '@/features/exam/components/cs408-past-paper-workspace';

const positiveInt = (value: unknown) => typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : undefined;

export const Route = createFileRoute('/exam/cs408/past-papers')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
    year: typeof search.year === 'number' && Number.isInteger(search.year) ? search.year : undefined,
    attempt: positiveInt(search.attempt),
    // The paper's own public question identity. A past-paper question has no row id in the
    // contract, so `(subject_key, year, question_number)` IS its canonical identity — which
    // is exactly what makes this a factual deep link rather than a positional guess.
    question: positiveInt(search.question),
  }),
  component: PastPapersRoute,
});

function PastPapersRoute() {
  const { module, year, attempt, question } = Route.useSearch(); const navigate = Route.useNavigate();
  return <Cs408PastPaperWorkspace moduleKey={module} year={year} attemptId={attempt} questionNumber={question} onAttemptChange={(attemptId) => void navigate({ search: (current) => ({ ...current, attempt: attemptId }) })} />;
}
