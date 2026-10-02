import { Link } from '@tanstack/react-router';
import { ArrowRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { PageHeader } from '@/components/page/page-header';
import { useDailyAgenda } from '@/features/home/agenda-api';
import {
  decisionBadges,
  decisionSentence,
  listRowDetail,
  localDeepLink,
  scopeLine,
  type AgendaItem,
} from '@/features/home/agenda-narrative';
import { formatDate } from '@/lib/format';
import { routePath } from '@/lib/router';
import { cn } from '@/lib/utils';
import { canonicalLanguage, programmingLanguages, type ProgrammingLanguageSlug } from '../programming-language';
import { legacyProgrammingTarget, type LegacyProgrammingTarget } from '../legacy-routes';
import { readProgrammingOnboarding } from '../programming-onboarding';
import { useProgrammingLanguage } from '../programming-context';
import {
  exerciseTotal,
  useProgrammingExercises,
  useProgrammingHome,
  useProgrammingOnboarding,
} from '../api/programming';

/** The programming space's own record namespace (`core.learning_context.ServiceNamespace`). */
const PROGRAMMING_NAMESPACE = 'programming';

/** Rows of 今天接下来 shown before the list is asked for the rest. */
const COLLAPSED_TASKS = 4;

const secondaryAction =
  'inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-4 text-body font-medium text-text-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/* ------------------------------------------------------------------ progress numbers */

/** One reading of `/programming/home`'s `stats`, with nothing invented for a value it omits. */
function statsOf(value: unknown): {
  streakDays: number | undefined;
  momentum: string | undefined;
  todayPractice: number | undefined;
  todaySubmissions: number | undefined;
  lastActivity: string | undefined;
} {
  const root = isRecord(value) ? value : {};
  const stats = isRecord(root.stats) ? root.stats : {};
  const number = (key: string): number | undefined => {
    const raw = stats[key];
    return typeof raw === 'number' && Number.isFinite(raw) ? raw : undefined;
  };
  const text = (key: string): string | undefined => {
    const raw = stats[key];
    return typeof raw === 'string' && raw.trim() ? raw : undefined;
  };
  return {
    streakDays: number('streak_days'),
    momentum: text('momentum'),
    todayPractice: number('today_practice_count'),
    todaySubmissions: number('today_submission_count'),
    lastActivity: text('last_activity_date'),
  };
}

/* ------------------------------------------------------------------ continuation */

/** When one exercise was last touched, read off the progress the exercise list carries. */
function lastTouched(exercise: unknown): number {
  if (!isRecord(exercise) || !isRecord(exercise.personal_progress)) return 0;
  const progress = exercise.personal_progress;
  for (const key of ['last_submit_at', 'last_test_at', 'last_run_at']) {
    const value = progress[key];
    if (typeof value === 'string') {
      const time = new Date(value).getTime();
      if (Number.isFinite(time)) return time;
    }
  }
  return 0;
}

/**
 * The most recent practice worth returning to: the one touched last, and among those the most
 * recent one that is not already passed. Nothing is invented — an exercise nobody has opened is
 * not "in progress", so a learner who has run nothing gets no continuation.
 */
function resumeTarget(exercises: readonly unknown[]): { id: number; title: string } | undefined {
  const touched = exercises
    .map((exercise) => ({ exercise, at: lastTouched(exercise) }))
    .filter((entry) => entry.at > 0)
    .sort((left, right) => right.at - left.at);
  const entry =
    touched.find(({ exercise }) => {
      const progress = isRecord(exercise) && isRecord(exercise.personal_progress) ? exercise.personal_progress : undefined;
      return progress?.last_submit_passed !== true;
    }) ?? touched[0];
  if (!entry) return undefined;
  const exercise = entry.exercise;
  const title = isRecord(exercise) && typeof exercise.title === 'string' ? exercise.title : undefined;
  const id = isRecord(exercise) && typeof exercise.id === 'number' ? exercise.id : undefined;
  if (!title || id === undefined) return undefined;
  return { id, title };
}

function exerciseItems(value: unknown): unknown[] {
  if (isRecord(value) && Array.isArray(value.items)) return value.items;
  return [];
}

/* ------------------------------------------------------------------ external destinations */

/**
 * A server-supplied deep link, as a destination this router can open without a page reload.
 *
 * The backend still builds programming links in the OLD shape — `/programming/Python/exercises/7`
 * — because the language used to be a path segment. `legacyProgrammingTarget` is the same mapping
 * the redirect route uses, so an agenda item opened from here is a client-side navigation instead
 * of a full reload, and both paths agree on where a link lands.
 */
function destination(deepLink: string): LegacyProgrammingTarget | undefined {
  const local = localDeepLink(deepLink);
  if (!local) return undefined;
  if (local.startsWith('/programming/')) {
    return legacyProgrammingTarget(local.slice('/programming/'.length));
  }
  return { to: local, search: {} };
}

/* ------------------------------------------------------------------ the page */

/**
 * 编程工作台 — the programming space's home.
 *
 * The page answers three questions in the order a learner asks them: what to do now (今日任务),
 * where I stand (学习进度), and where else I could go (学习方向 / 学习工具). It used to answer
 * none of them: it was a list of entry points — four languages, then the same four tools again
 * under a language, then three cards repeating them — so the first screen named the doors without
 * ever naming the work. A learner had to open a language and then a题 to find the first thing to do.
 *
 * 今日任务 leads and carries the ONE filled action on the page. It comes from the same ranked
 * agenda the personal home reads, narrowed to this space's own rows, so a task is stated here in
 * the words its own facts support — never a reassembled payload. When the agenda holds nothing
 * for programming the page falls back to the exercise last worked on, which is a stored fact and
 * not a recommendation; when there is neither, it says so rather than filling the space.
 *
 * The language is a 学习方向 here, not a navigation level: 学习方向 lists the four, 学习工具 opens
 * the four tools, and both carry the current language as context.
 */
export function ProgrammingWorkbenchPage() {
  const onboarding = useProgrammingOnboarding();
  const declared = readProgrammingOnboarding(onboarding.data);
  const unconfigured = !onboarding.isPending && !onboarding.isError && !declared.completed;
  const { language } = useProgrammingLanguage();
  const canonical = language ? canonicalLanguage(language) : undefined;

  const exercises = useProgrammingExercises(language ?? '');
  const resume = resumeTarget(exerciseItems(exercises.data));
  const bankSize = exerciseTotal(exercises.data);
  const home = useProgrammingHome();
  const stats = statsOf(home.data);

  const agenda = useDailyAgenda();
  const tasks = (agenda.data?.items ?? []).filter(
    (item) => item.service_namespace === PROGRAMMING_NAMESPACE,
  );

  // The focal item is the agenda's own first row; the resume target is only the stand-in when the
  // agenda has nothing to say about this space. Exactly one of them is ever the primary action.
  const focus: AgendaItem | undefined = tasks[0];
  const rest = tasks.slice(1);
  const toolSearch = language ? { language } : {};

  return (
    <div className="space-accent space-accent--programming mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="编程学习"
        title="编程工作台"
        description="今天要做什么、练到哪了、语言和工具在哪里——都在这一页。"
        actions={
          <Link to="/programming/setup" search={{ returnTo: '/programming' }} className={secondaryAction}>
            学习设置
          </Link>
        }
      />

      {unconfigured ? (
        <StatusNote className="mt-8">
          还没有声明练习语言与当前水平，学习进度与计划因此不会有内容。{' '}
          <Link
            to="/programming/setup"
            search={{ returnTo: '/programming' }}
            className="text-primary-ink underline hover:text-primary-hover"
          >
            设置编程学习
          </Link>{' '}
          后即可继续；下面的语言与工具仍然可以直接使用。
        </StatusNote>
      ) : null}

      {/* ---------------------------------------------------------------- 今日任务 */}
      <section className="mt-10" aria-labelledby="programming-today-title">
        <SectionHeading
          id="programming-today-title"
          title="今日任务"
          description="按已记录的学习情况排序；今天没有待处理项时，会显示上次停下的练习。"
        />

        {agenda.isPending ? (
          <Panel tone="focus" className="mt-4">
            <div aria-hidden="true">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="mt-2 h-6 w-72 max-w-full" />
              <Skeleton className="mt-3 h-4 w-full" />
              <Skeleton className="mt-4 h-12 w-32" />
            </div>
            <p role="status" className="sr-only">
              正在读取今天的学习任务…
            </p>
          </Panel>
        ) : agenda.isError ? (
          <StatusNote tone="danger" className="mt-4">
            今天的学习任务暂时读不到。下面的学习方向与工具仍然可以继续使用。
          </StatusNote>
        ) : focus ? (
          <>
            <Panel tone="focus" className="mt-4">
              <p className="text-metadata text-text-secondary">{scopeLine(focus)}</p>
              <h3 className="mt-1.5 text-section-title font-semibold text-text-primary wrap-anywhere">
                {focus.title}
              </h3>
              {decisionSentence(focus) ? (
                <p className="mt-2 max-w-prose text-body text-text-primary">{decisionSentence(focus)}</p>
              ) : null}
              {decisionBadges(focus).length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {decisionBadges(focus).map((badge) => (
                    <Badge key={badge} tone="brand">
                      {badge}
                    </Badge>
                  ))}
                </div>
              ) : null}
              <div className="mt-5">
                <FocusAction item={focus} />
              </div>
            </Panel>

            {rest.length ? (
              <ol className="programming-today__list mt-2">
                {rest.slice(0, COLLAPSED_TASKS).map((item) => (
                  <li key={`${item.source_type}-${item.source_id}`} className="programming-today__row">
                    <span className="min-w-0 flex-1">
                      <span className="block text-body font-medium text-text-primary wrap-anywhere">
                        {item.title}
                      </span>
                      {listRowDetail(item) ? (
                        <span className="mt-0.5 block text-metadata text-text-secondary wrap-anywhere">
                          {listRowDetail(item)}
                        </span>
                      ) : null}
                    </span>
                    <ArrowRight className="mt-1 size-4 shrink-0 text-text-muted" aria-hidden="true" />
                  </li>
                ))}
              </ol>
            ) : null}
          </>
        ) : resume && language ? (
          <Panel tone="focus" className="mt-4">
            <p className="text-metadata text-text-secondary">继续上次的练习</p>
            <h3 className="mt-1.5 text-section-title font-semibold text-text-primary wrap-anywhere">
              {resume.title}
            </h3>
            <p className="mt-2 max-w-prose text-body text-text-primary">
              这道练习上次还没有通过，接着把它做完。
            </p>
            <div className="mt-5">
              <Button asChild size="lg">
                <Link
                  to="/programming/workbench/$exerciseId"
                  params={{ exerciseId: String(resume.id) }}
                  search={{ language }}
                >
                  打开练习
                  <ArrowRight className="size-4" aria-hidden="true" />
                </Link>
              </Button>
            </div>
          </Panel>
        ) : (
          <EmptyState
            className="mt-4"
            title="今天暂时没有需要处理的编程任务。"
            description="从下面选一门语言开始练习；第一次运行或提交之后，这里会出现下一次要做的事。"
          />
        )}
      </section>

      {/* ---------------------------------------------------------------- 学习进度 */}
      <section className="mt-12" aria-labelledby="programming-progress-title">
        <SectionHeading id="programming-progress-title" title="学习进度" description={stats.momentum} />
        {home.isPending ? (
          <div className="programming-progress" aria-hidden="true">
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-20" />
          </div>
        ) : home.isError ? (
          <StatusNote tone="warning" className="mt-4">
            学习进度暂时读不到；这不影响练习、运行与提交。
          </StatusNote>
        ) : (
          <dl className="programming-progress">
            <ProgressItem
              label="连续学习"
              value={stats.streakDays !== undefined && stats.streakDays > 0 ? `${stats.streakDays} 天` : undefined}
            />
            <ProgressItem
              label="今日练习"
              value={stats.todayPractice !== undefined ? `${stats.todayPractice} 次` : undefined}
            />
            <ProgressItem
              label="今日提交"
              value={stats.todaySubmissions !== undefined ? `${stats.todaySubmissions} 次` : undefined}
            />
            <ProgressItem label="最近一次学习" value={formatDate(stats.lastActivity) || undefined} />
            {canonical && bankSize !== undefined ? (
              <ProgressItem label={`${canonical} 题库`} value={`${bankSize} 道`} />
            ) : null}
          </dl>
        )}
      </section>

      {/* ---------------------------------------------------------------- 学习方向 */}
      <section className="mt-12" aria-labelledby="programming-directions-title">
        <SectionHeading
          id="programming-directions-title"
          title="学习方向"
          description="编程按语言进行；练习、运行与记录都发生在具体一门语言下。"
        />
        <ul className="programming-directions">
          {orderedLanguages(declared.languages).map(({ slug, label, declared: isDeclared }) => (
            <li key={slug}>
              <Link
                to="/programming/practice"
                search={{ language: slug }}
                className={cn('programming-direction', isDeclared && 'programming-direction--current')}
              >
                <p className="programming-direction__name">{label}</p>
                {isDeclared ? <p className="programming-direction__note">你设置的语言</p> : null}
                <span className="programming-direction__go">进入练习</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      {/* ---------------------------------------------------------------- 学习工具 */}
      <section className="mt-12" aria-labelledby="programming-tools-title">
        <SectionHeading
          id="programming-tools-title"
          title="学习工具"
          description={canonical ? `下面四项都在 ${canonical} 下打开。` : '选好语言后，下面四项都会在它的上下文里打开。'}
        />
        <ul className="programming-tools">
          {TOOLS.map((tool) => (
            <li key={tool.to}>
              <Link to={routePath(tool.to)} search={toolSearch} className="programming-tool">
                <span className="programming-tool__name">{tool.name}</span>
                <span className="programming-tool__note">{tool.note}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** The declared language first, then the rest in the product's own order. */
function orderedLanguages(
  declared: readonly string[],
): Array<{ slug: ProgrammingLanguageSlug; label: string; declared: boolean }> {
  const entries = (Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, string]>).map(
    ([slug, label]) => ({ slug, label, declared: declared.includes(label) }),
  );
  return [...entries.filter((entry) => entry.declared), ...entries.filter((entry) => !entry.declared)];
}

function ProgressItem({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <dt className="programming-progress__label">{label}</dt>
      <dd className="programming-progress__value">{value ?? '—'}</dd>
    </div>
  );
}

const TOOLS: readonly { to: string; name: string; note: string }[] = [
  { to: '/programming/practice', name: '练习中心', note: '题库、推荐练习，以及写代码、运行与提交的 Workbench。' },
  { to: '/programming/ai', name: 'AI 编程助手', note: '围绕当前语言提问，可以带上你正在写的代码。' },
  { to: '/programming/records', name: '成长记录', note: '运行、测试、提交与复习的真实记录，以及已记下的学习状态。' },
  { to: '/programming/plan', name: '计划', note: '学习计划与调整建议；调整需要你确认后才会生效。' },
];

/** The focal item's one way in — the page's single filled action. */
function FocusAction({ item }: { item: AgendaItem }) {
  const target = destination(item.deep_link);
  if (!target) {
    return <p className="text-metadata text-text-secondary">暂时无法从这里直接打开这项学习。</p>;
  }
  return (
    <Button asChild size="lg">
      <Link to={routePath(target.to)} params={target.params} search={target.search}>
        继续学习
        <ArrowRight className="size-4" aria-hidden="true" />
      </Link>
    </Button>
  );
}
