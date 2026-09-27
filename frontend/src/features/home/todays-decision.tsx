import { ArrowRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { useDailyAgenda } from './agenda-api';
import { decisionBadges, decisionSentence, localDeepLink, scopeLine } from './agenda-narrative';

/**
 * The one thing to do now.
 *
 * The heading above the card is a SECTION heading, built from the same component as 今天接下来 and
 * 我的学习方向, because "现在先做" names a part of the page — not a property of the card. It used
 * to sit inside the card as a small eyebrow, which read as a label on one card and left the item's
 * own title as the loudest thing on the page; a learner arriving had to read the title before they
 * could tell it was the top priority. The order is now stated before the work is named.
 *
 * The card below it is deliberately open, not a nested landmark: the section is the region, the
 * card is what the section contains.
 *
 * The backend ranks the agenda with a fixed policy and hands back the first entry already at the
 * top. This section gives that entry the page's focal treatment and nothing else — the list of
 * everything after it is the section below, so a task is never shown twice.
 */
export function TodaysDecision({ courseNames }: { courseNames?: ReadonlyMap<string, string> }) {
  const agenda = useDailyAgenda();

  if (agenda.isPending) {
    return (
      <section aria-labelledby="todays-decision-heading" className="mt-8">
        <SectionHeading id="todays-decision-heading" title="现在先做" />
        {/* The gap to the card is tighter than the one between sections, so the heading reads as
            belonging to the card under it rather than to the page in general. */}
        <Panel tone="focus" className="mt-2">
          <div aria-hidden="true">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="mt-1.5 h-6 w-72 max-w-full" />
            <Skeleton className="mt-3 h-4 w-full" />
            <Skeleton className="mt-1.5 h-4 w-2/3" />
            <Skeleton className="mt-4 h-12 w-36" />
          </div>
          <p role="status" className="sr-only">
            正在读取今天的学习建议…
          </p>
        </Panel>
      </section>
    );
  }

  if (agenda.isError) {
    return (
      <section aria-labelledby="todays-decision-heading" className="mt-8">
        <SectionHeading id="todays-decision-heading" title="现在先做" />
        <StatusNote tone="danger" className="mt-2">
          今天的学习建议暂时读不到。下面的学习方向仍然可以继续使用。
        </StatusNote>
      </section>
    );
  }

  const item = (agenda.data.items ?? [])[0];
  // Nothing to do now is not a section with nothing in it: there is no "现在先做" to state, and an
  // empty heading would claim a slot the page is not filling.
  if (!item) {
    return (
      <EmptyState
        className="mt-10"
        title="今天暂时没有需要优先处理的学习任务。"
        description="从下面任意一个学习方向开始，下一次学习记录就会出现在这里。"
      />
    );
  }

  const href = localDeepLink(item.deep_link);
  const sentence = decisionSentence(item);
  const badges = decisionBadges(item);

  return (
    <section aria-labelledby="todays-decision-heading" className="mt-8">
      <SectionHeading id="todays-decision-heading" title="现在先做" />

      <Panel tone="focus" className="mt-2 lg:py-4">
        <div className="max-w-2xl">
          <p className="text-metadata text-text-secondary">{scopeLine(item, courseNames)}</p>

          <h3 className="mt-1.5 text-section-title font-semibold text-text-primary wrap-anywhere">
            {item.title}
          </h3>

          {sentence ? <p className="mt-2 text-body text-text-primary">{sentence}</p> : null}

          {/* Labels, not a list: nothing here is a thing to navigate to, and marking them up as
              one would put three more list items in front of a screen reader for two words of
              context. */}
          {badges.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {badges.map((badge) => (
                <Badge key={badge} tone="brand">
                  {badge}
                </Badge>
              ))}
            </div>
          ) : null}

          <div className="mt-4">
            {href ? (
              <Button asChild size="lg">
                <a href={href}>
                  继续学习
                  <ArrowRight className="size-4" aria-hidden="true" />
                </a>
              </Button>
            ) : (
              <p className="text-metadata text-text-secondary">暂时无法从这里直接打开这项学习。</p>
            )}
          </div>
        </div>
      </Panel>
    </section>
  );
}
