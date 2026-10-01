import { useEffect, useMemo } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Circle, CircleCheck, CircleDot, RotateCcw } from 'lucide-react';
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

/* ------------------------------------------------------------------ the structure this page reads */

/**
 * The learner's points, read from the ACTIVE version and nothing else.
 *
 * The points arrive as one ordered list whose chapters are their `parent_id`; grouping them here
 * keeps that single read as the page's only source. The grouping is not drawn as a navigation —
 * the workspace renders exactly ONE point, and 知识结构 is where a point is chosen — but the
 * chapter a point sits under is still part of what the point IS: it is what the page states
 * above the title, and what the practice link below sends the learner to.
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

  return (
    <CoursePageShell courseId={courseId} active="knowledge">
      <PageHeader
        title="学习"
        actions={
          // The workspace holds ONE point, so the way to another one is back where points are
          // chosen. Without this the page would be a dead end — 知识结构 is the entry, and this
          // is the way back to it.
          <Link
            to="/course/$courseId/knowledge"
            params={{ courseId }}
            className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft"
          >
            返回知识结构
          </Link>
        }
      />

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
        <div className="mt-8 max-w-prose">
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
      ) : null}
    </CoursePageShell>
  );
}
