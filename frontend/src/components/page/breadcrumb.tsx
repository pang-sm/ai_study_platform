import { Link } from '@tanstack/react-router';
import { ChevronRight } from 'lucide-react';
import { routePath } from '@/lib/router';
import { cn } from '@/lib/utils';

export type Crumb = {
  label: string;
  /** Omit on the last crumb: the page a visitor is already reading is not a link. */
  to?: string;
  params?: Record<string, string>;
  search?: Record<string, unknown>;
};

/**
 * Where this page sits: learning space → context → page. The trail is a list rather than a row of
 * separators so it reads in order to a screen reader, and the last entry carries `aria-current`.
 * Nothing here depends on hover, and no crumb is a link unless the caller supplies a destination.
 */
export function Breadcrumb({ items, className }: { items: readonly Crumb[]; className?: string }) {
  if (!items.length) return null;
  return (
    <nav aria-label="面包屑" className={cn('text-metadata text-text-secondary', className)}>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {items.map((item, index) => (
          <li key={`${item.label}-${index}`} className="flex items-center gap-x-2">
            {index > 0 ? <ChevronRight className="size-3.5 text-text-muted" aria-hidden="true" /> : null}
            {item.to ? (
              // An explicit colour, not the global anchor blue: breadcrumbs also sit on the exam
              // shell's paper background, where #2563eb falls to 4.09:1 against #e8e5da.
              <Link
                to={routePath(item.to)}
                params={item.params}
                search={item.search}
                className="rounded-control text-text-secondary underline-offset-4 hover:text-primary-ink hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {item.label}
              </Link>
            ) : (
              <span aria-current="page" className="text-text-primary">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
