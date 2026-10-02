import { Link, createFileRoute, redirect } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/page/page-header';
import { legacyProgrammingTarget } from '@/features/programming/legacy-routes';
import { routePath } from '@/lib/router';

/**
 * Every address that names a language in the path, forwarded to the tool that owns it now.
 *
 * The programming space used to hang its tools off the language — `/programming/python/records`
 * — and those URLs are everywhere a learner's own history is stored: bookmarks, pasted links, and
 * the deep links the backend recomputes on every read (`backend/learning/agenda.py`,
 * `backend/learning/review.py`). The tools live at the space's own paths now and carry the
 * language in the search, so this is the one place that has to know both shapes.
 *
 * A redirect rather than a page: nothing here has content of its own, and rendering something
 * first would put a page in front of a learner on their way to one. An address this build cannot
 * place renders the not-found the app already has, rather than guessing at a destination — the
 * `component` below is only reached for those.
 */
export const Route = createFileRoute('/programming/$')({
  beforeLoad: ({ params }) => {
    const target = legacyProgrammingTarget(params._splat ?? '');
    if (!target) return;
    // `to`/`params`/`search` are widened here because the destination is composed from the route
    // table at runtime; `routePath` exists for exactly this, and the route ids it produces are
    // checked by the redirect itself when the router resolves them.
    throw redirect({
      to: routePath(target.to) as never,
      params: (target.params ?? {}) as never,
      search: target.search as never,
      replace: true,
    });
  },
  component: ProgrammingUnknownRoute,
});

function ProgrammingUnknownRoute() {
  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="编程学习"
        title="没有这个页面"
        description="这个地址不属于编程学习；练习、AI 编程助手、成长记录与计划都在工作台里。"
      />
      <Button asChild variant="secondary" className="mt-6">
        <Link to="/programming">回到编程工作台</Link>
      </Button>
    </div>
  );
}
