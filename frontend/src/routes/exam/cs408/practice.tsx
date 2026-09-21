import { createFileRoute } from '@tanstack/react-router';
import { Cs408PracticeWorkspace } from '@/features/exam/components/cs408-practice-workspace';
import { AdaptivePractice } from '@/components/learning/adaptive-practice';

export const Route = createFileRoute('/exam/cs408/practice')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
    chapter: typeof search.chapter === 'string' || typeof search.chapter === 'number' ? String(search.chapter) : undefined,
    // The canonical knowledge leaf this practice was entered FROM. Set only by a surface
    // that holds it as a canonical id (the knowledge tree's own node code) — never derived
    // from a title, a path, a list position or the question text. Absent for every other
    // entry point, where no canonical concept is known.
    concept: typeof search.concept === 'string' && search.concept.trim() ? search.concept : undefined,
    attempt: typeof search.attempt === 'number' && Number.isInteger(search.attempt) && search.attempt > 0 ? search.attempt : undefined,
  }),
  component: PracticeRoute,
});

function PracticeRoute() {
  const { module, chapter, concept, attempt } = Route.useSearch();
  const navigate = Route.useNavigate();
  return <><AdaptivePractice serviceKey="exam_11408" examModuleId={module} entryHref="/exam/cs408/practice" /><Cs408PracticeWorkspace moduleKey={module} chapterCode={chapter} conceptCode={concept} attemptId={attempt} onAttemptChange={(attemptId) => void navigate({ search: (current) => ({ ...current, attempt: attemptId }) })} /></>;
}
