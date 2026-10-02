import { createFileRoute } from '@tanstack/react-router';
import { WorkbenchPage } from '@/features/programming/components/workbench/workbench-page';
import { validateWorkbenchSearch } from '@/features/programming/programming-context';

/**
 * 编程工作台 — the workspace itself, at the space's own level.
 *
 * The language and the open题 both ride in the search rather than the path, so selecting a题 is a
 * state change inside one page instead of a navigation to a new one — which is the whole point of
 * a workspace. An address that names no language renders the workspace's own language question
 * rather than guessing.
 */
export const Route = createFileRoute('/programming/workbench/')({
  validateSearch: validateWorkbenchSearch,
  component: ProgrammingWorkbenchRoute,
});

function ProgrammingWorkbenchRoute() {
  const { language, exercise } = Route.useSearch();
  return <WorkbenchPage language={language} exerciseId={exercise} />;
}
