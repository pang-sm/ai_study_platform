import { createFileRoute } from '@tanstack/react-router';
import { ProgrammingRecordsPage } from '@/features/programming/components/programming-records-page';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

export const Route = createFileRoute('/programming/records')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingRecordsRoute,
});

function ProgrammingRecordsRoute() {
  const { language } = Route.useSearch();
  // No gate: the recorded facts are the whole space's and the endpoint takes no language, so the
  // page reads without one. The language in the strip is the context the other tools open in.
  return <ProgrammingRecordsPage language={language} />;
}
