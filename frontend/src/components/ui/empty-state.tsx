import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * An empty region that says why it is empty and what would fill it.
 *
 * Deliberately not a card: nothing here is clickable, so a border and a background would only
 * add another rectangle to the page. The left rule matches how dated items are marked
 * elsewhere, which keeps "no data" visually quieter than real content.
 */
export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  /** The statement of fact. It stands alone, so a caller that has nothing to add can omit the rest. */
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('border-l-2 border-border-default pl-4', className)}>
      <p className="text-body text-text-primary">{title}</p>
      {description ? (
        <p className="mt-2 max-w-prose text-body text-text-secondary">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
