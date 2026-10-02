import { Link, createFileRoute, redirect } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/page/page-header';
import { legacyProgrammingTarget } from '@/features/programming/legacy-routes';
import { validateProgrammingSearch } from '@/features/programming/programming-context';
import { routePath } from '@/lib/router';

/**
 * Every older programming address, forwarded to where it lives now.
 *
 * The space has had two address shapes before this one — tools hanging off the language, then the
 * tools as the space's own pages — and both are still in learners' bookmarks and in the deep links
 * the backend recomputes on every read. All of them now land in the workspace, which is where the
 * exercises, the editor, the runs and the AI 助手 are; `legacyProgrammingTarget` is the one place
 * that knows both older shapes.
 *
 * A redirect rather than a page: nothing here has content of its own, and rendering something
 * first would put a page in front of a learner on their way to one. An address this build cannot
 * place renders the not-found the app already has, rather than guessing at a destination.
 */
export const Route = createFileRoute('/programming/$')({
  validateSearch: validateProgrammingSearch,
  beforeLoad: ({ params, search }) => {
    const target = legacyProgrammingTarget(params._splat ?? '', search.language);
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
        description="这个地址不属于编程学习；题目、编辑器、AI 教练与提交记录都在编程工作台里。"
      />
      <Button asChild variant="secondary" className="mt-6">
        <Link to="/programming">回到编程学习</Link>
      </Button>
    </div>
  );
}
