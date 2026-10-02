import { createFileRoute } from '@tanstack/react-router';
import { ProgrammingAiPage } from '@/features/programming/components/programming-ai-page';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

export const Route = createFileRoute('/programming/ai')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingAiRoute,
});

function ProgrammingAiRoute() {
  const { language } = Route.useSearch();
  // The page, not a gate: the assistant can ask for the language itself, and it does so inside the
  // same shell the other tools use, so the way it asks looks like every other page here.
  return <ProgrammingAiPage language={language} />;
}
