import { useRef, useState, type ReactNode } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { Download, ExternalLink, Search, Trash2 } from 'lucide-react';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { Button } from '@/components/ui/button';
import { MaterialFileIcon, isMaterialPreviewable, materialStatusLabel, materialTypeLabel } from '@/components/materials/material-file';
import { deleteMaterialErrorMessage, useLibraryDelete, useLibraryMaterials, type LibraryMaterial } from '@/features/library/api/library';
import { FactList } from '@/components/page/fact-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { formatBytes, formatDateTime } from '@/lib/format';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { serverMessage } from '@/lib/api/server-message';
import { cn } from '@/lib/utils';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { enumText } from '@/lib/learner-safe';
import { eventTypeLabel, serviceNamespaceLabel } from '@/features/records/event-labels';
import { MATERIAL_UPLOAD_ACCEPT, materialUploadErrorMessage, useCourseMaterialUpload, useCourseRecords, useCourseState, useCourseTodayPlan, useCourseWrongAnswers, useStartCourseQuestionAttempt } from '@/features/course/api/course';
import { CoursePageShell } from './course-page-shell';
import { ScopedAiChatWorkspace } from '@/features/ai/components/ai-chat-page';
import { DynamicPlanSurface, WrongAnalysisSurface } from '@/features/learning-intelligence/learning-intelligence-surfaces';

/* ------------------------------------------------------------------ shared local grammar */

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

function number(value: unknown, key: string): number | undefined {
  return isRecord(value) && typeof value[key] === 'number' ? value[key] : undefined;
}

function Section({ title, description, actions, children }: { title: string; description?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="mt-8">
      <SectionHeading title={title} description={description} action={actions} as="h2" />
      <div className="mt-4">{children}</div>
    </section>
  );
}

/**
 * The next step of the course loop, stated as a link rather than left to the tab bar.
 *
 * Every course page used to end wherever its data ended, which is what made these surfaces read
 * as separate tools. Naming the next step here — material → learn → practice → wrong → review →
 * plan — is what turns them into one sequence.
 */
function NextStep({ label, to, params }: { label: string; to: string; params?: Record<string, string> }) {
  return (
    <div className="mt-10 flex flex-wrap items-center justify-end gap-4 border-t border-border-default pt-6">
      <Link
        to={to as '/course'}
        params={params}
        className="inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover"
      >
        {label}
      </Link>
    </div>
  );
}

/**
 * A failure a learner can act on: what did not load, the server's own sentence when it wrote one,
 * and the way back. The response body, its status code and the request that produced it are not
 * a learner's business — they are for whoever reads the logs.
 */
function Failure({ title, error, retry }: { title: string; error: unknown; retry?: () => void }) {
  const message =
    error instanceof ApiRequestError ? serverMessage(error.detail) : null;
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

/* ------------------------------------------------------------------ materials */

/**
 * The five columns, declared ONCE and used by the header row and every data row.
 *
 * One template, not two layouts that happen to agree: a header built from flex and a row built
 * from something else drift the first time a label changes length, and the misalignment is what a
 * reader sees before they read anything.
 *
 * 名称 takes the remaining width (long filenames are the only unbounded content here). The rest
 * are fixed, sized to their longest honest value — a course name, a type and size, a state word,
 * and three actions — so a row with fewer buttons keeps its last column in the same place instead
 * of the actions sliding left.
 */
const MATERIAL_GRID = 'sm:grid sm:grid-cols-[minmax(0,1fr)_9rem_11rem_5rem_15rem] sm:items-center sm:gap-4';

const MATERIAL_FILTERS = [
  { id: 'all', label: '全部' },
  { id: 'pdf', label: 'PDF' },
  { id: 'doc', label: '文档' },
  { id: 'image', label: '图片' },
] as const;

type MaterialFilter = (typeof MATERIAL_FILTERS)[number]['id'];

/** The coarse buckets the filter offers; the exact type is still shown on the row. */
function matchesFilter(fileType: string, filter: MaterialFilter): boolean {
  if (filter === 'all') return true;
  const code = fileType.trim().toLowerCase();
  if (filter === 'pdf') return code === 'pdf';
  if (filter === 'image') return code === 'image';
  return code === 'docx' || code === 'pptx' || code === 'text' || code === 'code';
}

/**
 * ONE asset in the learner's library.
 *
 * The name is a LABEL, not a control. Opening a preview is what the 查看 action is for, and a
 * name that also opens a tab is a second, invisible way to do the same thing — one the learner
 * cannot see, cannot aim at and never asked for. So the name is plain text, and previewing has
 * exactly one door.
 *
 * 查看 is offered only where a browser can actually render the file: `isMaterialPreviewable` is
 * the shared statement of that rule, and the server's own `can_preview` adds whether this
 * particular file can still be served. A type that cannot be previewed gets no 查看 at all
 * rather than one that explains its own uselessness.
 */
function MaterialRow({ material, onDelete }: { material: LibraryMaterial; onDelete: (material: LibraryMaterial) => void }) {
  const canView = isMaterialPreviewable(material.fileType) && material.canPreview === true && material.previewUrl !== undefined;
  const canDownload = material.canDownload === true && material.downloadUrl !== undefined;
  const statusLabel = materialStatusLabel(material.parseStatus);
  const sizeText = [
    materialTypeLabel(material.fileType),
    material.fileSize === undefined ? undefined : formatBytes(material.fileSize),
  ].filter(Boolean).join(' · ');

  return (
    <li className="border-b border-border-default">
      {/* One element per column at every width; below `sm` the grid collapses to a single column
          and the same nodes stack, so nothing is rendered twice. Every column is centred on the
          row's own line, which is what keeps a two-line 类型 · 大小 block level with a one-line
          status rather than hanging below it. */}
      <div className={cn('py-4', MATERIAL_GRID)}>
        <div className="flex min-w-0 items-center gap-3">
          <MaterialFileIcon fileType={material.fileType} />
          {/* The name is a label, and a long one is clipped rather than allowed to push the
              columns after it around; the tooltip is where the whole name stays readable. */}
          <span title={material.filename} className="truncate text-body font-medium text-text-primary">{material.filename}</span>
        </div>
        <p className="mt-2 truncate text-metadata text-text-secondary sm:mt-0">{material.sourceLabel}</p>
        <div className="mt-1 sm:mt-0">
          <p className="text-metadata text-text-secondary">{sizeText}</p>
          {material.createdAt ? <p className="mt-0.5 text-metadata text-text-muted">{formatDateTime(material.createdAt)}</p> : null}
        </div>
        <p className="mt-1 text-metadata text-text-secondary sm:mt-0">{statusLabel}</p>
        <div className="mt-3 flex items-center gap-2 sm:mt-0 sm:justify-end">
          {canView ? (
            <a
              href={resolveApiResourceUrl(material.previewUrl!)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-metadata text-text-primary hover:bg-primary-soft"
            >
              <ExternalLink className="size-3.5" />
              查看
            </a>
          ) : null}
          {canDownload ? (
            <a
              href={resolveApiResourceUrl(material.downloadUrl!)}
              className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-metadata text-text-primary hover:bg-primary-soft"
            >
              <Download className="size-3.5" />
              下载
            </a>
          ) : null}
          <button
            type="button"
            onClick={() => onDelete(material)}
            className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-metadata text-danger-ink hover:bg-danger-soft"
          >
            <Trash2 className="size-3.5" />
            删除
          </button>
        </div>
      </div>
    </li>
  );
}

/**
 * The learner's whole material library, seen from inside a course.
 *
 * It lists every asset they own — this course's uploads, another course's, files sent to a chat,
 * files uploaded from the library picker — because all of them are the same thing to the person
 * who uploaded them. What stays course-specific is what RETRIEVAL uses: a question asked in this
 * course is grounded in this course's own material, plus whatever the learner explicitly
 * attaches, and never in everything this page happens to list. Those are deliberately different
 * questions and this list answers only the first.
 *
 * Uploading still belongs to the course it is done from, so the button says so and the server
 * files the file under this course — which is then what its 来源 column reads.
 */
export function CourseMaterialsPage({ courseId }: { courseId: string }) {
  const library = useLibraryMaterials();
  const remove = useLibraryDelete();
  const upload = useCourseMaterialUpload(courseId);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<MaterialFilter>('all');
  const [pendingDelete, setPendingDelete] = useState<LibraryMaterial | null>(null);

  const materials = library.data ?? [];
  const needle = search.trim().toLowerCase();
  const visible = materials.filter((material) => (
    matchesFilter(material.fileType, filter) && material.filename.toLowerCase().includes(needle)
  ));

  const confirmDelete = () => {
    if (!pendingDelete) return;
    // The dialog closes either way: a failure is stated in the list's own error note, where the
    // learner can see which row it was about, rather than as a modal that will not go away.
    remove.mutate(pendingDelete.materialId, { onSettled: () => setPendingDelete(null) });
  };

  return (
    <CoursePageShell courseId={courseId} active="materials" facts={[]}>
      {/* No page-sized title: 资料 is what the tab strip already says, and the course is named by
          the switcher above. The toolbar is what the page opens with. */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
          <div className="relative min-w-56 flex-1 sm:max-w-sm">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              aria-label="搜索资料"
              placeholder="搜索资料"
              className="h-11 w-full rounded-control border border-border-default bg-surface pl-9 pr-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            />
          </div>
          <div role="group" aria-label="按类型筛选资料" className="flex items-center gap-1">
            {MATERIAL_FILTERS.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={filter === option.id}
                onClick={() => setFilter(option.id)}
                className={cn(
                  'h-9 rounded-control px-3 text-body',
                  filter === option.id ? 'bg-primary-soft font-medium text-primary-ink' : 'text-text-secondary hover:bg-page-background',
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
        <label className="inline-flex h-11 shrink-0 cursor-pointer items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover focus-within:outline-none focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2">
          {upload.isPending ? '正在上传…' : '上传资料'}
          <input
            ref={uploadRef}
            type="file"
            className="sr-only"
            accept={MATERIAL_UPLOAD_ACCEPT}
            disabled={upload.isPending}
            onChange={(event) => {
              const file = event.target.files?.[0];
              // Clearing the input lets the same file be chosen again after a failure; without
              // it the second selection fires no change event and the retry looks ignored.
              event.target.value = '';
              if (file) upload.mutate(file);
            }}
          />
        </label>
      </div>

      {upload.isError ? (
        <StatusNote tone="danger" className="mt-4">{materialUploadErrorMessage(upload.error)}</StatusNote>
      ) : null}
      {upload.isSuccess ? <StatusNote tone="success" className="mt-4">已上传到本课程</StatusNote> : null}
      {remove.isError ? (
        <StatusNote tone="danger" className="mt-4">{deleteMaterialErrorMessage(remove.error)}</StatusNote>
      ) : null}

      {library.isPending ? (
        <LoadingState label="正在读取资料…" className="mt-8" rows={4} />
      ) : library.isError ? (
        <Failure title="资料暂时无法加载。" error={library.error} retry={() => void library.refetch()} />
      ) : materials.length === 0 ? (
        <EmptyState
          className="mt-8"
          title="暂无资料"
          description="上传课件、讲义或笔记，之后可在课程问答中直接使用。"
          action={
            <button
              type="button"
              onClick={() => uploadRef.current?.click()}
              disabled={upload.isPending}
              className="inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            >
              上传资料
            </button>
          }
        />
      ) : (
        <>
          <div className={cn('mt-8 hidden border-b border-border-default pb-2 text-metadata font-medium text-text-muted', MATERIAL_GRID)}>
            <span>名称</span>
            <span>来源</span>
            <span>类型 · 大小</span>
            <span>状态</span>
            <span className="text-right">操作</span>
          </div>
          {visible.length ? (
            <ul className="border-t border-border-default sm:border-t-0">
              {visible.map((material) => (
                <MaterialRow key={material.materialId} material={material} onDelete={setPendingDelete} />
              ))}
            </ul>
          ) : (
            <p className="mt-8 text-body text-text-secondary">没有找到相关资料</p>
          )}
        </>
      )}

      {pendingDelete ? (
        <ConfirmDialog
          title={`删除“${pendingDelete.filename}”？`}
          description="删除后，该资料将无法继续用于新的问答，但历史聊天中的文件记录会保留。"
          pending={remove.isPending}
          onConfirm={confirmDelete}
          onCancel={() => setPendingDelete(null)}
        />
      ) : null}
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ practice + wrong */

export function CourseWrongPage({ courseId }: { courseId: string }) {
  const navigate = useNavigate();
  const query = useCourseWrongAnswers(courseId);
  const startAttempt = useStartCourseQuestionAttempt();
  const items = list(query.data);

  return (
    <CoursePageShell
      courseId={courseId}
      active="wrong"
      facts={[{ label: '待复习条目', value: query.isPending ? '正在读取…' : `${items.length} 条` }]}
    >
      <PageHeader title="待复习条目" />

      {query.isPending ? (
        <LoadingState label="正在读取错题…" className="mt-8" />
      ) : query.isError ? (
        <Failure title="错题暂时无法加载。" error={query.error} retry={() => void query.refetch()} />
      ) : items.length ? (
        <ol className="mt-8 space-y-8">
          {items.map((item, index) => {
            const status = text(item, 'status');
            const stem = text(item, 'stem');
            const stateId = number(item, 'wrong_record_id');
            const questionId = number(item, 'question_id');
            return (
              <li key={stateId ?? index} className="border-l-2 border-border-default pl-5">
                <p className="text-metadata text-text-secondary">
                  {enumText('status', status, '待处理')}
                </p>
                <h2 className="mt-1 text-card-title font-medium text-text-primary">
                  {stem ?? '题目信息暂不完整'}
                </h2>
                <FactList
                  className="mt-4"
                  columns={1}
                  value={{
                    // `null`, not `undefined`: an answer the learner left blank is a fact this card
                    // states as `—`. Only a field the payload never carried is dropped.
                    user_answer: text(item, 'user_answer') ?? null,
                    reference_answer: text(item, 'reference_answer') ?? null,
                    analysis: text(item, 'analysis') ?? null,
                  }}
                />
                {status === 'active' && questionId !== undefined ? (
                  <div className="mt-4">
                    <Button
                      disabled={startAttempt.isPending}
                      onClick={() => startAttempt.mutate(
                        { courseId, questionId },
                        { onSuccess: (attempt) => void navigate({
                          to: '/course/$courseId/practice',
                          params: { courseId },
                          search: { session: attempt.attempt_id },
                        }) },
                      )}
                    >
                      重做此题
                    </Button>
                  </div>
                ) : null}
                <WrongAnalysisSurface stateId={stateId} sourceProven={Boolean(stem?.trim())} />
              </li>
            );
          })}
        </ol>
      ) : (
        <EmptyState className="mt-8" title="这门课程没有待复习条目。" />
      )}

      {startAttempt.isError ? (
        <StatusNote tone="danger" className="mt-4">暂时无法开始重做，请稍后重试。</StatusNote>
      ) : null}

      <NextStep label="进入统一复习" to="/review" />
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ plan + records + state */

function TodayPlanList({ value }: { value: unknown }) {
  const items = list(value);
  if (!items.length) {
    return <EmptyState title="今天没有课程任务。" />;
  }
  return (
    <ul className="border-t border-border-default">
      {items.map((item, index) => (
        <li key={text(item, 'id') ?? index} className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-border-default py-4">
          <div>
            <p className="text-body font-medium text-text-primary">{text(item, 'title') ?? '未命名的计划任务'}</p>
            <p className="mt-1 text-metadata text-text-secondary">
              {[
                text(item, 'mode_label'),
                text(item, 'task_type') ? enumText('task_type', text(item, 'task_type')) : undefined,
                text(item, 'due_date') ? `计划日期 ${text(item, 'due_date')}` : undefined,
              ]
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <span className="text-metadata text-text-secondary">
            {text(item, 'urgency_label') ?? (text(item, 'status') ? enumText('status', text(item, 'status'), '—') : '—')}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function CoursePlanPage({ courseId }: { courseId: string }) {
  const plan = useCourseTodayPlan(courseId);
  // Adjusting is something the learner decides to do to a plan they already have, so the panel
  // is opened by the button and there is no paragraph introducing it: what the panel asks for is
  // the whole introduction.
  const [adjusting, setAdjusting] = useState(false);
  const count = list(plan.data).length;

  return (
    <CoursePageShell
      courseId={courseId}
      active="plan"
      facts={[{ label: '今日任务', value: plan.isPending ? '正在读取…' : `${count} 项` }]}
    >
      <PageHeader
        title="今日计划"
        actions={
          adjusting ? undefined : (
            <button
              type="button"
              onClick={() => setAdjusting(true)}
              className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft"
            >
              调整计划
            </button>
          )
        }
      />

      {plan.isPending ? (
        <LoadingState label="正在读取今日计划…" className="mt-8" />
      ) : plan.isError ? (
        <Failure title="今日计划暂时无法加载。" error={plan.error} retry={() => void plan.refetch()} />
      ) : (
        <Section title="今天的任务">
          <TodayPlanList value={plan.data} />
        </Section>
      )}

      <DynamicPlanSurface
        scope={{ service_key: 'course_learning', course_id: courseId, exam_module_id: '', language: '' }}
        open={adjusting}
        onOpenChange={setAdjusting}
      />

      <NextStep
        label="查看学习记录"
        to="/course/$courseId/records"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

export function CourseRecordsPage({ courseId }: { courseId: string }) {
  const records = useCourseRecords(courseId);
  const events = list(records.data);

  return (
    <CoursePageShell
      courseId={courseId}
      active="records"
      facts={[{ label: '记录事件', value: records.isPending ? '正在读取…' : `${events.length} 条` }]}
    >
      {/* The record IS the timeline: what happened, in the order it happened. There is nothing
          above it to summarise it and nothing below it to lead out of it — the report is one
          link away for the totals, and the strip is where a learner goes next. */}
      <PageHeader
        title="专业学习记录"
        actions={
          <Link
            to="/reports"
            search={{ space: 'course_learning', courseId, module: undefined, language: undefined }}
            className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft"
          >
            查看学习报告
          </Link>
        }
      />

      {records.isPending ? (
        <LoadingState label="正在读取学习记录…" className="mt-8" />
      ) : records.isError ? (
        <Failure title="学习记录暂时无法加载。" error={records.error} retry={() => void records.refetch()} />
      ) : events.length ? (
        <ol className="mt-6 border-t border-border-default">
          {events.map((event, index) => (
            <li key={text(event, 'event_id') ?? index} className="border-b border-border-default py-4">
              <p className="text-body text-text-primary">
                {eventTypeLabel(text(event, 'event_type') ?? '')}
              </p>
              <p className="mt-1 text-metadata text-text-secondary">
                {serviceNamespaceLabel(text(event, 'service_namespace') ?? '')} · {formatDateTime(text(event, 'occurred_at'))}
              </p>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState className="mt-8" title="还没有学习记录。" />
      )}
    </CoursePageShell>
  );
}

export function CourseStatePage({ courseId }: { courseId: string }) {
  const state = useCourseState(courseId);
  const value = isRecord(state.data) ? state.data : undefined;
  const recent = value ? list(value.recent_activity) : [];

  return (
    <CoursePageShell courseId={courseId} active="state">
      <PageHeader
        title="已记录的学习情况"
        description="这里只呈现已经记录下来的内容：知识点状态、练习、错题、复习与计划。不含掌握度、能力评分或模型输出。"
      />

      {state.isPending ? (
        <LoadingState label="正在读取学习状态…" className="mt-8" rows={4} />
      ) : state.isError ? (
        <Failure title="状态暂时无法加载。" error={state.error} retry={() => void state.refetch()} />
      ) : value ? (
        <>
          <Section title="知识点进度">
            <FactList value={value.knowledge_progress} />
          </Section>
          <Section title="练习">
            <FactList value={value.practice} />
          </Section>
          <Section title="错题">
            <FactList value={value.wrong_answers} />
          </Section>
          <Section title="复习">
            <FactList value={value.review} />
          </Section>
          <Section title="计划">
            <FactList value={value.plan} />
          </Section>
          <Section title="最近活动">
            {recent.length ? (
              <ol className="border-t border-border-default">
                {recent.map((event, index) => (
                  <li key={text(event, 'event_id') ?? index} className="border-b border-border-default py-4">
                    <p className="text-body text-text-primary">{eventTypeLabel(text(event, 'event_type') ?? '')}</p>
                    <p className="mt-1 text-metadata text-text-secondary">{formatDateTime(text(event, 'occurred_at'))}</p>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState title="最近没有活动。" description="学习事件产生后会出现在这里。" />
            )}
          </Section>
        </>
      ) : (
        <EmptyState className="mt-8" title="暂无状态数据。" description="还没有可以展示的记录。" />
      )}

      <NextStep label="返回课程概览" to="/course/$courseId" params={{ courseId }} />
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ course Q&A */

export function CourseAskPage({ courseId }: { courseId: string }) {
  return (
    <CoursePageShell courseId={courseId} active="ask">
      <ScopedAiChatWorkspace scope={{ kind: 'course', courseId, label: courseId }} embedded />
    </CoursePageShell>
  );
}
