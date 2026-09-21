import { useState, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { SectionHeading } from '@/components/ui/section-heading';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusNote } from '@/components/ui/status-note';
import { Breadcrumb } from '@/components/page/breadcrumb';
import { ContextHeader } from '@/components/page/context-header';
import { ContextNav, type ContextNavItem } from '@/components/page/context-nav';
import { FactList } from '@/components/page/fact-list';
import { LoadingState } from '@/components/page/loading-state';
import { PageHeader } from '@/components/page/page-header';
import { canonicalLanguage, programmingLanguages } from '../programming-language';
import { readProgrammingOnboarding } from '../programming-onboarding';
import { useCodeAnalysis, useCodeDiagnose, useProgrammingAction, useProgrammingExercise, useProgrammingExercises, useProgrammingHome, useProgrammingOnboarding, useProgrammingPlan, useProgrammingRecords, useProgrammingRecordsSummary, useProgrammingState } from '../api/programming';
import { DebugAgentSurface } from '@/components/learning/advanced-learning-surfaces';
import { executionEvidence } from '@/components/learning/workflow-adapters';
import { DynamicPlanSurface } from '@/features/learning-intelligence/learning-intelligence-surfaces';
import { AiFeedback } from '@/components/learning/ai-feedback';
import { eventTypeLabel } from '@/features/records/event-labels';
import { usageCreditsText } from '@/lib/learner-safe';
import { formatDateTime } from '@/lib/format';

function rows(value: unknown): Array<Record<string, unknown>> { if (Array.isArray(value)) return value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null); if (value && typeof value === 'object') { const record = value as Record<string, unknown>; return rows(record.items ?? record.data ?? record.exercises ?? record.tasks ?? []); } return []; }
/** The exercise's own title. An exercise with no title is unnamed — its database id is not a name. */
function display(item: Record<string, unknown>, fallback: string) { return String(item.title ?? item.name ?? item.exercise_title ?? fallback); }
function text(value: unknown): string | undefined { return typeof value === 'string' && value.trim() ? value : undefined; }
function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value); }

/* ------------------------------------------------------------------ language context */

type ProgrammingTab = 'exercises' | 'errors' | 'plan' | 'records' | 'state';

function programmingTabs(language: string): readonly ContextNavItem[] {
  const params = { language };
  return [
    { id: 'exercises', label: '练习', to: '/programming/$language', params },
    { id: 'errors', label: '错误与待处理', to: '/programming/$language/errors', params },
    { id: 'plan', label: '计划', to: '/programming/$language/plan', params },
    { id: 'records', label: '记录', to: '/programming/$language/records', params },
    { id: 'state', label: '学习状态', to: '/programming/$language/state', params },
  ];
}

/**
 * One language, its tools, and the language a learner is currently in.
 *
 * The programming pages had no shared navigation at all — each was reachable only from the list
 * it happened to link back to. The tab strip below is the same one the other two spaces use, so
 * moving between practice, planning and records now keeps the language in view.
 */
function ProgrammingShell({ language, active, facts, children }: { language: string; active: ProgrammingTab; facts?: ReactNode; children: ReactNode }) {
  const canonical = canonicalLanguage(language) ?? language;
  const tabs = programmingTabs(language);
  const tabLabel = tabs.find((tab) => tab.id === active)?.label;
  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <Breadcrumb
        items={[
          { label: '编程学习', to: '/programming' },
          { label: canonical, to: active === 'exercises' ? undefined : '/programming/$language', params: { language } },
          ...(tabLabel ? [{ label: tabLabel }] : []),
        ]}
      />
      <ContextNav ariaLabel="编程学习导航" items={tabs} activeId={active} className="mt-4" />
      <ContextHeader
        className="mt-6"
        facts={[{ label: '当前语言', value: canonical }]}
        note={facts}
      />
      <div className="pb-12 pt-8">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ programming home */

/** The loop a programming exercise goes through, named in the order it happens. */
const PRACTICE_LOOP = [
  ['选择练习', '从题库里挑一道当前语言的练习题'],
  ['进入 Workbench', '读题面、写代码'],
  ['运行与测试', '运行、跑题目自带的测试'],
  ['提交', '提交会写进学习记录'],
  ['需要时求助', '代码诊断来自编译器；AI Debug 是单次调用；Debug Agent 是多步工作流'],
  ['修改并重试', '按反馈修改后重跑'],
] as const;

export function ProgrammingHomePage() {
  const query = useProgrammingHome();
  const onboarding = useProgrammingOnboarding();
  const declared = readProgrammingOnboarding(onboarding.data);
  const unconfigured = !onboarding.isPending && !onboarding.isError && !declared.completed;

  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="编程学习"
        title="编程工作台"
        description="编程学习按语言组织：练习、运行、提交与调试都在具体一门语言下发生。"
      />

      {unconfigured ? (
        <StatusNote className="mt-8">
          还没有声明练习语言与当前水平，学习状态与计划因此不会有内容。{' '}
          <Link
            to="/programming/setup"
            search={{ returnTo: '/programming' }}
            className="text-primary-ink underline hover:text-primary-hover"
          >
            设置编程学习
          </Link>{' '}
          后即可继续。下面的语言入口仍然可以直接使用。
        </StatusNote>
      ) : null}

      <section className="mt-8" aria-labelledby="language-choice-title">
        <SectionHeading
          id="language-choice-title"
          title="选择语言"
          description="进入某个语言后，它的练习、记录与学习状态会一起出现。"
        />
        <ul className="mt-5 grid gap-3 sm:grid-cols-2">
          {Object.entries(programmingLanguages).map(([slug, label]) => (
            <li key={slug}>
              <Link
                to="/programming/$language"
                params={{ language: slug }}
                className="flex items-center justify-between gap-4 rounded-card border border-border-default bg-surface px-5 py-4 hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              >
                <span className="text-body font-medium text-text-primary">{label}</span>
                <span className="text-metadata text-text-secondary">进入练习</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10" aria-labelledby="practice-loop-title">
        <SectionHeading
          id="practice-loop-title"
          title="一次练习是怎么走的"
          description="运行、测试与提交是主流程；诊断与 AI 是围绕它的辅助层。"
        />
        <ol className="mt-5 border-t border-border-default">
          {PRACTICE_LOOP.map(([step, detail], index) => (
            <li key={step} className="flex gap-4 border-b border-border-default py-4">
              <span className="w-6 text-metadata tabular-nums text-text-muted">
                {String(index + 1).padStart(2, '0')}
              </span>
              <span>
                <span className="block text-body font-medium text-text-primary">{step}</span>
                <span className="mt-0.5 block text-body text-text-secondary">{detail}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-10">
        <h2 className="text-metadata font-medium tracking-eyebrow text-text-muted">工作台数据</h2>
        {query.isPending ? (
          <LoadingState label="正在读取工作台…" className="mt-3" />
        ) : query.isError ? (
          <StatusNote tone="danger" className="mt-3">
            工作台数据暂时无法加载；上面的语言入口仍然可用。
          </StatusNote>
        ) : (
          <FactList
            className="mt-3"
            value={isRecord(query.data) ? query.data.stats : undefined}
            allow={['streak_days', 'momentum', 'today_practice_count', 'today_submission_count', 'last_activity_date']}
          />
        )}
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------ exercises */

export function ExercisesPage({ language }: { language: string }) {
  const canonical = canonicalLanguage(language);
  const query = useProgrammingExercises(canonical ?? language);
  const items = rows(query.data);

  if (!canonical) {
    return (
      <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
        <PageHeader eyebrow="编程学习" title="未支持的语言" description="请选择 C、C++、Python 或 Java。" />
      </div>
    );
  }

  return (
    <ProgrammingShell
      language={language}
      active="exercises"
      facts={query.isSuccess ? `${items.length} 道练习题` : null}
    >
      <PageHeader
        eyebrow="练习"
        title={`${canonical} 练习`}
        description="列表来自真实题库；难度与来源由后端给出，不在前端计算或补造。"
      />

      {query.isPending ? (
        <LoadingState label="正在加载练习…" className="mt-8" rows={4} />
      ) : query.isError ? (
        <StatusNote tone="danger" className="mt-8">
          练习列表暂时无法加载。
        </StatusNote>
      ) : items.length ? (
        <ol className="mt-8 border-t border-border-default">
          {items.map((item, index) => (
            <li key={String(item.id ?? index)} className="border-b border-border-default">
              <Link
                className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-4 hover:bg-primary-soft"
                to="/programming/$language/exercises/$exerciseId"
                params={{ language, exerciseId: String(item.id) }}
              >
                <span className="text-body font-medium text-text-primary">
                  {display(item, `练习 ${index + 1}`)}
                </span>
                <span className="flex items-center gap-2">
                  {text(item.difficulty) ? <Badge>{text(item.difficulty)}</Badge> : null}
                  {text(item.source_label) ? <Badge tone="neutral">{text(item.source_label)}</Badge> : null}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState
          className="mt-8"
          title="这门语言暂时没有可练习的题目。"
          description="题库为空时不补造练习；可以先看看其他语言，或回到编程学习首页。"
        />
      )}
    </ProgrammingShell>
  );
}

export function ExerciseDetailPage({ language, exerciseId }: { language: string; exerciseId: number }) {
  const query = useProgrammingExercise(language, exerciseId);
  return (
    <ProgrammingShell language={language} active="exercises">
      <PageHeader eyebrow="练习" title="练习题面" />
      {query.isPending ? (
        <LoadingState label="正在读取题目…" className="mt-6" rows={4} />
      ) : query.isError ? (
        <StatusNote tone="danger" className="mt-6">
          题目暂时无法加载。
          <button type="button" className="ml-3 underline" onClick={() => void query.refetch()}>
            重试
          </button>
          <Link
            to="/programming/$language/exercises"
            params={{ language }}
            className="ml-3 underline"
          >
            返回练习列表
          </Link>
        </StatusNote>
      ) : (
        <>
          <ExerciseStatement
            payload={query.data}
            recovery={
              <>
                <Button variant="secondary" onClick={() => void query.refetch()}>
                  重试
                </Button>
                <Button asChild variant="ghost">
                  <Link to="/programming/$language/exercises" params={{ language }}>
                    返回练习列表
                  </Link>
                </Button>
              </>
            }
          />
          <Button asChild className="mt-6">
            <Link to="/programming/$language/projects/$projectId" params={{ language, projectId: String(exerciseId) }}>
              在 Workbench 中开始
            </Link>
          </Button>
        </>
      )}
    </ProgrammingShell>
  );
}

/* ------------------------------------------------------------------ workbench */

type DiagnosticItem = { line?: number; column?: number; message?: string; severity?: string; source?: string };

function readDiagnostics(value: unknown, key: 'errors' | 'warnings'): DiagnosticItem[] {
  if (!value || typeof value !== 'object') return [];
  const list = (value as Record<string, unknown>)[key];
  if (!Array.isArray(list)) return [];
  return list.filter((item): item is DiagnosticItem => typeof item === 'object' && item !== null);
}

/** A compiler's own verdict, printed with the line and column IT reported. */
function DiagnosticList({ title, items }: { title: string; items: DiagnosticItem[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-4">
      <h4 className="text-body font-medium text-text-primary">{title}</h4>
      <ul className="mt-2 space-y-2">
        {items.map((item, index) => (
          <li key={`${item.source ?? 'x'}-${item.line ?? 0}-${index}`} className="text-body text-text-secondary">
            <span className="font-mono text-metadata">
              {item.line ?? '?'}:{item.column ?? '?'}
            </span>{' '}
            {item.message ?? '诊断项未提供描述。'}
            {item.source ? <span className="ml-2 text-metadata text-text-muted">来源：{item.source}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The statement, as fields the backend actually sends.
 *
 * The payload is a dict of Chinese fields (`statement`, `input_format`, `output_format`,
 * `constraints`, `public_samples`, …), so they are laid out as a readable problem rather than
 * dumped as JSON. Hints and background stay folded: they are support a learner asks for, and
 * unfolding them by default would answer the exercise on arrival.
 */
function ExerciseStatement({ payload, recovery }: { payload: unknown; recovery?: ReactNode }) {
  const root = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
  const exercise = (root.exercise && typeof root.exercise === 'object' ? root.exercise : root) as Record<string, unknown>;
  const title = text(exercise.title);
  const statement = text(exercise.statement) ?? text(exercise.problem_statement) ?? text(exercise.summary);
  const inputFormat = text(exercise.input_format);
  const outputFormat = text(exercise.output_format);
  const constraints = text(exercise.constraints);
  const hints = text(exercise.hints);
  const background = text(exercise.background_knowledge);
  const samples = Array.isArray(exercise.public_samples) ? (exercise.public_samples as Array<Record<string, unknown>>) : [];

  return (
    <Panel tone="plain" className="mt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <h2 className="text-heading font-semibold text-text-primary">{title ?? '练习题面'}</h2>
        <div className="flex flex-wrap items-center gap-2">
          {text(exercise.language) ? <Badge tone="brand">{text(exercise.language)}</Badge> : null}
          {text(exercise.difficulty) ? <Badge>{text(exercise.difficulty)}</Badge> : null}
          {text(exercise.source_label) ? <Badge>{text(exercise.source_label)}</Badge> : null}
        </div>
      </div>

      {statement ? (
        <p className="mt-4 whitespace-pre-wrap text-body text-text-primary">{statement}</p>
      ) : (
        <div className="mt-4">
          <p className="text-body text-text-secondary">题目信息暂不完整，这里无法显示题面。</p>
          {recovery ? <div className="mt-3 flex flex-wrap gap-3">{recovery}</div> : null}
        </div>
      )}

      <dl className="mt-5 space-y-3">
        {inputFormat ? (
          <div>
            <dt className="text-metadata font-medium tracking-eyebrow text-text-muted">输入格式</dt>
            <dd className="mt-1 whitespace-pre-wrap text-body text-text-primary">{inputFormat}</dd>
          </div>
        ) : null}
        {outputFormat ? (
          <div>
            <dt className="text-metadata font-medium tracking-eyebrow text-text-muted">输出格式</dt>
            <dd className="mt-1 whitespace-pre-wrap text-body text-text-primary">{outputFormat}</dd>
          </div>
        ) : null}
        {constraints ? (
          <div>
            <dt className="text-metadata font-medium tracking-eyebrow text-text-muted">约束</dt>
            <dd className="mt-1 whitespace-pre-wrap text-body text-text-primary">{constraints}</dd>
          </div>
        ) : null}
      </dl>

      {samples.length ? (
        <div className="mt-5">
          <h3 className="text-metadata font-medium tracking-eyebrow text-text-muted">公开样例</h3>
          <ul className="mt-2 space-y-3">
            {samples.map((sample, index) => (
              <li key={String(sample.id ?? index)} className="rounded-control border border-border-default p-3">
                <div className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <p className="text-metadata text-text-muted">输入</p>
                    <pre className="mt-1 overflow-auto whitespace-pre-wrap font-mono text-metadata text-text-primary">
                      {String(sample.input ?? sample.stdin ?? '—')}
                    </pre>
                  </div>
                  <div>
                    <p className="text-metadata text-text-muted">期望输出</p>
                    <pre className="mt-1 overflow-auto whitespace-pre-wrap font-mono text-metadata text-text-primary">
                      {String(sample.output ?? sample.expected_output ?? sample.stdout ?? '—')}
                    </pre>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {hints || background ? (
        <div className="mt-5 space-y-2">
          {background ? (
            <details>
              <summary className="text-body text-text-secondary">背景知识</summary>
              <p className="mt-2 whitespace-pre-wrap text-body text-text-primary">{background}</p>
            </details>
          ) : null}
          {hints ? (
            <details>
              <summary className="text-body text-text-secondary">提示（先自己尝试再看）</summary>
              <p className="mt-2 whitespace-pre-wrap text-body text-text-primary">{hints}</p>
            </details>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}

export function WorkbenchPage({ language, exerciseId }: { language: string; exerciseId: number }) {
  const [code, setCode] = useState('');
  const [output, setOutput] = useState<unknown>();
  const [diagnosis, setDiagnosis] = useState<unknown>();
  const [analysis, setAnalysis] = useState<unknown>();
  const [analysisQuestion, setAnalysisQuestion] = useState('');
  const [lastAction, setLastAction] = useState<'run' | 'test' | 'submit' | undefined>();

  const action = useProgrammingAction(language, exerciseId);
  const exercise = useProgrammingExercise(language, exerciseId);
  const diagnose = useCodeDiagnose();
  const analyze = useCodeAnalysis();
  const canonical = canonicalLanguage(language) ?? language;

  const invoke = (kind: 'start' | 'run' | 'test' | 'submit') => action.mutate({ action: kind }, { onSuccess: (data) => { setOutput(data); if (kind !== 'start') setLastAction(kind); } });
  const evidence = lastAction && output !== undefined ? executionEvidence(lastAction, output) : undefined;
  const failedTest = evidence?.kind === 'test' && evidence.passed === false;

  // The question the AI is asked is composed from THIS run's real output, so the request names
  // the failure that actually happened instead of a generic prompt.
  const failedTestQuestion = ['测试未通过。', evidence?.stderr ? `stderr：${evidence.stderr.slice(0, 1000)}` : '', '请分析原因并给出可审阅的修改建议。'].filter(Boolean).join('\n');

  const runAnalysis = (question: string) => {
    setAnalysisQuestion(question);
    analyze.mutate({ language: canonical, code, question }, { onSuccess: setAnalysis });
  };

  const diagnosisErrors = readDiagnostics(diagnosis, 'errors');
  const diagnosisWarnings = readDiagnostics(diagnosis, 'warnings');
  const diagnosisStatus = diagnosis && typeof diagnosis === 'object' ? (diagnosis as Record<string, unknown>).status : undefined;
  const analysisRequestId = analysis && typeof analysis === 'object' && typeof (analysis as Record<string, unknown>).request_id === 'string' ? (analysis as Record<string, string>).request_id : undefined;
  const analysisAnswer = analysis && typeof analysis === 'object' && typeof (analysis as Record<string, unknown>).answer === 'string' ? (analysis as Record<string, string>).answer : undefined;
  const usageCredits = usageCreditsText(analysis && typeof analysis === 'object' ? (analysis as Record<string, unknown>).usage : undefined);
  const busy = action.isPending;

  return (
    <div className="mx-auto w-full max-w-content px-5 py-8 sm:px-8 lg:px-12">
      <Breadcrumb
        items={[
          { label: '编程学习', to: '/programming' },
          { label: canonical, to: '/programming/$language', params: { language } },
          { label: '练习', to: '/programming/$language/exercises', params: { language } },
          { label: `练习 #${exerciseId}` },
        ]}
      />
      <PageHeader
        eyebrow={`${canonical} · Workbench`}
        title={`练习 #${exerciseId}`}
        description="沿开始、编写、运行、测试、提交、修复推进；每一步的结果都由后端返回。"
        className="mt-4"
      />

      {exercise.isPending ? (
        <Panel className="mt-6">
          <div className="space-y-3" aria-hidden="true">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </Panel>
      ) : exercise.isError ? (
        <StatusNote tone="danger" className="mt-6">
          题目暂时无法加载，无法安全开始。
          <button type="button" className="ml-3 underline" onClick={() => void exercise.refetch()}>
            重试
          </button>
          <Link to="/programming/$language/exercises" params={{ language }} className="ml-3 underline">
            返回练习列表
          </Link>
        </StatusNote>
      ) : (
        <ExerciseStatement
          payload={exercise.data}
          recovery={
            <>
              <Button variant="secondary" onClick={() => void exercise.refetch()}>
                重试
              </Button>
              <Button asChild variant="ghost">
                <Link to="/programming/$language/exercises" params={{ language }}>
                  返回练习列表
                </Link>
              </Button>
            </>
          }
        />
      )}

      <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <section aria-labelledby="workbench-editor-title">
          <h2 id="workbench-editor-title" className="text-heading font-semibold text-text-primary">
            编写代码
          </h2>
          <label className="mt-4 block text-body font-medium text-text-primary" htmlFor="program-code">
            代码
          </label>
          <textarea
            id="program-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            className="mt-2 min-h-80 w-full rounded-card border border-border-default bg-surface p-4 font-mono text-sm text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            placeholder="在这里编写代码"
          />

          {/*
            The deterministic tier. Every control here runs a compiler or the runtime against the
            buffer: no model call, nothing spent from the learner's AI 额度 — so they keep working
            when no model is available, and they are what a learner reaches for by default. 提交 is
            the only filled button because it is the one that changes the record; the rest are
            outlined peers.
          */}
          <div
            role="group"
            aria-labelledby="workbench-deterministic-title"
            className="mt-4 rounded-card border border-border-default bg-surface p-4"
          >
            <p
              id="workbench-deterministic-title"
              className="text-metadata font-medium tracking-eyebrow text-text-muted"
            >
              确定性工具（不调用模型、不消耗额度）
            </p>
            <div className="mt-3 flex flex-wrap gap-3">
              <Button variant="ghost" disabled={busy || exercise.isError} onClick={() => invoke('start')}>
                开始练习
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => invoke('run')}>
                运行
              </Button>
              <Button variant="secondary" disabled={busy} onClick={() => invoke('test')}>
                运行测试
              </Button>
              <Button
                variant="secondary"
                disabled={diagnose.isPending || !code.trim()}
                onClick={() => diagnose.mutate({ language: canonical, code }, { onSuccess: setDiagnosis })}
              >
                {diagnose.isPending ? '正在检查…' : '运行代码诊断'}
              </Button>
              <Button variant="primary" disabled={busy} onClick={() => invoke('submit')}>
                提交
              </Button>
            </div>
            <p className="mt-3 text-metadata text-text-muted">
              「开始练习」建立本次练习上下文；其余动作都作用于当前代码。代码诊断由 gcc / Python
              编译器完成，行号与列号来自编译器本身。
            </p>

            {diagnose.isError ? (
              <StatusNote tone="warning" className="mt-4">
                代码诊断暂时不可用；这不影响运行、测试与提交。
              </StatusNote>
            ) : null}

            {diagnosis ? (
              <section className="mt-4" aria-label="代码诊断结果">
                <p className="text-body text-text-primary">
                  结果：{diagnosisStatus === 'ok' ? '未发现问题' : diagnosisStatus === 'warning' ? '有警告' : '有错误'}
                </p>
                <DiagnosticList title="错误" items={diagnosisErrors} />
                <DiagnosticList title="警告" items={diagnosisWarnings} />
                {!diagnosisErrors.length && !diagnosisWarnings.length ? (
                  <p className="mt-2 text-body text-text-secondary">编译器未报告错误或警告。</p>
                ) : null}
              </section>
            ) : null}
          </div>
        </section>

        <section aria-labelledby="workbench-output-title" aria-live="polite">
          <h2 id="workbench-output-title" className="text-heading font-semibold text-text-primary">
            执行反馈
          </h2>
          <div className="mt-4 rounded-card border border-border-default bg-surface p-4">
            {action.isPending ? (
              <p className="text-body text-text-secondary">
                正在执行{lastAction === 'run' ? '运行' : lastAction === 'test' ? '测试' : lastAction === 'submit' ? '提交' : '操作'}…
              </p>
            ) : action.isError ? (
              <StatusNote tone="danger">执行未成功。请检查输入后重试。</StatusNote>
            ) : evidence ? (
              <>
                <p className="text-body text-text-secondary">
                  {evidence.kind === 'run' ? '运行结果' : evidence.kind === 'test' ? '测试结果' : '提交结果'}
                </p>
                {evidence.stdout ? (
                  <pre className="mt-3 overflow-auto rounded-control bg-lab-ink p-4 text-xs text-lab-paper">stdout{`\n`}{evidence.stdout}</pre>
                ) : null}
                {evidence.stderr ? (
                  <pre className="mt-3 overflow-auto rounded-control border border-danger p-4 text-xs text-danger-ink">stderr{`\n`}{evidence.stderr}</pre>
                ) : null}
                {evidence.kind === 'test' && evidence.passed !== undefined ? (
                  <p className="mt-3 text-body text-text-primary">测试：{evidence.passed ? '通过' : '未通过'}</p>
                ) : null}
                {evidence.kind === 'submit' ? (
                  <p className="mt-3 text-body text-text-secondary">
                    提交已收到后端响应；学习记录与状态正在刷新。
                  </p>
                ) : null}
              </>
            ) : (
              <p className="text-body text-text-secondary">
                运行、测试或提交后，会在这里显示对应的真实证据。
              </p>
            )}
          </div>
        </section>
      </div>

      {/*
        The AI tier. One call that spends the learner's AI 额度 — which is why it is a step below
        the deterministic tools rather than a peer of 运行: it is help a learner asks for, not the
        default way to make progress. The agent workflow below is the widest and rarest of the
        three, so it stays folded until asked for.
      */}
      <Panel tone="ai" className="mt-8" labelledBy="workbench-ai-title">
        <p className="text-metadata font-medium tracking-eyebrow text-ai-ink">AI 辅助 · 单次调用</p>
        <h2 id="workbench-ai-title" className="mt-2 text-heading font-semibold text-text-primary">
          AI Debug（AI 代码分析）
        </h2>
        <p className="mt-2 max-w-prose text-body text-text-secondary">
          一次真实 AI 调用，会消耗额度；回答下方可以评价这次分析是否有帮助。
        </p>

        <label className="mt-4 block text-body font-medium text-text-primary" htmlFor="analysis-question">
          要分析的问题
        </label>
        <textarea
          id="analysis-question"
          value={analysisQuestion}
          onChange={(event) => setAnalysisQuestion(event.target.value)}
          className="mt-2 min-h-24 w-full rounded-card border border-border-default bg-surface p-3 text-body text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-accent focus-visible:ring-offset-2"
          placeholder="例如：这段代码为什么输出不对？"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            variant="secondary"
            disabled={analyze.isPending || !code.trim() || !analysisQuestion.trim()}
            onClick={() => runAnalysis(analysisQuestion.trim())}
          >
            {analyze.isPending ? '正在分析…' : 'AI Debug'}
          </Button>
          {failedTest ? (
            <Button variant="ghost" disabled={analyze.isPending} onClick={() => runAnalysis(failedTestQuestion)}>
              用 AI Debug 分析这次失败
            </Button>
          ) : null}
        </div>
        {!analysisQuestion.trim() ? (
          <p className="mt-2 text-metadata text-text-secondary">
            请输入要分析的问题；AI 需要知道你在问什么。
          </p>
        ) : null}
        {analyze.isError ? (
          <StatusNote tone="danger" className="mt-3">
            AI 请求暂时不可用；请稍后重试。
          </StatusNote>
        ) : null}
        {analysis ? (
          <section className="mt-4" aria-label="AI 代码分析回答">
            {analysisAnswer ? (
              <p className="whitespace-pre-wrap text-body text-text-primary">{analysisAnswer}</p>
            ) : (
              <p className="text-body text-text-secondary">
                这次分析没有返回可显示的内容，可以重新提问或换个问法。
              </p>
            )}
            {usageCredits ? (
              <p className="mt-3 text-metadata text-text-secondary">{usageCredits}</p>
            ) : null}
            {analysisRequestId ? <AiFeedback requestId={analysisRequestId} workflowId="programming_ai_explain" /> : null}
          </section>
        ) : null}
      </Panel>

      <details className="mt-6">
        <summary className="cursor-pointer text-body font-medium text-text-primary">
          高级工作流：Debug Agent（多步诊断与修补，逐步结算）
        </summary>
        <div className="mt-4">
          <DebugAgentSurface exerciseId={exerciseId} code={code} onApply={setCode} />
        </div>
      </details>
    </div>
  );
}

/* ------------------------------------------------------------------ records / state / plan / errors */

export function RecordsPage({ language }: { language: string }) {
  const records = useProgrammingRecords();
  const summary = useProgrammingRecordsSummary();
  const events = rows(records.data);
  return (
    <ProgrammingShell
      language={language}
      active="records"
      facts={records.isSuccess ? `${events.length} 条记录` : null}
    >
      <PageHeader
        eyebrow="记录"
        title="编程学习记录"
        description="运行、测试、提交与 Debug Agent 都记为真实事件。"
        actions={
          <Link
            to="/reports"
            search={{ space: 'programming', courseId: undefined, module: undefined, language }}
            className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft"
          >
            查看学习报告
          </Link>
        }
      />

      <section className="mt-8">
        <SectionHeading title="记录统计" as="h2" description="统计窗口与口径由后端给出；缺失的指标显示为「—」。" />
        {summary.isPending ? <LoadingState label="正在读取记录统计…" className="mt-3" rows={2} /> : null}
        {summary.isError ? (
          <StatusNote tone="danger" className="mt-3">
            记录统计暂时无法加载。
          </StatusNote>
        ) : null}
        {summary.data !== undefined ? <FactList className="mt-4" value={summary.data} /> : null}
      </section>

      <section className="mt-10">
        <SectionHeading title="记录明细" as="h2" />
        {records.isPending ? (
          <LoadingState label="正在读取记录…" className="mt-3" />
        ) : records.isError ? (
          <StatusNote tone="danger" className="mt-3">
            记录暂时无法加载。
          </StatusNote>
        ) : events.length ? (
          <ol className="mt-4 space-y-4">
            {events.map((event, index) => (
              <li key={String(event.event_id ?? index)} className="border-l-2 border-border-default pl-4">
                <p className="text-body text-text-primary">
                  {eventTypeLabel(text(event.event_type) ?? '')}
                </p>
                <p className="mt-1 text-metadata text-text-secondary">
                  {formatDateTime(text(event.occurred_at))}
                </p>
                <FactList
                  className="mt-2"
                  columns={2}
                  value={event.summary}
                  allow={['correct', 'score', 'passed_count', 'total_count', 'exit_code', 'timed_out']}
                />
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState
            className="mt-4"
            title="还没有编程学习记录。"
            description="运行、测试或提交一次练习后，这里会出现真实事件。"
            action={
              <Button asChild variant="secondary">
                <Link to="/programming/$language" params={{ language }}>
                  回到练习
                </Link>
              </Button>
            }
          />
        )}
      </section>
    </ProgrammingShell>
  );
}

export function StatePage({ language }: { language: string }) {
  const query = useProgrammingState();
  return (
    <ProgrammingShell language={language} active="state">
      <PageHeader
        eyebrow="学习状态"
        title="已记录的学习事实"
        description="只呈现后端存储的事实与计数；不含熟练度、能力评分或 readiness 判断。"
        actions={
          <Link
            to="/reports"
            search={{ space: 'programming', courseId: undefined, module: undefined, language }}
            className="inline-flex h-11 items-center rounded-control border border-border-default bg-surface px-5 text-body font-medium text-text-primary hover:bg-primary-soft"
          >
            查看学习报告
          </Link>
        }
      />

      {query.isPending ? (
        <LoadingState label="正在读取状态…" className="mt-8" />
      ) : query.isError ? (
        <StatusNote tone="danger" className="mt-8">
          状态暂时无法加载。
        </StatusNote>
      ) : (
        <FactList className="mt-8" value={query.data} />
      )}
    </ProgrammingShell>
  );
}

export function PlanPage({ language }: { language: string }) {
  const canonical = canonicalLanguage(language);
  const activeLanguage = canonical ?? language;
  const query = useProgrammingPlan(activeLanguage);
  return (
    <ProgrammingShell language={language} active="plan">
      <PageHeader
        eyebrow="计划"
        title="学习计划"
        description="计划来自后端；调整建议需要你确认后才会生效。"
      />
      {query.isPending ? (
        <LoadingState label="正在读取计划…" className="mt-8" />
      ) : query.isError ? (
        <StatusNote tone="warning" className="mt-8">
          计划暂时不可用；该能力可能需要升级。
        </StatusNote>
      ) : (
        <FactList className="mt-8" value={query.data} />
      )}
      <DynamicPlanSurface
        scope={{ service_key: 'programming', course_id: '', exam_module_id: '', language: activeLanguage }}
      />
    </ProgrammingShell>
  );
}

export function ErrorsPage({ language }: { language: string }) {
  return (
    <ProgrammingShell language={language} active="errors">
      <PageHeader
        eyebrow="错误与待处理"
        title="错误复盘"
        description="复盘材料来自真实运行结果：运行与测试输出、编译器的诊断结论，以及 AI 分析与 Debug Agent 的返回。"
      />

      <EmptyState
        className="mt-8"
        title="这里不聚合跨接口的错误清单。"
        description="错误复盘在发生它的地方进行：Workbench 的执行反馈里有真实 stderr 与测试结果，代码诊断里有编译器的行列与结论。这里不跨接口猜测题面或错误原因。"
        action={
          <Button asChild variant="secondary">
            <Link to="/programming/$language" params={{ language }}>
              回到练习
            </Link>
          </Button>
        }
      />

      <section className="mt-10">
        <SectionHeading
          title="需要帮忙时"
          as="h2"
          description="三个辅助层的差别：编译器、单次 AI 调用、多步工作流。"
        />
        <ul className="mt-4 space-y-3">
          <li className="text-body text-text-secondary">
            <span className="text-text-primary">代码诊断</span>：由编译器等确定性工具完成，不调用模型、不消耗额度。
          </li>
          <li className="text-body text-text-secondary">
            <span className="text-text-primary">AI Debug</span>：一次真实 AI 调用，会消耗额度，回答下方可以评价这次分析是否有帮助。
          </li>
          <li className="text-body text-text-secondary">
            <span className="text-text-primary">Debug Agent</span>：有边界的多步工作流，每步单独结算；结果只作用于编辑器缓冲区。
          </li>
        </ul>
      </section>
    </ProgrammingShell>
  );
}
