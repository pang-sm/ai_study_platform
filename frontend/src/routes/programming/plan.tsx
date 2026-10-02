import { createFileRoute } from '@tanstack/react-router';
import { ProgrammingPlanPage } from '@/features/programming/components/programming-plan-page';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

export const Route = createFileRoute('/programming/plan')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingPlanRoute,
});

function ProgrammingPlanRoute() {
  const { language } = Route.useSearch();
  // No gate: the plan endpoint falls back to the learner's declared languages when the address
  // names none, so the page can read without an explicit choice.
  return <ProgrammingPlanPage language={language} />;
}
