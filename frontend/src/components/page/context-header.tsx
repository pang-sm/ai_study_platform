import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type ContextFact = { label: string; value: ReactNode };

/**
 * What this page is *about* — the course, the exam module, the chapter, the language.
 *
 * The three spaces each carry a different context vocabulary, so this component does not try to
 * name those dimensions itself: it renders the facts the domain hands it, in one row, above the
 * content. That is the whole requirement — a learner should never have to infer from the page
 * body which course or chapter they are looking at.
 */
export function ContextHeader({
  facts,
  note,
  actions,
  className,
}: {
  facts: readonly ContextFact[];
  note?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  if (!facts.length && !note) return null;
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-x-8 gap-y-3 border-b border-border-default py-4',
        className,
      )}
    >
      <dl className="flex flex-wrap gap-x-8 gap-y-2">
        {facts.map((fact) => (
          <div key={fact.label}>
            <dt className="text-metadata font-medium tracking-eyebrow text-text-muted">{fact.label}</dt>
            <dd className="mt-1 text-body text-text-primary">{fact.value}</dd>
          </div>
        ))}
      </dl>
      {note ? <p className="max-w-prose text-metadata text-text-secondary">{note}</p> : null}
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
