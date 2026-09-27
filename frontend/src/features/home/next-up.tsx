import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { useDailyAgenda } from './agenda-api';
import { listRowDetail, localDeepLink, type AgendaItem } from './agenda-narrative';

/** Rows shown before the list has to be asked for the rest. */
const COLLAPSED_ROWS = 3;

/**
 * What makes two rendered rows "the same row" for the duplicate check: the title together with
 * the line under it. A tab separates the two parts because a title cannot contain one, so two
 * rows whose text differs only in where the boundary falls cannot collapse into one key.
 */
function rowIdentity(item: AgendaItem, detail: string | null): string {
  return `${item.title}\t${detail ?? ''}`;
}

/**
 * The rest of the server's agenda, in the server's order.
 *
 * Home promotes the first entry to the focal card above, so this list begins at the second: the
 * same task is never shown twice. It is deliberately the cheapest possible rendering — a title,
 * the direction it belongs to, and where it goes. The evidence behind a suggestion is what a
 * learner reads when they doubt it, and the focal card already offers exactly that; repeating it
 * on every row is what made this page read as a log instead of a plan.
 *
 * The section carries no link of its own: 学习报告 is a destination in the header, on every
 * screen, and a second copy of it here competed with the tasks it sat beside.
 */
export function NextUp({ courseNames }: { courseNames?: ReadonlyMap<string, string> }) {
  const agenda = useDailyAgenda();
  const [expanded, setExpanded] = useState(false);

  if (agenda.isPending) {
    return (
      <section aria-labelledby="next-up-title" className="mt-10">
        <SectionHeading id="next-up-title" title="今天接下来" />
        <div className="mt-4 space-y-3" aria-hidden="true">
          <Skeleton className="h-5 w-56" />
          <Skeleton className="h-5 w-64" />
        </div>
        <p role="status" className="sr-only">
          正在读取今天的其他任务…
        </p>
      </section>
    );
  }

  if (agenda.isError) {
    return (
      <section aria-labelledby="next-up-title" className="mt-10">
        <SectionHeading id="next-up-title" title="今天接下来" />
        <StatusNote tone="danger" className="mt-4">
          今天的学习任务暂时无法加载。
        </StatusNote>
      </section>
    );
  }

  const all = agenda.data.items ?? [];
  const rest = all.slice(1);
  if (rest.length === 0) return null;

  const visible = expanded ? rest : rest.slice(0, COLLAPSED_ROWS);
  const hidden = rest.length - visible.length;

  // Two exercises can carry the same title in the same direction. The backend keys them by
  // exercise, so the row has to say which one it means — otherwise a learner reads a duplicate
  // task where there are two different ones.
  const details = visible.map((item) => listRowDetail(item, courseNames));
  const seen = new Map<string, number>();
  for (const [index, item] of visible.entries()) {
    const key = rowIdentity(item, details[index] ?? null);
    seen.set(key, (seen.get(key) ?? 0) + 1);
  }

  return (
    <section aria-labelledby="next-up-title" className="mt-10">
      <SectionHeading id="next-up-title" title="今天接下来" />

      <ol className="mt-4">
        {visible.map((item, index) => {
          const detail = details[index] ?? null;
          const duplicated = (seen.get(rowIdentity(item, detail)) ?? 0) > 1;
          return (
            <NextUpRow
              key={`${item.source_type}-${item.source_id}`}
              item={item}
              rank={index + 2}
              detail={duplicated ? [detail, `#${item.source_id}`].filter(Boolean).join(' · ') : detail}
            />
          );
        })}
      </ol>

      {hidden > 0 ? (
        <Button variant="ghost" size="sm" className="mt-3" onClick={() => setExpanded(true)}>
          还有 {hidden} 项
        </Button>
      ) : null}
    </section>
  );
}

function NextUpRow({
  item,
  rank,
  detail,
}: {
  item: AgendaItem;
  rank: number;
  detail: string | null;
}) {
  const href = localDeepLink(item.deep_link);
  const body = (
    <>
      <span className="w-6 shrink-0 pt-0.5 text-metadata tabular-nums text-text-muted">
        {String(rank).padStart(2, '0')}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium text-text-primary wrap-anywhere">{item.title}</span>
        {detail ? (
          <span className="mt-0.5 block text-metadata text-text-secondary wrap-anywhere">
            {detail}
          </span>
        ) : null}
      </span>
      <ArrowRight className="mt-0.5 size-4 shrink-0 text-text-muted" aria-hidden="true" />
    </>
  );

  return (
    <li className="border-t border-border-default first:border-t-0">
      {href ? (
        <a
          href={href}
          className="flex min-h-14 items-start gap-3 py-3 transition-colors hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          {body}
        </a>
      ) : (
        <div className="flex min-h-14 items-start gap-3 py-3 text-text-secondary">
          <span className="w-6 shrink-0 pt-0.5 text-metadata tabular-nums text-text-muted">
            {String(rank).padStart(2, '0')}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-medium text-text-primary wrap-anywhere">{item.title}</span>
            <span className="mt-0.5 block text-metadata text-text-secondary">
              暂时无法从这里直接打开。
            </span>
          </span>
        </div>
      )}
    </li>
  );
}
