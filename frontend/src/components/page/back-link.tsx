import { Link } from '@tanstack/react-router';
import { ArrowLeft } from 'lucide-react';
import { routePath } from '@/lib/router';
import { cn } from '@/lib/utils';

/**
 * The way out of a page, stated as a destination rather than as a history step.
 *
 * Pages inside a learning space used to rely on the browser's back button and on a breadcrumb
 * trail, which meant a learner who opened a URL directly — from a bookmark, a chat message, a
 * pasted link — had no way out at all, and a learner who arrived through a redirect went
 * wherever the history happened to point. Every caller here names the page above it, so the
 * control says the same thing and goes to the same place however the page was reached.
 *
 * It is not a breadcrumb: one hop, one label, and the destination is the caller's to state.
 */
export function BackLink({
  to,
  params,
  search,
  label = '返回',
  className,
}: {
  /** The page above this one. Absolute path, from the same route table the links point into. */
  to: string;
  params?: Record<string, string>;
  search?: Record<string, unknown>;
  /** What the destination is called, when 返回 alone would not say it ("返回 408"). */
  label?: string;
  className?: string;
}) {
  return (
    <Link
      to={routePath(to)}
      params={params}
      search={search}
      className={cn(
        'inline-flex min-h-9 items-center gap-1 rounded-control pr-2 text-metadata font-medium text-text-secondary',
        'hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
        className,
      )}
    >
      <ArrowLeft className="size-4" aria-hidden="true" />
      {label}
    </Link>
  );
}
