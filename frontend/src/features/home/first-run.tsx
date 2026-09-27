import { Link } from '@tanstack/react-router';
import { Panel } from '@/components/ui/panel';
import { StatusNote } from '@/components/ui/status-note';
import { routePath } from '@/lib/router';
import type { SpaceContext } from './space-context';

/**
 * The first thing a learner sees, before any of the three spaces holds a context.
 *
 * It is deliberately not a set of feature cards: each row states what that space is organised
 * around, what is still missing in it, and the one screen where that is fixed. Nothing is
 * promoted above the others — the choice of where to start belongs to the learner, so no row
 * carries the page's primary action and none is described as recommended.
 */
export function FirstRunSurface({ spaces }: { spaces: readonly SpaceContext[] }) {
  const failed = spaces.filter((space) => space.failed);

  return (
    <Panel tone="focus" labelledBy="first-run-title">
      <p className="text-metadata font-medium tracking-eyebrow text-primary-ink">先设置一个学习方向</p>
      <h2 id="first-run-title" className="mt-2 text-section-title font-semibold text-text-primary">
        设置任意一个方向，就可以开始学习。
      </h2>

      <ul className="mt-6">
        {spaces.map((space) => (
          <li
            key={space.id}
            className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-t border-border-default py-5"
          >
            <div className="min-w-0">
              <p className="text-body font-medium text-text-primary">{space.label}</p>
              <p className="mt-1 max-w-prose text-metadata text-text-secondary">
                {space.failed ? '暂时读不到这个方向的设置。' : space.missing} {space.purpose}
              </p>
            </div>
            <Link
              to={routePath(space.action.to)}
              search={space.action.search}
              className="inline-flex h-11 shrink-0 items-center rounded-control border border-border-default bg-surface px-4 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              {space.action.label}
            </Link>
          </li>
        ))}
      </ul>

      {failed.length ? (
        <StatusNote tone="warning" className="mt-5">
          有方向的设置没有读到；这不影响你在对应页面里直接开始。
        </StatusNote>
      ) : null}
    </Panel>
  );
}
