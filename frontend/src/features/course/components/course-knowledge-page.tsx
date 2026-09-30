import { useEffect, useRef, useState } from 'react';
import { Check, Pencil, Plus, Trash2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { StatusNote } from '@/components/ui/status-note';
import { MaterialFileIcon, materialStatusLabel } from '@/components/materials/material-file';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { cn } from '@/lib/utils';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import {
  MATERIAL_UPLOAD_ACCEPT,
  materialUploadErrorMessage,
  knowledgeStructureErrorMessage,
  useConfirmKnowledgeStructure,
  useCourseKnowledgeStructure,
  useCourseMaterials,
  useCourseMaterialUpload,
  useDeleteKnowledgeStructurePoint,
  useDiscardKnowledgeStructure,
  useEditKnowledgeStructurePoint,
  useGenerateKnowledgeStructure,
  type KnowledgeStructureChapter,
  type KnowledgeStructurePoint,
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

const FIELD =
  'h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2';

/* ------------------------------------------------------------------ sources */

/**
 * The two ways a structure can come into being.
 *
 * The first carries the page's Primary because it is the RECOMMENDED default — the structure
 * is then grounded in the learner's own material rather than in what a model already knows —
 * and this region has exactly one Primary action for that reason. It is not a ranking of
 * quality: 从资料生成 has nothing to do without files, so a learner who has none takes the
 * second path, and the copy above the buttons says both are open to them.
 */
function ChooseSource({ onPick, onCancel }: { onPick: (mode: 'files' | 'ai') => void; onCancel?: () => void }) {
  return (
    <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border-default pt-6">
      <Button size="lg" onClick={() => onPick('files')}>
        从资料生成
      </Button>
      <Button variant="secondary" size="lg" onClick={() => onPick('ai')}>
        AI 生成
      </Button>
      {onCancel ? (
        <Button variant="ghost" onClick={onCancel}>
          取消
        </Button>
      ) : null}
    </div>
  );
}

/**
 * The files this course's library holds, as something to choose from.
 *
 * An empty library is not a dead end: uploading from here files the material into the same
 * course library the 资料 page reads, and the file lands selected, so the flow the learner
 * started continues instead of sending them to another page to start over.
 */
function MaterialPicker({
  courseId,
  selected,
  onToggle,
  onCancel,
}: {
  courseId: string;
  selected: readonly number[];
  onToggle: (id: number) => void;
  onCancel: () => void;
}) {
  const materials = useCourseMaterials(courseId);
  const upload = useCourseMaterialUpload(courseId);
  const uploadRef = useRef<HTMLInputElement>(null);

  const rows = list(materials.data);

  return (
    <div className="mt-6 border-t border-border-default pt-6">
      {/* 返回 sits with the heading rather than beside the submit: the submit belongs to the
          parent (it is the parent that knows what was selected), and a back action placed after
          the forward one reads as a second step of the same flow. */}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <h2 className="text-heading font-semibold text-text-primary">选择资料</h2>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          返回
        </Button>
      </div>
      <p className="mt-2 max-w-prose text-body text-text-secondary">
        选中的资料会被用来整理知识结构。不选就是不用，不会默认把整个资料库都算进去。
      </p>

      {upload.isError ? (
        <StatusNote tone="danger" className="mt-4">{materialUploadErrorMessage(upload.error)}</StatusNote>
      ) : null}
      {upload.isSuccess ? (
        <StatusNote tone="success" className="mt-4">已上传到本课程资料库</StatusNote>
      ) : null}

      {materials.isPending ? (
        <LoadingState label="正在读取课程资料…" className="mt-6" rows={3} />
      ) : materials.isError ? (
        <Failure title="课程资料暂时无法加载。" error={materials.error} retry={() => void materials.refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState
          className="mt-6"
          title="还没有课程资料"
          description="先上传课件、讲义或笔记，上传后就能在这里勾选。"
          action={
            <>
              <Button
                size="lg"
                disabled={upload.isPending}
                onClick={() => uploadRef.current?.click()}
              >
                {upload.isPending ? '正在上传…' : '上传资料'}
              </Button>
              <input
                ref={uploadRef}
                type="file"
                className="sr-only"
                accept={MATERIAL_UPLOAD_ACCEPT}
                disabled={upload.isPending}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  // Cleared so choosing the same file again after a failure still fires.
                  event.target.value = '';
                  if (file) upload.mutate(file);
                }}
              />
            </>
          }
        />
      ) : (
        <>
          <ul className="mt-6 border-t border-border-default">
            {rows.map((material, index) => {
              const id = numberAt(material, 'id');
              const filename = text(material, 'original_filename') ?? '未命名资料';
              const checked = id !== undefined && selected.includes(id);
              return (
                <li key={id ?? index} className="border-b border-border-default">
                  <label className="flex cursor-pointer items-center gap-3 py-4">
                    <input
                      type="checkbox"
                      className="size-4 shrink-0 accent-primary"
                      checked={checked}
                      disabled={id === undefined}
                      onChange={() => id !== undefined && onToggle(id)}
                    />
                    <MaterialFileIcon fileType={text(material, 'file_type')} />
                    <span className="min-w-0 flex-1 truncate text-body font-medium text-text-primary" title={filename}>
                      {filename}
                    </span>
                    <span className="shrink-0 text-metadata text-text-secondary">
                      {materialStatusLabel(text(material, 'parse_status'))}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
          <Button
            variant="ghost"
            className="mt-4"
            disabled={upload.isPending}
            onClick={() => uploadRef.current?.click()}
          >
            <Plus className="size-4" aria-hidden="true" />
            上传更多资料
          </Button>
          <input
            ref={uploadRef}
            type="file"
            className="sr-only"
            accept={MATERIAL_UPLOAD_ACCEPT}
            disabled={upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              if (file) upload.mutate(file);
            }}
          />
        </>
      )}

    </div>
  );
}

/**
 * The learner's goal, asked for in the learner's words.
 *
 * Three of the four answers are the goals this product already knows how to talk about, offered
 * as one tap; 自定义 exists because the fourth learner is real and a closed list would make their
 * goal unstateable. Nothing else is asked: the course is already known, and every additional
 * field would be an internal parameter the learner has no way to answer.
 */
const GOALS = ['期末考试', '考研', '系统学习', '自定义'] as const;

function AiStructureForm({
  courseName,
  pending,
  error,
  onSubmit,
  onCancel,
}: {
  courseName: string;
  pending: boolean;
  error: unknown;
  onSubmit: (goal: string, requirement: string) => void;
  onCancel: () => void;
}) {
  const [goal, setGoal] = useState<string>('系统学习');
  const [customGoal, setCustomGoal] = useState('');
  const [requirement, setRequirement] = useState('');
  const resolvedGoal = goal === '自定义' ? customGoal.trim() : goal;

  return (
    <form
      className="mt-6 border-t border-border-default pt-6"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(resolvedGoal, requirement.trim());
      }}
    >
      <h2 className="text-heading font-semibold text-text-primary">AI 生成知识结构</h2>
      <p className="mt-2 max-w-prose text-body text-text-secondary">
        不用选资料。AI 会按这门课程公开的知识体系整理，生成后你可以先看再决定。
      </p>

      <dl className="mt-6">
        <dt className="text-metadata font-medium text-text-muted">课程</dt>
        <dd className="mt-1 text-body text-text-primary">{courseName}</dd>
      </dl>

      <fieldset className="mt-6">
        <legend className="text-metadata font-medium text-text-muted">学习目标（可选）</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {GOALS.map((option) => (
            <button
              key={option}
              type="button"
              aria-pressed={goal === option}
              onClick={() => setGoal(option)}
              className={cn(
                'h-9 rounded-control px-3 text-body',
                goal === option
                  ? 'bg-primary-soft font-medium text-primary-ink'
                  : 'border border-border-default text-text-secondary hover:bg-page-background',
              )}
            >
              {option}
            </button>
          ))}
        </div>
        {goal === '自定义' ? (
          <input
            type="text"
            value={customGoal}
            onChange={(event) => setCustomGoal(event.target.value)}
            aria-label="自定义学习目标"
            placeholder="例如：把二叉树和排序彻底弄懂"
            className={cn(FIELD, 'mt-3 sm:max-w-md')}
          />
        ) : null}
      </fieldset>

      <div className="mt-6">
        <label htmlFor="knowledge-structure-requirement" className="text-metadata font-medium text-text-muted">
          补充要求（可选）
        </label>
        <textarea
          id="knowledge-structure-requirement"
          value={requirement}
          onChange={(event) => setRequirement(event.target.value)}
          rows={3}
          placeholder="例如：按王道 408 的体系组织"
          className={cn(FIELD, 'mt-2 h-auto py-3')}
        />
      </div>

      {error ? <StatusNote tone="danger" className="mt-4">{knowledgeStructureErrorMessage(error)}</StatusNote> : null}

      <div className="mt-8 flex flex-wrap gap-3">
        <Button type="submit" size="lg" disabled={pending}>
          {pending ? '正在生成…' : '生成'}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={pending}>
          返回
        </Button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ the tree */

/**
 * One point in the structure, editable while it is still a proposal.
 *
 * Renaming happens in place, and saving is the only thing that leaves the row — pressing Escape
 * or the check both end the edit, so an abandoned rename never leaves a half-typed value in a
 * pending list the learner then has to hunt for.
 */
function PointRow({
  point,
  chapters,
  editable,
  busy,
  showProvenance,
  onRename,
  onMove,
  onDelete,
}: {
  point: KnowledgeStructurePoint;
  chapters: readonly KnowledgeStructureChapter[];
  editable: boolean;
  busy: boolean;
  showProvenance: boolean;
  onRename: (title: string) => void;
  onMove: (chapterId: number) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(point.title);
  const inputRef = useRef<HTMLInputElement>(null);
  // Only real chapters can be a destination. A point the server could not place under any
  // chapter is rendered in its own group, and moving a point INTO that group means nothing.
  const targets = chapters.filter((chapter) => chapter.id !== null);

  // Focus moves HERE because the learner just asked to edit this row — not on mount, which
  // would steal focus from wherever they were. The a11y rule bans the `autoFocus` attribute
  // precisely because it fires for the whole document; this fires for one explicit intent.
  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  if (editing) {
    return (
      <li className="border-b border-border-default py-3">
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            const next = draft.trim();
            if (next && next !== point.title) onRename(next);
            setEditing(false);
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={draft}
            aria-label="知识点名称"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setEditing(false);
            }}
            className={cn(FIELD, 'min-w-48 flex-1')}
          />
          {/* Named distinctly: this row also has a 取消 that abandons the REQUEST, and the
              draft bar has one that abandons the whole DRAFT — three different 取消 on one
              screen are three different actions to a screen reader. */}
          <Button type="submit" variant="secondary" size="sm" aria-label="保存知识点名称">
            <Check className="size-4" aria-hidden="true" />
            保存
          </Button>
          <Button variant="ghost" size="sm" aria-label="放弃修改" onClick={() => setEditing(false)}>
            <X className="size-4" aria-hidden="true" />
            取消
          </Button>
        </form>
      </li>
    );
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-border-default py-3">
      <div className="flex min-w-0 items-baseline gap-2">
        {/* A quiet bullet, not an icon: the list's subject is the names, and a marker per row
            would compete with them for the eye. */}
        <span aria-hidden="true" className="text-text-muted">○</span>
        <span className="text-body text-text-primary">{point.title}</span>
        {showProvenance && point.origin === 'ai_inferred' ? (
          <span className="text-metadata text-text-muted">AI 补充</span>
        ) : null}
      </div>
      {editable ? (
        <div className="flex items-center gap-1">
          {targets.length ? (
            <label className="flex items-center gap-1 text-metadata text-text-secondary">
              <span className="sr-only">{`把“${point.title}”移动到其他章节`}</span>
              <select
                value=""
                disabled={busy}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (value) onMove(value);
                }}
                className="h-8 rounded-control border border-border-default bg-surface px-2 text-metadata text-text-primary"
              >
                <option value="">移到…</option>
                {targets.map((chapter) => (
                  <option key={chapter.id} value={chapter.id as number}>
                    {chapter.title}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => {
              setDraft(point.title);
              setEditing(true);
            }}
          >
            <Pencil className="size-4" aria-hidden="true" />
            改名
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="text-danger-ink hover:bg-danger-soft hover:text-danger-ink"
            disabled={busy}
            onClick={onDelete}
          >
            <Trash2 className="size-4" aria-hidden="true" />
            删除
          </Button>
        </div>
      ) : null}
    </li>
  );
}

/** The structure itself: chapters, each with its points. Nothing else is on this surface. */
function StructureTree({
  chapters,
  editable,
  busy,
  showProvenance,
  onRename,
  onMove,
  onDelete,
}: {
  chapters: readonly KnowledgeStructureChapter[];
  editable: boolean;
  busy: boolean;
  showProvenance: boolean;
  onRename: (pointId: number, title: string) => void;
  onMove: (pointId: number, chapterId: number) => void;
  onDelete: (pointId: number) => void;
}) {
  return (
    <ol className="mt-8">
      {chapters.map((chapter, index) => (
        <li key={chapter.id ?? index} className="mt-10 first:mt-0">
          {/* A chapter is a MILESTONE on a path, not a row in a table, so it reads as one: its
              ordinal on the left, its name, and how much it contains on the right. The ordinal
              is what makes the sequence of chapters legible at a glance — the thing a learner
              is actually looking for when they open this page. */}
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-border-default pb-3">
            <span aria-hidden="true" className="text-metadata font-medium tabular-nums text-text-muted">
              {String(index + 1).padStart(2, '0')}
            </span>
            {/* h2, not h3: the page has exactly one h1 (the title), and a chapter IS a top-level
                block of it. Skipping to h3 leaves a screen reader with a level that names nothing. */}
            <h2 className="text-heading font-semibold text-text-primary">{chapter.title}</h2>
            <span className="ml-auto text-metadata text-text-muted">
              {chapter.points.length} 个知识点
            </span>
          </div>
          <ul>
            {chapter.points.map((point) => (
              <PointRow
                key={point.id}
                point={point}
                chapters={chapters}
                editable={editable}
                busy={busy}
                showProvenance={showProvenance}
                onRename={(title) => onRename(point.id, title)}
                onMove={(chapterId) => onMove(point.id, chapterId)}
                onDelete={() => onDelete(point.id)}
              />
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------------------------------------------ the page */

type Mode = 'idle' | 'choose-source' | 'files' | 'ai';

export function CourseKnowledgePage({ courseId }: { courseId: string }) {
  const structure = useCourseKnowledgeStructure(courseId);
  const generate = useGenerateKnowledgeStructure(courseId);
  const confirm = useConfirmKnowledgeStructure(courseId);
  const discard = useDiscardKnowledgeStructure(courseId);
  const renamePoint = useEditKnowledgeStructurePoint(courseId);
  const deletePoint = useDeleteKnowledgeStructurePoint(courseId);

  const [mode, setMode] = useState<Mode>('idle');
  const [selected, setSelected] = useState<readonly number[]>([]);

  const data = structure.data;
  const display = data?.display ?? 'none';
  const shown = data?.active ?? data?.draft ?? null;
  const isDraft = display === 'draft';
  const hasStructure = display !== 'none';
  const busy = generate.isPending || confirm.isPending || discard.isPending
    || renamePoint.isPending || deletePoint.isPending;

  const courseName = data?.course_id ?? courseId;

  const backToIdle = () => {
    setMode('idle');
    setSelected([]);
  };

  const runGenerate = (input: Parameters<typeof generate.mutate>[0]) => {
    generate.mutate(input, { onSuccess: () => { setMode('idle'); setSelected([]); } });
  };

  return (
    <CoursePageShell
      courseId={courseId}
      active="knowledge"
      facts={
        hasStructure && shown
          ? [
              { label: '知识点', value: `${shown.point_count} 个` },
              { label: '章节', value: `${shown.chapter_count} 个` },
            ]
          : []
      }
    >
      <PageHeader
        title="知识结构"
        description={
          hasStructure
            ? '这门课的知识点与章节。学习、练习与复习都围绕这份结构记录。'
            : undefined
        }
      />

      {structure.isPending ? (
        <LoadingState label="正在读取知识结构…" className="mt-8" />
      ) : structure.isError ? (
        <Failure title="知识结构暂时无法加载。" error={structure.error} retry={() => void structure.refetch()} />
      ) : (
        <>
          {/* The empty state is two sentences and two choices. Nothing is asked for until the
              learner has said which way they want to go, because at this point they have told
              the page nothing it could pre-fill. */}
          {!hasStructure && mode === 'idle' ? (
            <EmptyState
              className="mt-6"
              title="还没有知识结构"
              description="你可以从已有资料生成，也可以让 AI 根据这门课程生成。"
            />
          ) : null}
          {!hasStructure && mode === 'idle' ? (
            <ChooseSource onPick={(next) => setMode(next === 'files' ? 'files' : 'ai')} />
          ) : null}

          {/* An existing structure is a fact, not a call to action: it is stated, and regenerating
              is the one quiet thing offered beside it. */}
          {hasStructure && mode === 'idle' && !isDraft && shown ? (
            <div className="mt-6 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-t border-border-default pt-6">
              <div>
                <p className="text-body text-text-primary">
                  当前共 {shown.point_count} 个知识点，{shown.chapter_count} 个章节
                </p>
                <p className="mt-1 text-metadata text-text-muted">
                  {shown.source_mode === 'selected_materials' ? '来自资料生成' : 'AI 生成'} · 第 {shown.version} 版
                </p>
              </div>
              <Button variant="secondary" onClick={() => setMode('choose-source')}>
                重新生成
              </Button>
            </div>
          ) : null}

          {hasStructure && mode === 'choose-source' ? (
            <>
              <p className="mt-6 border-t border-border-default pt-6 text-body text-text-secondary">
                {isDraft
                  ? '换一种来源会重新生成一份草稿，现在这份草稿会被替换。'
                  : '重新生成会先做成草稿，确认后才会替换现在这份，原来的记录不会删除。'}
              </p>
              <ChooseSource onPick={(next) => setMode(next === 'files' ? 'files' : 'ai')} onCancel={backToIdle} />
            </>
          ) : null}

          {mode === 'files' ? (
            <>
              <MaterialPicker
                courseId={courseId}
                selected={selected}
                onToggle={(id) => setSelected((current) => (
                  current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
                ))}
                onCancel={backToIdle}
              />
              {generate.isError ? (
                <StatusNote tone="danger" className="mt-4">
                  {knowledgeStructureErrorMessage(generate.error)}
                </StatusNote>
              ) : null}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                  size="lg"
                  disabled={busy || selected.length === 0}
                  onClick={() => runGenerate({ sourceMode: 'selected_materials', materialIds: [...selected] })}
                >
                  {generate.isPending ? '正在生成…' : '生成知识结构'}
                </Button>
                {/* The count is stated because the button is disabled until at least one file is
                    chosen, and a disabled button with no explanation is a dead end. */}
                <span className="text-metadata text-text-muted">
                  {selected.length ? `已选 ${selected.length} 份资料` : '请至少选择 1 份资料'}
                </span>
              </div>
            </>
          ) : null}

          {mode === 'ai' ? (
            <AiStructureForm
              courseName={courseName}
              pending={generate.isPending}
              error={generate.error}
              onSubmit={(goal, requirement) => runGenerate({ sourceMode: 'ai_generated', goal, requirement })}
              onCancel={backToIdle}
            />
          ) : null}

          {/* The draft is shown as the structure it proposes, with the fact that it is NOT yet in
              use stated above it. Confirming is the only thing that makes it real. */}
          {hasStructure && isDraft && mode === 'idle' && data ? (
            <div className="mt-6 border-l-2 border-primary pl-4">
              <p className="text-body font-medium text-text-primary">这是一份草稿，还没有生效</p>
              <p className="mt-1 max-w-prose text-body text-text-secondary">
                确认后，学习和练习就会按这份结构记录。
                {data.carry_over?.has_progress && data.carry_over.matched_progressed_points > 0
                  ? `其中 ${data.carry_over.matched_progressed_points} 个已学过的知识点能对上，进度会保留。`
                  : ''}
                {data.carry_over?.has_progress && data.carry_over.unmatched_progressed_points > 0
                  ? `有 ${data.carry_over.unmatched_progressed_points} 个已学过的知识点不在新结构里，它们的记录会留在原版本，不会删除。`
                  : ''}
              </p>
            </div>
          ) : null}

          {hasStructure && mode === 'idle' && data ? (
            <StructureTree
              chapters={data.chapters}
              editable={isDraft}
              busy={busy}
              // Only useful when part of the structure came from files and part did not: in a
              // purely AI-generated structure every row would carry the same marker, which
              // says nothing per row.
              showProvenance={shown?.source_mode === 'selected_materials'}
              onRename={(pointId, title) => {
                if (shown) renamePoint.mutate({ structureId: shown.id, pointId, title });
              }}
              onMove={(pointId, chapterId) => {
                if (shown) renamePoint.mutate({ structureId: shown.id, pointId, chapterId });
              }}
              onDelete={(pointId) => {
                if (shown) deletePoint.mutate({ structureId: shown.id, pointId });
              }}
            />
          ) : null}

          {hasStructure && isDraft && mode === 'idle' && shown ? (
            <>
              {confirm.isError ? (
                <StatusNote tone="danger" className="mt-6">
                  {knowledgeStructureErrorMessage(confirm.error)}
                </StatusNote>
              ) : null}
              {discard.isError ? (
                <StatusNote tone="danger" className="mt-4">
                  {knowledgeStructureErrorMessage(discard.error)}
                </StatusNote>
              ) : null}
              <div className="mt-8 flex flex-wrap gap-3 border-t border-border-default pt-6">
                <Button size="lg" disabled={busy} onClick={() => confirm.mutate(shown.id)}>
                  {confirm.isPending ? '正在启用…' : '使用这个知识结构'}
                </Button>
                <Button variant="secondary" size="lg" disabled={busy} onClick={() => setMode('choose-source')}>
                  重新生成
                </Button>
                <Button variant="ghost" disabled={busy} onClick={() => discard.mutate(shown.id)}>
                  {discard.isPending ? '正在取消…' : '取消'}
                </Button>
              </div>
            </>
          ) : null}
        </>
      )}
    </CoursePageShell>
  );
}
