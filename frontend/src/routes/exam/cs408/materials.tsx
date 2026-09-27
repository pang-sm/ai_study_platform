import { createFileRoute } from '@tanstack/react-router';
import { Cs408MaterialsWorkspace } from '@/features/exam/components/cs408-materials-workspace';

/**
 * The paper's 资料库, as a page OF the paper.
 *
 * `module` is not defaulted: material belongs to the paper it was uploaded for, and a page that
 * guessed which paper would file the learner's next upload under a subject they never chose.
 */
export const Route = createFileRoute('/exam/cs408/materials')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
  }),
  component: MaterialsRoute,
});

function MaterialsRoute() {
  const { module } = Route.useSearch();
  return <Cs408MaterialsWorkspace moduleKey={module} />;
}
