import { Link } from '@tanstack/react-router';
import { routePath } from '@/lib/router';
import { cn } from '@/lib/utils';

export type ContextNavItem = {
  id: string;
  label: string;
  to: string;
  params?: Record<string, string>;
  search?: Record<string, unknown>;
};

/**
 * The tabs of one learning space.
 *
 * Every space previously grew its own version of this — one in the course shell, one inline on
 * the CS408 overview, none at all on the programming pages — so the same three spaces were
 * navigable in three different ways. This is that one navigation: always visible, wrapping or
 * scrolling horizontally on a phone, with the current tab marked by `aria-current` as well as by
 * its rule. Nothing here is hover-only, and an inactive tab is never hidden behind a control.
 */
export function ContextNav({
  ariaLabel,
  items,
  activeId,
  className,
}: {
  ariaLabel: string;
  items: readonly ContextNavItem[];
  activeId?: string;
  className?: string;
}) {
  return (
    <nav aria-label={ariaLabel} className={cn('border-b border-border-default', className)}>
      <ul className="-mb-px flex gap-1 overflow-x-auto">
        {items.map((item) => {
          const active = item.id === activeId;
          return (
            <li key={item.id} className="shrink-0">
              <Link
                to={routePath(item.to)}
                params={item.params}
                search={item.search}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'inline-flex min-h-11 items-center border-b-2 px-3 text-body transition-colors duration-fast ease-standard',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset',
                  active
                    ? 'border-primary font-medium text-primary-ink'
                    : 'border-transparent text-text-secondary hover:text-text-primary',
                )}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
