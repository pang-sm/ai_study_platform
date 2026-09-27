import { useEffect, useRef, useState } from 'react';
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
 *
 * Narrow screens needed two things the strip did not do on its own. The current tab has to be
 * VISIBLE — at 390 the later tabs sit off the right edge, so landing on 学习状态 showed a strip
 * whose marked tab was the one you could not see; the strip now centres it. And a cut-off tail
 * has to look cut off rather than look finished, which is what the fade says; it appears only
 * while there is something further along.
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
  const listRef = useRef<HTMLUListElement>(null);
  const activeRef = useRef<HTMLLIElement>(null);
  const [overflows, setOverflows] = useState(false);

  // Centre the current tab. Done by setting `scrollLeft` rather than `scrollIntoView`, because
  // the latter also scrolls the PAGE, and entering a page must not move the reader vertically.
  useEffect(() => {
    const list = listRef.current;
    const item = activeRef.current;
    if (!list || !item) return;
    if (list.scrollWidth <= list.clientWidth) return;
    list.scrollLeft = Math.max(0, item.offsetLeft - (list.clientWidth - item.clientWidth) / 2);
  }, [activeId]);

  // Whether anything is out of view to the right, for the fade. Re-measured on resize, because
  // the same strip overflows at 390 and does not at 1440.
  useEffect(() => {
    const list = listRef.current;
    if (!list || typeof ResizeObserver === 'undefined') return;
    const measure = () => setOverflows(list.scrollWidth > list.clientWidth + 1);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(list);
    return () => observer.disconnect();
  }, [items.length]);

  return (
    <nav aria-label={ariaLabel} className={cn('border-b border-border-default', className)}>
      <ul
        ref={listRef}
        className={cn('-mb-px flex gap-1 overflow-x-auto', overflows && 'context-nav--overflows')}
      >
        {items.map((item) => {
          const active = item.id === activeId;
          return (
            <li key={item.id} ref={active ? activeRef : undefined} className="shrink-0">
              <Link
                to={routePath(item.to)}
                params={item.params}
                search={item.search}
                aria-current={active ? 'page' : undefined}
                // `context-nav-tab` is the hook the space accent uses for the current tab's rule
                // and label. The classes below remain the default for a tab strip rendered
                // outside a learning space, so nothing here depends on an ancestor existing.
                className={cn(
                  'context-nav-tab inline-flex min-h-11 items-center border-b-2 px-3 text-body transition-colors duration-fast ease-standard',
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
