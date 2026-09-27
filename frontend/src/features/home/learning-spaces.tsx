import { Link } from '@tanstack/react-router';
import { ArrowRight } from 'lucide-react';
import { accentClasses, LEARNING_SPACES } from '@/components/layout/primary-nav';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { routePath } from '@/lib/router';
import type { SpaceContext } from './space-context';

const NOT_READABLE = '暂时读不到这个方向的状态。';

/**
 * The three directions, each stating where the learner stands in its own words.
 *
 * This is not a dashboard: a card carries one line, and that line is a value the direction's own
 * endpoint returned — a declared language, the subjects chosen, the courses set up. A direction
 * with nothing recorded says what is missing rather than showing a zero, and a direction whose
 * read failed says so rather than showing a confident blank. The card's real job is the link: it
 * is the way back into a space from the page that says what to do today.
 */
export function LearningSpaces({ spaces }: { spaces: readonly SpaceContext[] }) {
  // The cards follow the header's order, not the order the three reads happen to resolve in:
  // the same three names in two orders on one screen reads as two different sets of things.
  const navOrder = new Map(LEARNING_SPACES.map((item, index) => [item.to, index]));
  const ordered = [...spaces].sort(
    (a, b) => (navOrder.get(`/${a.id}`) ?? 99) - (navOrder.get(`/${b.id}`) ?? 99),
  );

  return (
    <section aria-labelledby="learning-spaces-title" className="mt-10">
      <h2 id="learning-spaces-title" className="text-section-title font-semibold text-text-primary">
        我的学习方向
      </h2>

      <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ordered.map((space) => {
          const nav = LEARNING_SPACES.find((item) => item.to === `/${space.id}`);
          const accent = nav?.accent;
          const label = nav?.label ?? space.label;
          const destination = nav?.to ?? `/${space.id}`;
          // "Nothing is set up here" is a claim about the direction, so it is only made when the
          // direction itself answered that way. A direction that IS set up but whose one line
          // could not be built shows no line at all — an empty line is honest, and a status this
          // page cannot state is not improved by guessing at one.
          const detail = space.failed
            ? NOT_READABLE
            : space.configured
              ? space.status
              : space.missing;
          const awaiting = space.pending;

          return (
            <li key={space.id}>
              <Link
                to={routePath(destination)}
                className={cn(
                  'flex h-full min-h-28 flex-col justify-between gap-4 rounded-card border border-border-default bg-surface p-5',
                  'transition-colors duration-fast ease-standard hover:bg-primary-soft',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
                )}
              >
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-body font-medium text-text-primary">
                    {accent ? (
                      <span
                        aria-hidden="true"
                        className={cn('h-3.5 w-1 shrink-0 rounded-pill', accentClasses[accent])}
                      />
                    ) : null}
                    {label}
                  </p>
                  {/* While the direction is still answering, the line is withheld rather than
                      guessed: "还没有声明课程" shown for a learner who has declared three is a
                      claim the page cannot make yet. */}
                  {awaiting ? (
                    <Skeleton className="mt-2 h-4 w-32" />
                  ) : detail ? (
                    <p className="mt-2 text-metadata text-text-secondary wrap-anywhere">{detail}</p>
                  ) : null}
                </div>
                <span className="inline-flex items-center gap-1.5 text-body font-medium text-primary-ink">
                  {space.cta}
                  <ArrowRight className="size-4" aria-hidden="true" />
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
