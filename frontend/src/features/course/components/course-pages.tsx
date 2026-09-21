import { useState, type FormEvent, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { FactList } from '@/components/page/fact-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { formatBytes, formatDateTime } from '@/lib/format';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { enumText } from '@/lib/learner-safe';
import { eventTypeLabel, serviceNamespaceLabel } from '@/features/records/event-labels';
import { useCourseChat, useCourseKnowledge, useCourseKnowledgeMap, useCourseMaterials, useCourseMaterialUpload, useCoursePractice, useCoursePracticeAction, useCoursePracticeHistory, useCourseRecords, useCourseRecordsSummary, useCourseState, useCourseTodayPlan, useCourseWrongAnswers } from '@/features/course/api/course';
import { CoursePageShell } from './course-page-shell';
import { StrongReasoningSurface } from '@/components/learning/advanced-learning-surfaces';
import { DynamicPlanSurface, WrongAnalysisSurface } from '@/features/learning-intelligence/learning-intelligence-surfaces';
import { AiFeedback } from '@/components/learning/ai-feedback';

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
function NextStep({ label, description, to, params }: { label: string; description: string; to: string; params?: Record<string, string> }) {
  return (
    <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-border-default pt-6">
      <div>
        <p className="text-metadata font-medium tracking-eyebrow text-text-muted">下一步</p>
        <p className="mt-1 text-body text-text-secondary">{description}</p>
      </div>
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

function MaterialRow({ material }: { material: unknown }) {
  const name = text(material, 'original_filename');
  const size = number(material, 'file_size');
  const chunks = number(material, 'chunk_count');
  const progress = number(material, 'parse_progress');
  const status = text(material, 'parse_status');
  const created = text(material, 'created_at');
  return (
    <li className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 border-b border-border-default py-4">
      <div className="min-w-0">
        <p className="text-body font-medium text-text-primary">{name ?? '未命名资料'}</p>
        <p className="mt-1 text-metadata text-text-secondary">
          {[
            text(material, 'file_type') ? enumText('file_type', text(material, 'file_type')) : undefined,
            size !== undefined ? formatBytes(size) : undefined,
            chunks !== undefined ? `${chunks} 个片段` : undefined,
            `加入时间 ${formatDateTime(created)}`,
          ]
            .filter(Boolean)
            .join(' · ')}
        </p>
      </div>
      <div className="flex items-center gap-3">
        {status ? (
          <span className="text-metadata text-text-secondary">
            {enumText('parse_status', status)}
            {progress !== undefined && progress > 0 && progress < 100 ? ` ${progress}%` : ''}
          </span>
        ) : null}
      </div>
    </li>
  );
}

export function CourseMaterialsPage({ courseId }: { courseId: string }) {
  const query = useCourseMaterials(courseId);
  const upload = useCourseMaterialUpload(courseId);
  const materials = list(query.data);

  return (
    <CoursePageShell
      courseId={courseId}
      active="materials"
      facts={[
        { label: '本课程资料', value: query.isPending ? '正在读取…' : `${materials.length} 项` },
      ]}
    >
      <PageHeader
        eyebrow="资料"
        title="课程资料"
        description="上传到这门课程的资料会成为 AI 问答与知识点学习的引用来源。"
        actions={
          <label className="inline-flex h-11 cursor-pointer items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft">
            {upload.isPending ? '正在上传…' : '上传资料'}
            <input
              type="file"
              className="sr-only"
              disabled={upload.isPending}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
              }}
            />
          </label>
        }
      />

      {upload.isError ? <StatusNote tone="danger" className="mt-6">上传未成功，后端没有接受这个文件。</StatusNote> : null}
      {upload.isSuccess ? <StatusNote tone="success" className="mt-6">已提交上传；解析进度会显示在下方列表中。</StatusNote> : null}

      {query.isPending ? (
        <LoadingState label="正在读取课程资料…" className="mt-8" rows={4} />
      ) : query.isError ? (
        <Failure title="课程资料暂时无法加载。" error={query.error} retry={() => void query.refetch()} />
      ) : materials.length ? (
        <ul className="mt-6 border-t border-border-default">
          {materials.map((material, index) => (
            <MaterialRow key={text(material, 'id') ?? index} material={material} />
          ))}
        </ul>
      ) : (
        <EmptyState
          className="mt-8"
          title="这门课程还没有资料。"
          description="上传讲义、教材或课件后，知识点学习与课程问答才能引用它们。"
        />
      )}

      <NextStep
        label="进入知识结构"
        description="资料解析完成后，知识点与脉络会作为学习的起点。"
        to="/course/$courseId/knowledge"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ knowledge + study */

function KnowledgePointList({ value }: { value: unknown }) {
  const points = list(value);
  if (!points.length) {
    return <EmptyState title="暂无知识点。" description="知识点由课程内容解析产生；先确认这门课程已导入资料。" />;
  }
  return (
    <ul className="border-t border-border-default">
      {points.map((point, index) => {
        const title = text(point, 'title') ?? text(point, 'name') ?? text(point, 'knowledge_point_title');
        return (
          <li key={text(point, 'code') ?? title ?? index} className="border-b border-border-default py-4">
            <p className="text-body font-medium text-text-primary">{title ?? '未命名知识点'}</p>
            <FactList
              value={point}
              className="mt-3"
              columns={2}
              allow={['chapter', 'chapter_title', 'chapter_no', 'question_count', 'difficulty']}
            />
          </li>
        );
      })}
    </ul>
  );
}

export function CourseKnowledgePage({ courseId }: { courseId: string }) {
  const points = useCourseKnowledge(courseId);
  const map = useCourseKnowledgeMap(courseId);
  const count = list(points.data).length;

  return (
    <CoursePageShell
      courseId={courseId}
      active="knowledge"
      facts={[
        { label: '知识点', value: points.isPending ? '正在读取…' : `${count} 个` },
      ]}
    >
      <PageHeader
        eyebrow="知识结构"
        title="知识点与脉络"
        description="知识点与图谱都只属于当前课程；顺序与依赖来自后端记录，不在前端重排。"
      />

      {points.isPending ? (
        <LoadingState label="正在读取知识点…" className="mt-8" />
      ) : points.isError ? (
        <Failure title="知识结构暂时无法加载。" error={points.error} retry={() => void points.refetch()} />
      ) : (
        <Section title="知识点">
          <KnowledgePointList value={points.data} />
        </Section>
      )}

      <Section title="知识图谱" description="图谱是知识点之间记录的关联关系。">
        {map.isPending ? <LoadingState label="正在读取知识图谱…" rows={2} /> : null}
        {map.isError ? <Failure title="知识图谱暂时无法加载。" error={map.error} retry={() => void map.refetch()} /> : null}
        {!map.isPending && !map.isError && map.data !== undefined ? (
          <FactList value={map.data} columns={2} allow={['total_points', 'chapter', 'chapter_title']} />
        ) : null}
      </Section>

      <NextStep
        label="开始知识点学习"
        description="带着资料与知识点进入学习工作区，读完后直接进入练习。"
        to="/course/$courseId/study"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

export function CourseStudyPage({ courseId }: { courseId: string }) {
  const points = useCourseKnowledge(courseId);
  const materials = useCourseMaterials(courseId);
  const materialIds = list(materials.data).flatMap((material) => {
    const id = number(material, 'id');
    return id === undefined ? [] : [id];
  });

  return (
    <CoursePageShell
      courseId={courseId}
      active="study"
      facts={[
        { label: '可学知识点', value: points.isPending ? '正在读取…' : `${list(points.data).length} 个` },
        { label: '可引用资料', value: materials.isPending ? '正在读取…' : `${materialIds.length} 项` },
      ]}
    >
      <PageHeader
        eyebrow="学习"
        title="知识点学习"
        description="先读知识点与关联资料；读完直接进入练习验证理解。"
      />

      {points.isPending || materials.isPending ? (
        <LoadingState label="正在读取学习材料…" className="mt-8" />
      ) : points.isError || materials.isError ? (
        <Failure
          title="学习材料暂时无法加载。"
          error={points.error ?? materials.error}
          retry={() => {
            void points.refetch();
            void materials.refetch();
          }}
        />
      ) : (
        <>
          <Section title="当前课程知识点">
            <KnowledgePointList value={points.data} />
          </Section>
          <Section title="可引用资料">
            {materialIds.length ? (
              <ul className="border-t border-border-default">
                {list(materials.data).map((material, index) => (
                  <MaterialRow key={text(material, 'id') ?? index} material={material} />
                ))}
              </ul>
            ) : (
              <EmptyState title="还没有可引用的资料。" description="上传资料后，这里的提问与学习会带上真实引用。" />
            )}
          </Section>
        </>
      )}

      <StrongReasoningSurface context="课程学习" courseId={courseId} materialIds={materialIds} />

      <NextStep
        label="做本课程练习"
        description="练习会记录真实作答，并决定错题与复习安排。"
        to="/course/$courseId/practice"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ practice + wrong */

function PracticeAttemptFeedback({ data }: { data: unknown }) {
  return (
    <Panel tone="plain" className="mt-6">
      <p className="text-metadata font-medium tracking-eyebrow text-text-muted">本次提交</p>
      <FactList
        value={data}
        className="mt-3"
        allow={['correct', 'judge', 'submitted_at', 'status', 'question_type', 'difficulty']}
      />
    </Panel>
  );
}

export function CoursePracticePage({ courseId }: { courseId: string }) {
  const workbook = useCoursePractice(courseId);
  const history = useCoursePracticeHistory(courseId);
  const action = useCoursePracticeAction(courseId);
  const [answer, setAnswer] = useState('');

  const items = list(workbook.data);
  const current = items.find((item) => number(item, 'id') !== undefined);
  const questionId = number(current, 'id');
  const attempt = isRecord(current) && isRecord(current.latest_attempt) ? current.latest_attempt : undefined;
  const attemptId = number(attempt, 'id');
  const questionStem = text(current, 'stem') ?? text(current, 'title');

  return (
    <CoursePageShell
      courseId={courseId}
      active="practice"
      facts={[
        { label: '练习本', value: workbook.isPending ? '正在读取…' : `${items.length} 题` },
        { label: '历史作答', value: history.isPending ? '正在读取…' : `${list(history.data).length} 条` },
      ]}
    >
      <PageHeader
        eyebrow="练习"
        title="课程练习本"
        description="生成、作答与提交都记录为真实练习事实；提交结果决定错题与复习。"
        actions={
          <button
            type="button"
            className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft disabled:opacity-50"
            disabled={action.isPending}
            onClick={() => action.mutate({ kind: 'generate' })}
          >
            {action.isPending ? '正在生成…' : '生成练习题'}
          </button>
        }
      />

      {action.isError ? <StatusNote tone="danger" className="mt-6">操作未完成，请稍后重试。</StatusNote> : null}

      {questionId !== undefined ? (
        <Section title="当前题目" description={questionStem ?? '题目信息暂不完整'}>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="inline-flex h-10 items-center rounded-control border border-border-default bg-surface px-4 text-body text-text-primary hover:bg-primary-soft disabled:opacity-50"
              disabled={action.isPending}
              onClick={() => action.mutate({ kind: 'start', id: questionId })}
            >
              开始 / 重做本题
            </button>
          </div>
          {attemptId !== undefined ? (
            <form
              className="mt-5"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                action.mutate({ kind: 'submit', id: attemptId, answer });
              }}
            >
              <label className="block text-body font-medium text-text-primary" htmlFor="course-answer">
                你的作答
              </label>
              <textarea
                id="course-answer"
                value={answer}
                onChange={(event) => setAnswer(event.target.value)}
                className="mt-2 min-h-32 w-full rounded-card border border-border-default bg-surface p-4 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
                placeholder="写下你的答案"
              />
              <button
                type="submit"
                className="mt-4 inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50"
                disabled={action.isPending}
              >
                {action.isPending ? '正在提交…' : '提交作答'}
              </button>
            </form>
          ) : (
            <p className="mt-4 text-body text-text-secondary">先开始本题，作答后才能提交。</p>
          )}
        </Section>
      ) : null}

      {action.data !== undefined ? <PracticeAttemptFeedback data={action.data} /> : null}

      <Section title="练习本题目">
        {workbook.isPending ? (
          <LoadingState label="正在读取练习本…" />
        ) : workbook.isError ? (
          <Failure title="练习本暂时无法加载。" error={workbook.error} retry={() => void workbook.refetch()} />
        ) : items.length ? (
          <ol className="border-t border-border-default">
            {items.map((item, index) => {
              const stem = text(item, 'stem') ?? text(item, 'title');
              return (
                <li key={number(item, 'id') ?? index} className="border-b border-border-default py-4">
                  <p className="text-body text-text-primary">{stem ?? `第 ${index + 1} 题（题目信息暂不完整）`}</p>
                  <FactList
                    value={item}
                    className="mt-3"
                    columns={2}
                    allow={['question_type', 'difficulty', 'status', 'correct', 'judge', 'submitted_at']}
                  />
                </li>
              );
            })}
          </ol>
        ) : (
          <EmptyState title="练习本里还没有题目。" description="点「生成练习题」按当前课程知识点生成一题。" />
        )}
      </Section>

      <Section title="练习历史">
        {history.isPending ? (
          <LoadingState label="正在读取练习历史…" rows={2} />
        ) : list(history.data).length ? (
          <ol className="border-t border-border-default">
            {list(history.data).map((entry, index) => (
              <li key={number(entry, 'id') ?? index} className="border-b border-border-default py-4">
                <FactList
                  value={entry}
                  columns={2}
                  allow={['stem', 'title', 'question_type', 'difficulty', 'correct', 'judge', 'submitted_at', 'answered_at']}
                />
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title="还没有练习历史。" description="提交一次作答后，这里会按时间列出真实结果。" />
        )}
      </Section>

      <NextStep
        label="查看错题与复习"
        description="做错的题目会进入错题与复习安排，这是课程学习的闭环。"
        to="/course/$courseId/wrong"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

export function CourseWrongPage({ courseId }: { courseId: string }) {
  const query = useCourseWrongAnswers(courseId);
  const items = list(query.data);

  return (
    <CoursePageShell
      courseId={courseId}
      active="wrong"
      facts={[{ label: '待复习条目', value: query.isPending ? '正在读取…' : `${items.length} 条` }]}
    >
      <PageHeader
        eyebrow="错题与复习"
        title="待复习条目"
        description="题面、作答与参考答案都直接来自课程接口；这里不会用题目编号再去别处拼接内容。"
      />

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
                <WrongAnalysisSurface stateId={stateId} sourceProven={Boolean(stem?.trim())} />
              </li>
            );
          })}
        </ol>
      ) : (
        <EmptyState
          className="mt-8"
          title="这门课程没有待复习条目。"
          description="练习中做错的题目会产生错题与复习安排；当前没有需要订正的内容。"
        />
      )}

      <NextStep
        label="进入统一复习"
        description="跨学习空间的待复习项目都集中在统一复习里。"
        to="/review"
      />
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ plan + records + state */

function TodayPlanList({ value }: { value: unknown }) {
  const items = list(value);
  if (!items.length) {
    return <EmptyState title="今天没有课程任务。" description="计划任务来自学习计划；没有任务时这一栏保持为空，不补造内容。" />;
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
  const count = list(plan.data).length;

  return (
    <CoursePageShell
      courseId={courseId}
      active="plan"
      facts={[{ label: '今日任务', value: plan.isPending ? '正在读取…' : `${count} 项` }]}
    >
      <PageHeader
        eyebrow="计划"
        title="今日计划"
        description="任务顺序与紧迫程度由后端给出；这里是课程层面的今天。"
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

      <DynamicPlanSurface scope={{ service_key: 'course_learning', course_id: courseId, exam_module_id: '', language: '' }} />

      <NextStep
        label="查看学习记录"
        description="计划执行后留下的事件、练习与知识点变化都在记录里。"
        to="/course/$courseId/records"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

export function CourseRecordsPage({ courseId }: { courseId: string }) {
  const records = useCourseRecords(courseId);
  const summary = useCourseRecordsSummary(courseId);
  const events = list(records.data);

  return (
    <CoursePageShell
      courseId={courseId}
      active="records"
      facts={[{ label: '记录事件', value: records.isPending ? '正在读取…' : `${events.length} 条` }]}
    >
      <PageHeader
        eyebrow="记录"
        title="课程学习记录"
        description="按时间记录的事件流，与服务端学习报告使用同一批事实。"
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

      <Section title="汇总" description="统计窗口与口径由后端给出；缺失的指标显示为「—」，不当作 0。">
        {summary.isPending ? <LoadingState label="正在读取记录汇总…" rows={2} /> : null}
        {summary.isError ? <Failure title="记录汇总暂时无法加载。" error={summary.error} retry={() => void summary.refetch()} /> : null}
        {summary.data !== undefined ? <FactList value={summary.data} /> : null}
      </Section>

      <Section title="事件流">
        {records.isPending ? (
          <LoadingState label="正在读取学习记录…" />
        ) : records.isError ? (
          <Failure title="学习记录暂时无法加载。" error={records.error} retry={() => void records.refetch()} />
        ) : events.length ? (
          <ol className="border-t border-border-default">
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
          <EmptyState title="还没有学习记录。" description="完成一次练习、打开资料或提问后，这里会出现真实事件。" />
        )}
      </Section>

      <NextStep
        label="查看学习状态"
        description="状态是这些记录的确定性投影：知识点状态、练习、错题与计划。"
        to="/course/$courseId/state"
        params={{ courseId }}
      />
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
        eyebrow="学习状态"
        title="已记录的学习事实"
        description="这里只呈现已记录的事实：知识点状态、练习、错题、复习与计划。不含掌握度、能力评分或模型输出。"
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
        <EmptyState className="mt-8" title="暂无状态数据。" description="还没有可以投影的学习事实。" />
      )}

      <NextStep
        label="返回课程概览"
        description="回到概览查看学习闭环的下一步。"
        to="/course/$courseId"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}

/* ------------------------------------------------------------------ course Q&A */

export function CourseAskPage({ courseId }: { courseId: string }) {
  const chat = useCourseChat(courseId);
  const [message, setMessage] = useState('');
  const answer = isRecord(chat.data) && typeof chat.data.answer === 'string' ? chat.data.answer : undefined;
  const requestId = isRecord(chat.data) && typeof chat.data.request_id === 'string' ? chat.data.request_id : undefined;

  return (
    <CoursePageShell courseId={courseId} active="ask">
      <PageHeader
        eyebrow="课程问答"
        title="向这门课程提问"
        description="问题带上当前课程上下文，回答只引用这门课程的资料。"
      />

      <form
        className="mt-8"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (message.trim()) chat.mutate(message.trim());
        }}
      >
        <label className="block text-body font-medium text-text-primary" htmlFor="course-question">
          你的问题
        </label>
        <textarea
          id="course-question"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          required
          className="mt-2 min-h-28 w-full rounded-card border border-border-default bg-surface p-4 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          placeholder="例如：这一章的重点结论是什么？"
        />
        <button
          type="submit"
          className="mt-4 inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50"
          disabled={chat.isPending}
        >
          {chat.isPending ? '正在请求…' : '发送问题'}
        </button>
      </form>

      {chat.isError ? (
        <StatusNote tone="danger" className="mt-6">
          问答暂时不可用，没有返回可显示的答案。
          <button type="button" className="ml-3 underline" onClick={() => chat.reset()}>
            重试
          </button>
        </StatusNote>
      ) : null}

      {chat.isSuccess && answer === undefined ? (
        <StatusNote tone="warning" className="mt-6">
          这次提问没有返回可显示的答案，可以重新提问或换个问法。
        </StatusNote>
      ) : null}

      {answer !== undefined ? (
        <Panel tone="ai" className="mt-8">
          <p className="text-metadata font-medium tracking-eyebrow text-ai-ink">AI 回答 · 单次调用</p>
          <p className="mt-3 whitespace-pre-wrap text-body text-text-primary">{answer}</p>
          {requestId ? <AiFeedback requestId={requestId} workflowId="course_chat" /> : null}
        </Panel>
      ) : null}

      <StrongReasoningSurface context="课程问答" courseId={courseId} />

      <NextStep
        label="回到课程概览"
        description="回到概览，继续资料、学习、练习的下一步。"
        to="/course/$courseId"
        params={{ courseId }}
      />
    </CoursePageShell>
  );
}
