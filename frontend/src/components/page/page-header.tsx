import type { ReactNode } from 'react';
import { Breadcrumb, type Crumb } from './breadcrumb';
import { cn } from '@/lib/utils';

/**
 * The identity of a page: where it sits, what it is, and the one action it exists to offer.
 *
 * It is not a card and not a banner — a rule under the title is enough separation, and the
 * actions sit on the same line as the title so the page has exactly one obvious thing to do.
 * Pages that need to state the learning context underneath (course, module, chapter) put a
 * `ContextHeader` below this rather than folding it into the title.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  breadcrumb,
  actions,
  meta,
  titleId,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  breadcrumb?: readonly Crumb[];
  actions?: ReactNode;
  /** Small facts that belong to the title line (a count, a status badge). */
  meta?: ReactNode;
  titleId?: string;
  className?: string;
}) {
  return (
    <header className={cn('border-b border-border-default pb-6', className)}>
      {breadcrumb?.length ? <Breadcrumb items={breadcrumb} className="mb-3" /> : null}
      <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-metadata font-medium tracking-eyebrow text-text-muted">{eyebrow}</p>
          ) : null}
          <h1
            id={titleId}
            className={cn('text-page-title font-semibold text-text-primary', eyebrow ? 'mt-2' : undefined)}
          >
            {title}
          </h1>
          {meta ? <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">{meta}</div> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>
      {description ? (
        <p className="mt-3 max-w-prose text-body text-text-secondary">{description}</p>
      ) : null}
    </header>
  );
}
