import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { ChevronRight, Circle, CircleCheck, CircleDot, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { StatusNote } from '@/components/ui/status-note';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { AssistantMarkdown } from '@/features/ai/components/assistant-markdown';
import { serverMessage } from '@/lib/api/server-message';
import { cn } from '@/lib/utils';
import { ApiRequestError } from '@/features/exam/api/content-status';
import {
  KNOWLEDGE_STATUSES,
  isKnowledgeStatus,
  knowledgeStatusLabel,
  useCourseKnowledge,
  useCourseKnowledgePointStudyContent,
  useCourseKnowledgeStructure,
  useGenerateCourseKnowledgePointStudyContent,
  useUpdateKnowledgePointStatus,
  type KnowledgeStatus,
} from '@/features/course/api/course';
import { CoursePageShell } from './course-page-shell';

/* ------------------------------------------------------------------ grammar */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function list(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (isRecord(value)) {
    for (const key of ['items', 'data', 'records']) {
      if (Array.isArray(value[key])) return value[key] as unknown[];
    }
  }
  return [];
}

function text(value: unknown, key: string): string | undefined {
  return isRecord(value) && typeof value[key] === 'string' && value[key] ? value[key] : undefined;
}

function numberAt(value: unknown, key: string): number | undefined {
  return isRecord(value) && typeof value[key] === 'number' ? value[key] : undefined;
}

/* ------------------------------------------------------------------ the structure as a navigation */

/**
 * One outline, read from the ACTIVE version and nothing else.
 *
 * The points arrive as one ordered list whose chapters are their `parent_id`; grouping them here
 * keeps that single read as the page's only source. A point whose chapter is missing is NOT
 * dropped — it is shown at the top level, because a point that silently disappears from the
 * outline is indistinguishable from a point that was never in the structure.
 */
export type StudyPoint = {
  id: number;
  title: string;
  chapterId: number | null;
  chapterTitle: string;
  status: KnowledgeStatus;
};

export type StudyOutline = {
  chapters: { id: number; title: string; points: StudyPoint[] }[];
  /** Top-level points that carry no children — a legacy flat structure, rendered as its own list. */
  loose: StudyPoint[];
  /** Every selectable point, in the order the outline shows them. */
  ordered: StudyPoint[];
};

export function readOutline(value: unknown): StudyOutline {
  const rows = isRecord(value) && Array.isArray(value.knowledge_points)
    ? value.knowledge_points
    : list(value);

  type Raw = { id: number; parentId: number | null; title: string; status: KnowledgeStatus };
  const raws: Raw[] = [];
  for (const row of rows) {
    const id = numberAt(row, 'id');
    const title = text(row, 'title');
    if (id === undefined || !title) continue;
    const parent = numberAt(row, 'parent_id');
    const status = text(row, 'status');
    raws.push({
      id,
      parentId: parent ?? null,
      title,
      status: isKnowledgeStatus(status) ? status : 'not_started',
    });
  }

  const childrenOf = new Map<number, Raw[]>();
  for (const row of raws) {
    if (row.parentId === null) continue;
    const bucket = childrenOf.get(row.parentId) ?? [];
    bucket.push(row);
    childrenOf.set(row.parentId, bucket);
  }

  const chapterIds = new Set(raws.filter((row) => row.parentId === null).map((row) => row.id));
  const chapters: StudyOutline['chapters'] = [];
  const loose: StudyPoint[] = [];
  const ordered: StudyPoint[] = [];

  for (const row of raws.filter((entry) => entry.parentId === null)) {
    const children = childrenOf.get(row.id) ?? [];
    if (!children.length) {
      const point: StudyPoint = { id: row.id, title: row.title, chapterId: null,
                                  chapterTitle: '', status: row.status };
      loose.push(point);
      ordered.push(point);
      continue;
    }
    const points = children.map((child) => ({
      id: child.id,
      title: child.title,
      chapterId: row.id,
      chapterTitle: row.title,
      status: child.status,
    }));
    chapters.push({ id: row.id, title: row.title, points });
    ordered.push(...points);
  }

  // A point whose chapter is not in this structure at all. It is still this learner's point, so
  // it is listed rather than dropped.
  const orphans = raws.filter((row) => row.parentId !== null && !chapterIds.has(row.parentId));
  if (orphans.length) {
    const points = orphans.map((row) => ({
      id: row.id, title: row.title, chapterId: null, chapterTitle: '', status: row.status,
    }));
    chapters.push({ id: -1, title: '未归入章节', points });
    ordered.push(...points);
  }

  return { chapters, loose, ordered };
}

/**
 * Which point the page opens on, in the order the learner's own situation decides it.
 *
 * Nothing here writes a state — it only chooses what to show. A point the learner is already in
 * the middle of beats one they finished and have not reviewed; both beat the first point of the
 * course, which is where a page with nothing else to go on starts.
 */
export function defaultPointId(outline: StudyOutline, fromUrl?: number): number | undefined {
  if (fromUrl !== undefined && outline.ordered.some((point) => point.id === fromUrl)) return fromUrl;
  return (
    outline.ordered.find((point) => point.status === 'learning')?.id
    ?? outline.ordered.find((point) => point.status === 'review_due')?.id
    ?? outline.ordered[0]?.id
  );
}

/* ------------------------------------------------------------------ status */

const STATUS_ICONS: Record<KnowledgeStatus, typeof Circle> = {
  not_started: Circle,
  learning: CircleDot,
  mastered: CircleCheck,
  review_due: RotateCcw,
};

/**
 * The state of a point, as a shape first and a colour second.
 *
 * The four marks are the four states and nothing else — no score, no percentage, no progress
 * bar. What the learner has actually recorded is one of four things, and showing it as a fifth
 * number would be inventing a precision the record does not carry.
 */
function StatusMark({ status }: { status: KnowledgeStatus }) {
  const Icon = STATUS_ICONS[status];
  return (
    <span className="inline-flex items-center gap-1">
      {/* The word is the accessible half: the shapes differ, but two of them are round, and a
          reader who cannot see the mark at all still needs to know the state. */}
      <Icon
        className={cn('size-4 shrink-0', status === 'not_started' ? 'text-text-muted' : 'text-primary')}
        aria-hidden="true"
      />
      <span className="sr-only">{knowledgeStatusLabel(status)}</span>
    </span>
  );
}

/**
 * The learner's own answer to "where am I on this point".
 *
 * Four buttons rather than a menu: the four states are the whole vocabulary, they fit on one
 * line, and a learner changing their mind should be able to see the other three without opening
 * anything. Reading the explanation never touches this — only pressing one of these does.
 */
function StatusControl({
  status,
  pending,
  onChange,
}: {
  status: KnowledgeStatus;
  pending: boolean;
  onChange: (next: KnowledgeStatus) => void;
}) {
  return (
    <fieldset className="flex flex-wrap items-center gap-2">
      <legend className="sr-only">这个知识点的学习状态</legend>
      {KNOWLEDGE_STATUSES.map((option) => {
        const Icon = STATUS_ICONS[option];
        const active = option === status;
        return (
          <button
            key={option}
            type="button"
            aria-pressed={active}
            disabled={pending}
            onClick={() => { if (!active) onChange(option); }}
            className={cn(
              'inline-flex h-9 items-center gap-1.5 rounded-control px-3 text-metadata transition-colors duration-fast ease-standard',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
              'disabled:opacity-50',
              active
                ? 'bg-primary-soft font-medium text-primary-ink'
                : 'border border-border-default text-text-secondary hover:bg-primary-soft',
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {knowledgeStatusLabel(option)}
          </button>
        );
      })}
    </fieldset>
  );
}

function Failure({ title, error, retry }: { title: string; error: unknown; retry?: () => void }) {
  const message = error instanceof ApiRequestError ? serverMessage(error.detail) : null;
  return (
    <StatusNote tone="danger" className="mt-6">
      {title}
      {message ? <span className="ml-1">{message}</span> : null}
      {retry ? (
        <button type="button" className="ml-3 underline" onClick={retry}>
          重试
        </button>
      ) : null}
    </StatusNote>
  );
}

/** A failed explanation, said in terms the learner can act on. */
function generationFailure(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.status === 403) return '这个能力需要升级后使用。';
    if (error.status === 429) return '本次额度不足，没有生成学习内容。';
    const message = serverMessage(error.detail);
    if (message) return message;
  }
  return '学习内容没有生成，请稍后重试。';
}

/* ------------------------------------------------------------------ the outline */

function OutlineNav({
  outline,
  selectedId,
  collapsed,
  onToggleChapter,
  onSelect,
}: {
  outline: StudyOutline;
  selectedId: number | undefined;
  collapsed: ReadonlySet<number>;
  onToggleChapter: (chapterId: number) => void;
  onSelect: (pointId: number) => void;
}) {
  const pointRow = (point: StudyPoint) => (
    <li key={point.id}>
      <button
        type="button"
        aria-current={point.id === selectedId ? 'true' : undefined}
        onClick={() => onSelect(point.id)}
        className={cn(
          'flex w-full items-center gap-2 rounded-control px-3 py-2 text-left text-body transition-colors duration-fast ease-standard',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
          point.id === selectedId
            ? 'bg-primary-soft font-medium text-primary-ink'
            : 'text-text-primary hover:bg-primary-soft',
        )}
      >
        <StatusMark status={point.status} />
        <span className="min-w-0 flex-1">{point.title}</span>
      </button>
    </li>
  );

  return (
    // One nav landmark for the outline; the point being studied is its sibling, so a screen
    // reader can jump straight past the outline to the content.
    <nav aria-label="知识点">
      {outline.chapters.length ? (
        <ul className="space-y-1">
          {outline.chapters.map((chapter) => {
            const open = !collapsed.has(chapter.id);
            return (
              <li key={chapter.id}>
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() => onToggleChapter(chapter.id)}
                  className="flex w-full items-center gap-1.5 rounded-control px-2 py-2 text-left text-metadata font-medium text-text-secondary hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                >
                  <ChevronRight
                    className={cn('size-4 shrink-0 transition-transform duration-fast ease-standard',
                                  open && 'rotate-90')}
                    aria-hidden="true"
                  />
                  <span className="min-w-0 flex-1">{chapter.title}</span>
                  <span className="shrink-0 tabular-nums text-text-muted">{chapter.points.length}</span>
                </button>
                {open ? <ul className="mt-0.5">{chapter.points.map(pointRow)}</ul> : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {/* Points that belong to no chapter — a legacy flat structure. Rendered in the same shape,
          because they are the same kind of thing to the learner. */}
      {outline.loose.length ? (
        <ul className="mt-1 space-y-1">{outline.loose.map(pointRow)}</ul>
      ) : null}
    </nav>
  );
}

/* ------------------------------------------------------------------ one point, being studied */

function StudyWorkspace({
  courseId,
  point,
  status,
  statusPending,
  onStatusChange,
}: {
  courseId: string;
  point: StudyPoint;
  status: KnowledgeStatus;
  statusPending: boolean;
  onStatusChange: (next: KnowledgeStatus) => void;
}) {
  const content = useCourseKnowledgePointStudyContent(courseId, point.id);
  const generate = useGenerateCourseKnowledgePointStudyContent(courseId);

  // A stored or freshly generated explanation belongs to ONE point, and is only shown under that
  // one: a result for a point the learner has stepped away from must never appear under the point
  // they are now reading.
  const generating = generate.isPending;
  const generated = generate.data?.knowledgePointId === point.id ? generate.data : null;
  const stored = content.data?.knowledgePointId === point.id ? content.data : null;
  const body = generated ?? stored;

  return (
    <article aria-labelledby="study-point-title">
      <div className="border-b border-border-default pb-4">
        {point.chapterTitle ? (
          <p className="text-metadata text-text-muted">{point.chapterTitle}</p>
        ) : null}
        <h2 id="study-point-title" className="mt-1 text-section-title font-semibold text-text-primary">
          {point.title}
        </h2>
        <div className="mt-4">
          <StatusControl status={status} pending={statusPending} onChange={onStatusChange} />
        </div>
      </div>

      <section className="mt-8" aria-labelledby="study-content-title">
        <h3 id="study-content-title" className="text-heading font-semibold text-text-primary">
          学习内容
        </h3>

        {generate.isError ? (
          <StatusNote tone="danger" className="mt-4">{generationFailure(generate.error)}</StatusNote>
        ) : null}

        {generating ? (
          <LoadingState label="正在生成学习内容…" className="mt-4" rows={4} />
        ) : body ? (
          <div className="mt-4 max-w-prose text-body leading-relaxed text-text-primary">
            <AssistantMarkdown content={body.content} />
          </div>
        ) : content.isPending ? (
          <LoadingState label="正在读取学习内容…" className="mt-4" />
        ) : content.isError ? (
          <Failure title="学习内容暂时无法读取。" error={content.error} retry={() => void content.refetch()} />
        ) : (
          <>
            <p className="mt-4 max-w-prose text-body text-text-secondary">
              这里会讲解这个知识点，并优先结合你这门课的资料。
            </p>
            <Button
              size="lg"
              className="mt-4"
              disabled={generating}
              onClick={() => generate.mutate({ pointId: point.id })}
            >
              开始学习
            </Button>
          </>
        )}
      </section>

      {/* Only real grounding is shown. No file was read for this explanation, so no file is
          named — an empty "关联资料" heading would claim a relation that does not exist. */}
      {body?.citations.length ? (
        <section className="mt-8" aria-labelledby="study-materials-title">
          <h3 id="study-materials-title" className="text-heading font-semibold text-text-primary">
            关联资料
          </h3>
          <ul className="mt-3 border-t border-border-default">
            {body.citations.map((citation) => (
              <li key={citation.filename} className="border-b border-border-default py-3">
                <p className="text-body font-medium text-text-primary">{citation.filename}</p>
                {citation.snippet ? (
                  <p className="mt-1 line-clamp-2 text-metadata text-text-secondary">{citation.snippet}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="mt-10 flex flex-wrap gap-3 border-t border-border-default pt-6">
        <Link
          to="/course/$courseId/practice"
          params={{ courseId }}
          search={{ chapter: point.chapterTitle || undefined }}
          className="inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover"
        >
          开始练习
        </Link>
        <Link
          to="/course/$courseId/ask"
          params={{ courseId }}
          search={{ knowledge_point_id: point.id, knowledge_point_title: point.title }}
          className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft"
        >
          围绕此知识点问 AI
        </Link>
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ the page */

export function CourseStudyPage({
  courseId,
  selectedPointId,
}: {
  courseId: string;
  /** The point named in the URL, when the learner (or a link) named one. */
  selectedPointId?: number;
}) {
  const points = useCourseKnowledge(courseId);
  const structure = useCourseKnowledgeStructure(courseId);
  const updateStatus = useUpdateKnowledgePointStatus(courseId);
  const navigate = useNavigate();

  const outline = useMemo(() => readOutline(points.data), [points.data]);
  const [collapsed, setCollapsed] = useState<ReadonlySet<number>>(() => new Set<number>());

  const chosenId = defaultPointId(outline, selectedPointId);
  const selected = outline.ordered.find((point) => point.id === chosenId);

  // The URL is the page's selection, so it is kept in step with what is actually on screen rather
  // than living as a second, invisible answer. That covers both "no point named yet" and "the id
  // in the URL is not in this structure any more" — after a new version is confirmed, a stale link
  // must not keep claiming a point the learner is not looking at. `replace` because arriving at
  // the page is not a step the learner should have to press Back through.
  useEffect(() => {
    if (points.isPending || chosenId === undefined || selectedPointId === chosenId) return;
    void navigate({
      to: '/course/$courseId/study',
      params: { courseId },
      search: { knowledge_point_id: chosenId },
      replace: true,
    });
  }, [chosenId, courseId, navigate, points.isPending, selectedPointId]);

  const hasStructure = Boolean(structure.data?.active) || outline.ordered.length > 0;
  const pending = points.isPending || structure.isPending;

  /**
   * Open a point, and its chapter with it.
   *
   * The chapter is opened HERE rather than in an effect watching the selection: the learner's own
   * click is the moment the outline must not hide what they picked, and an effect would re-open a
   * chapter they had deliberately collapsed every time the selection happened to land in it. Every
   * other way of naming a point (a link, the URL) arrives with the outline still fully expanded,
   * which is how it starts.
   */
  const select = (pointId: number) => {
    const target = outline.ordered.find((point) => point.id === pointId);
    if (target?.chapterId !== null && target?.chapterId !== undefined) {
      const chapterId = target.chapterId;
      setCollapsed((current) => {
        if (!current.has(chapterId)) return current;
        const next = new Set(current);
        next.delete(chapterId);
        return next;
      });
    }
    void navigate({
      to: '/course/$courseId/study',
      params: { courseId },
      search: { knowledge_point_id: pointId },
    });
  };

  return (
    <CoursePageShell courseId={courseId} active="study">
      <PageHeader title="学习" />

      {pending ? (
        <LoadingState label="正在读取知识结构…" className="mt-8" />
      ) : points.isError || structure.isError ? (
        <Failure
          title="知识结构暂时无法加载。"
          error={points.error ?? structure.error}
          retry={() => {
            void points.refetch();
            void structure.refetch();
          }}
        />
      ) : !hasStructure ? (
        // Nothing to study from yet, and saying why is the whole page. The one action leads to
        // the page that can change it.
        <EmptyState
          className="mt-8"
          title="还没有知识结构"
          description="先建立知识结构，再开始按知识点学习。"
          action={
            <Link
              to="/course/$courseId/knowledge"
              params={{ courseId }}
              className="inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover"
            >
              建立知识结构
            </Link>
          }
        />
      ) : selected ? (
        <div className="mt-8 lg:grid lg:grid-cols-[17rem_minmax(0,1fr)] lg:gap-10">
          {/* Below desktop the outline becomes a chooser: the page still works around exactly one
              point, and a 280px column beside the content is not a thing a phone has. */}
          <div className="lg:hidden">
            <label className="block text-metadata font-medium text-text-muted" htmlFor="study-point-picker">
              选择知识点
            </label>
            <select
              id="study-point-picker"
              value={selected.id}
              onChange={(event) => select(Number(event.target.value))}
              className="mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              {outline.chapters.flatMap((chapter) => [
                <optgroup key={`chapter-${chapter.id}`} label={chapter.title}>
                  {chapter.points.map((point) => (
                    <option key={point.id} value={point.id}>
                      {knowledgeStatusLabel(point.status)} · {point.title}
                    </option>
                  ))}
                </optgroup>,
              ])}
              {outline.loose.length ? (
                <optgroup label="其他知识点">
                  {outline.loose.map((point) => (
                    <option key={point.id} value={point.id}>
                      {knowledgeStatusLabel(point.status)} · {point.title}
                    </option>
                  ))}
                </optgroup>
              ) : null}
            </select>
          </div>

          <aside className="hidden lg:block">
            <div className="sticky top-6 max-h-[calc(100vh-3rem)] overflow-y-auto pr-2">
              <OutlineNav
                outline={outline}
                selectedId={selected.id}
                collapsed={collapsed}
                onToggleChapter={(chapterId) =>
                  setCollapsed((current) => {
                    const next = new Set(current);
                    if (next.has(chapterId)) next.delete(chapterId);
                    else next.add(chapterId);
                    return next;
                  })
                }
                onSelect={select}
              />
            </div>
          </aside>

          <div className="mt-8 lg:mt-0">
            <StudyWorkspace
              key={selected.id}
              courseId={courseId}
              point={selected}
              status={selected.status}
              statusPending={updateStatus.isPending}
              onStatusChange={(next) => updateStatus.mutate({ pointId: selected.id, status: next })}
            />
            {updateStatus.isError ? (
              <StatusNote tone="danger" className="mt-4">
                学习状态没有保存成功，请稍后重试。
              </StatusNote>
            ) : null}
          </div>
        </div>
      ) : null}
    </CoursePageShell>
  );
}
