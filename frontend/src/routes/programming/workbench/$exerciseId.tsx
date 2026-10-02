import { createFileRoute, redirect } from '@tanstack/react-router';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

/**
 * The题-addressed shape, kept for the links already in the world.
 *
 * `/programming/workbench/7` — where the old Workbench was reached from a题面, and what the
 * backend's own deep links still build — now opens the same workspace with that题 selected. The
 * workspace addresses its open题 in the search rather than the path, so this is a redirect into
 * that state rather than a page of its own.
 */
export const Route = createFileRoute('/programming/workbench/$exerciseId')({
  validateSearch: validateProgrammingSearch,
  beforeLoad: ({ params, search }) => {
    const exercise = Number(params.exerciseId);
    throw redirect({
      to: '/programming/workbench',
      search: {
        ...(search.language ? { language: search.language } : {}),
        ...(Number.isFinite(exercise) && exercise > 0 ? { exercise } : {}),
      } as never,
      replace: true,
    });
  },
});
