import type { components } from '@/types/api';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { FactList } from '@/components/page/fact-list';
import { Panel } from '@/components/ui/panel';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { serviceNamespaceLabel } from '@/features/records/event-labels';
import { REASON_UNAVAILABLE } from '@/lib/learner-safe';
import { useAgendaExplain, useDailyAgenda } from './agenda-api';

/**
 * The learner-meaningful facts behind a task, and nothing else.
 *
 * The agenda's `facts` object is assembled from three different sources, so its shape varies with
 * the kind of item. It is read through an allow-list rather than rendered wholesale: a field the
 * product has not decided how to say is not shown, and the item's internal references stay in the
 * payload. What remains is what a learner can act on — how many times they got it wrong, when
 * they last tried it, whether it is overdue.
 */
const AGENDA_FACT_FIELDS = [
  'status',
  'due_date',
  'task_type',
  'wrong_count',
  'attempts',
  'factual_correct',
  'factual_incorrect',
  'active_wrong_count',
  'last_attempt_at',
  'due_source',
] as const;

function AgendaFacts({ value }: { value: Record<string, unknown> | undefined }) {
  if (!value) return null;
  return <FactList className="mt-3" value={value} columns={1} allow={AGENDA_FACT_FIELDS} />;
}

/**
 * The rule behind a reason code, taken from the server's own `priority_rules` map rather than
 * from a list repeated here. A locally repeated list drifts silently, and a drifting list is
 * exactly how a learner ends up reading a raw code such as `repeated_wrong` on screen.
 *
 * A reason the server does not name is not shown as a code either — the explanation entry says
 * the product cannot state the basis yet. Naming the code would be a worse answer than admitting
 * there is none: `unseen_coverage` is the server's word, not the learner's.
 */
function ruleFor(contract: Record<string, unknown> | undefined, reason: string) {
  const rules = contract?.priority_rules;
  if (!rules || typeof rules !== 'object') return REASON_UNAVAILABLE;
  const rule = (rules as Record<string, unknown>)[reason];
  return typeof rule === 'string' && rule.trim() ? rule : REASON_UNAVAILABLE;
}

function localDeepLink(deepLink: string) {
  return deepLink.startsWith('/') ? deepLink : undefined;
}

function dueText(dueAt: string | null | undefined) {
  return dueAt ? `截止 / 到期：${new Date(dueAt).toLocaleString('zh-CN')}` : null;
}

/**
 * The server's own first item, promoted to the page's single focal action.
 *
 * The agenda arrives already ranked by the backend's fixed priority ladder. Home shows its first
 * entry here — at full weight, with the reason the server gives for putting it first — and the
 * list below continues from the second entry. Nothing is re-sorted and nothing is dropped: the
 * page reads "this one, then these".
 *
 * It renders nothing when the agenda is empty or unreadable, because the agenda section owns that
 * message; two empty panels saying the same thing would be noise, not honesty.
 */
export function AgendaFocus() {
  const agenda = useDailyAgenda();
  const explain = useAgendaExplain();

  if (agenda.isPending) {
    return (
      <div className="rounded-card border border-focus-border bg-focus-surface p-5 sm:p-6" aria-hidden="true">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="mt-3 h-6 w-64 max-w-full" />
        <Skeleton className="mt-4 h-4 w-full" />
        <Skeleton className="mt-2 h-4 w-3/4" />
        <Skeleton className="mt-6 h-11 w-44" />
      </div>
    );
  }

  if (agenda.isError) return null;

  const item = (agenda.data.items ?? [])[0];
  if (!item) return null;

  const href = localDeepLink(item.deep_link);
  const rule = ruleFor(explain.data, item.priority_reason);
  const due = dueText(item.due_at);

  return (
    <Panel tone="focus" labelledBy="agenda-focus-title">
      <p className="text-metadata font-medium tracking-eyebrow text-primary-ink">当前重点</p>
      <h2 id="agenda-focus-title" className="mt-2 text-section-title font-semibold text-text-primary">
        {item.title}
      </h2>
      <p className="mt-2 text-metadata text-text-secondary">
        {serviceNamespaceLabel(item.service_namespace)}
        {due ? ` · ${due}` : ''}
      </p>
      <p className="mt-4 max-w-prose text-body text-text-primary">{item.summary}</p>

      <details className="mt-4">
        <summary className="text-body text-text-secondary">为什么现在做这件事</summary>
        <p className="mt-2 text-body text-text-primary">{rule}</p>
        <AgendaFacts value={item.facts} />
        <p className="mt-2 text-metadata text-text-secondary">
          完成什么动作后它会改变：
          {item.resolved_by ?? '在对应学习页面完成此项真实动作后，系统会按最新学习事实重新计算。'}
        </p>
      </details>

      {href ? (
        <Button asChild size="lg" className="mt-6">
          <a href={href}>打开并完成这项学习</a>
        </Button>
      ) : (
        <p className="mt-6 text-metadata text-text-secondary">暂时无法从这里直接打开这项学习。</p>
      )}
    </Panel>
  );
}

function AgendaItem({
  item,
  explain,
}: {
  item: components['schemas']['AgendaItemView'];
  explain?: Record<string, unknown>;
}) {
  const href = localDeepLink(item.deep_link);
  const rule = ruleFor(explain, item.priority_reason);
  const due = dueText(item.due_at);
  return (
    <li className="border-l-2 border-border-default pl-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="font-medium text-text-primary">{item.title}</p>
        <p className="text-metadata text-text-secondary">
          {serviceNamespaceLabel(item.service_namespace)}
        </p>
      </div>
      <p className="mt-1 text-body text-text-secondary">{item.summary}</p>
      {due ? <p className="mt-2 text-metadata text-text-secondary">{due}</p> : null}
      <details className="mt-3">
        <summary className="text-body text-text-secondary">为什么现在做这件事</summary>
        <p className="mt-2 text-body text-text-primary">{rule}</p>
        <AgendaFacts value={item.facts} />
        <p className="mt-2 text-metadata text-text-secondary">
          完成什么动作后它会改变：
          {item.resolved_by ?? '在对应学习页面完成此项真实动作后，系统会按最新学习事实重新计算。'}
        </p>
      </details>
      {href ? (
        <a className="mt-3 inline-block text-body text-primary-ink hover:text-primary-hover" href={href}>
          打开并完成这项学习
        </a>
      ) : (
        <p className="mt-3 text-metadata text-text-secondary">暂时无法从这里直接打开这项学习。</p>
      )}
    </li>
  );
}

/**
 * The rest of the server's agenda, in the order the server returned it.
 *
 * `skipFirstItem` is set by Home, where the first entry was already given the page's focal
 * treatment above; rendering it twice would make the same task look like two.
 */
export function DailyAgenda({ skipFirstItem = false }: { skipFirstItem?: boolean }) {
  const agenda = useDailyAgenda();
  const explain = useAgendaExplain();

  if (agenda.isPending) {
    return (
      <section aria-labelledby="daily-agenda-title">
        <SectionHeading id="daily-agenda-title" eyebrow="今日议程" title="今天接下来学什么" />
        <div className="mt-6 space-y-3" aria-hidden="true">
          <Skeleton className="h-5 w-56" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <p role="status" className="sr-only">
          正在读取今天的学习任务…
        </p>
      </section>
    );
  }

  if (agenda.isError) {
    return (
      <section aria-labelledby="daily-agenda-title">
        <SectionHeading id="daily-agenda-title" eyebrow="今日议程" title="今天接下来学什么" />
        <StatusNote tone="danger" className="mt-6">
          今日任务暂时无法加载。
        </StatusNote>
      </section>
    );
  }

  const all = agenda.data.items ?? [];
  const items = skipFirstItem ? all.slice(1) : all;

  return (
    <section aria-labelledby="daily-agenda-title">
      <SectionHeading
        id="daily-agenda-title"
        eyebrow="今日议程"
        title="今天接下来学什么"
        description="顺序由学习系统的服务端策略给出；完成真实学习动作后会按新事实重新计算。"
      />

      {all.length === 0 ? (
        <EmptyState
          className="mt-6"
          title="当前没有需要优先处理的学习任务。"
          description="当你安排复习、加入计划任务或开始练习后，这里会按服务端策略给出下一件事。"
        />
      ) : items.length === 0 ? (
        <EmptyState
          className="mt-6"
          title="服务端没有排定其他优先任务。"
          description="上面那一项就是现在最该完成的事；完成后它会重新计算，新的任务会出现在这里。"
        />
      ) : (
        <ol className="mt-6 space-y-6">
          {items.map((item) => (
            <AgendaItem
              key={`${item.source_type}-${item.source_id}`}
              item={item}
              explain={explain.data}
            />
          ))}
        </ol>
      )}
    </section>
  );
}
