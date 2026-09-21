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
      <p className="text-metadata font-medium tracking-eyebrow text-primary-ink">先建立学习空间</p>
      <h2 id="first-run-title" className="mt-2 text-section-title font-semibold text-text-primary">
        先建立一个学习空间，智学AI才能为你形成真实学习安排。
      </h2>
      <p className="mt-4 max-w-prose text-body text-text-secondary">
        每个学习空间都有自己的上下文：课程空间围绕你声明的课程，考研空间围绕你确认的科目，编程空间围绕你要练的语言。
        设置好任意一个，首页就会回到今天该做什么。
      </p>

      <ul className="mt-6">
        {spaces.map((space) => (
          <li
            key={space.id}
            className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-t border-border-default py-5"
          >
            <div className="min-w-0">
              <p className="text-body font-medium text-text-primary">{space.label}</p>
              <p className="mt-1 max-w-prose text-metadata text-text-secondary">
                {space.failed ? '暂时无法读取这个学习空间的状态。' : space.missing} {space.purpose}
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
          有学习空间的状态没有读到；这不影响你在对应页面里直接开始。
        </StatusNote>
      ) : null}
    </Panel>
  );
}
