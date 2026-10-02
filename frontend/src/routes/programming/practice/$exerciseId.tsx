import { createFileRoute } from '@tanstack/react-router';
import { PracticeDetailPage } from '@/features/programming/components/programming-practice-page';
import { ProgrammingToolGate } from '@/features/programming/components/programming-shell';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

export const Route = createFileRoute('/programming/practice/$exerciseId')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingExerciseDetailRoute,
});

function ProgrammingExerciseDetailRoute() {
  const { language } = Route.useSearch();
  const { exerciseId } = Route.useParams();
  return (
    // `to` is the BANK, not this exercise: an exercise id belongs to one language's catalogue, so
    // a learner who has named no language is sent to where they can pick one, not to a question
    // that may not exist in the language they would have chosen.
    <ProgrammingToolGate
      slugFromUrl={language}
      to="/programming/practice"
      active="practice"
      description="题目属于某一门语言的题库。先选一门，再打开这道题。"
    >
      {(resolved) => <PracticeDetailPage language={resolved} exerciseId={Number(exerciseId)} />}
    </ProgrammingToolGate>
  );
}
