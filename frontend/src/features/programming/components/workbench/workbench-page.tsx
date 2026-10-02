import { useMemo, useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { StatusNote } from '@/components/ui/status-note';
import { REASON_LABELS } from '@/components/learning/adaptive-practice';
import { useAdaptivePractice } from '@/components/learning/p4-api';
import {
  useExerciseWorkspace,
  useProgrammingExercise,
  useProgrammingExerciseBank,
  useProgrammingJudge,
  useProgrammingRecords,
  type JudgeAction,
} from '../../api/programming';
import { ProgrammingLanguagePicker } from '../programming-language-picker';
import { canonicalLanguage, normalizeLanguageSlug, programmingLanguages, type ProgrammingLanguageSlug } from '../../programming-language';
import { BottomPanel } from './bottom-panel';
import { CodeEditor } from './code-editor';
import { CoachPanel } from './coach-panel';
import { ExerciseNav, type RecommendedExercise } from './exercise-nav';
import { ExerciseStatement } from './exercise-statement';
import { judgeFailureMessage } from './judge-error';
import { readRailCollapsed, rememberRailCollapsed } from './workbench-preferences';
import {
  chapterOf,
  coachTestPayload,
  entryFileOf,
  exerciseIdOf,
  exerciseTitle,
  personalProgress,
  publicSampleIds,
  resumeExerciseId,
} from './workbench-model';
import './workbench.css';

function recordRows(data: unknown): Array<Record<string, unknown>> {
  if (typeof data !== 'object' || data === null) return [];
  const records = (data as Record<string, unknown>).records;
  if (!Array.isArray(records)) return [];
  return records.filter((entry): entry is Record<string, unknown> => typeof entry === 'object' && entry !== null);
}

function submittedForExercise(data: unknown, exerciseId: number | undefined): Array<Record<string, unknown>> {
  if (exerciseId === undefined) return [];
  return recordRows(data).filter((entry) => {
    const context = entry.context;
    if (typeof context !== 'object' || context === null) return false;
    return (context as Record<string, unknown>).exercise_id === exerciseId;
  });
}

/**
 * 编程工作台 — the programming space's whole working surface.
 *
 * The space's front door asks one question (which language) and this is what it opens: a
 * three-column workspace, in the shape of a desktop IDE. 左 = the language's bank as a
 * chapter-grouped题目导航; 中 = the题面, a real code editor and the results of what the learner
 * ran; 右 = the AI 教练, scoped to the exercise on screen. Switching题目 happens inside the
 * workspace — the rail selects, the centre swaps, the address records which题 is open so the view
 * can be shared and reloaded.
 *
 * Everything shown is a server fact: the bank's own product status, the project the backend keeps
 * for this learner and this exercise (which is both the starter code and their own draft), the
 * judge's own verdict, and the submission history off the canonical records stream. Nothing is
 * estimated — there is no score, no mastery, no recommendation for the learner to misread.
 */
export function WorkbenchPage({
  language,
  exerciseId,
}: {
  language: ProgrammingLanguageSlug | undefined;
  exerciseId: number | undefined;
}) {
  const navigate = useNavigate();
  const bank = useProgrammingExerciseBank(language ?? '');
  const items = useMemo(() => bank.data?.items ?? [], [bank.data]);

  // The题 to open: the one the address names, otherwise the learner's own most recent unfinished
  // exercise, otherwise the bank's first row. Deriving it keeps the URL honest — a题 nobody chose
  // is not written into the address as if they had.
  const currentId = exerciseId ?? resumeExerciseId(items);
  const detail = useProgrammingExercise(language ?? '', currentId);
  const workspace = useExerciseWorkspace(language ?? '', currentId);
  const records = useProgrammingRecords(200, 'code_submitted');
  const judge = useProgrammingJudge(language ?? '', currentId ?? 0);

  const [code, setCode] = useState('');
  const [stdin, setStdin] = useState('');
  const [runResult, setRunResult] = useState<unknown>();
  const [testResult, setTestResult] = useState<unknown>();
  // A device preference, read once on mount: the learner's own width choice for the题目栏.
  const [railCollapsed, setRailCollapsed] = useState(() => readRailCollapsed());
  const toggleRailCollapsed = () => {
    setRailCollapsed((current) => {
      const next = !current;
      rememberRailCollapsed(next);
      return next;
    });
  };

  const entry = workspace.data ? entryFileOf(workspace.data) : undefined;
  const workspaceKey = workspace.data ? `${language}:${currentId}` : undefined;

  // The buffer follows the OPEN PROJECT, and only that. This is the "adjust state when an input
  // changes" pattern rather than an effect: recording which project the buffer belongs to and
  // loading the new one during the same render means switching题目 never paints the previous题's
  // code. A run or a test cannot trigger it either — they invalidate the bank, never this read —
  // so nothing replaces what the learner is typing. A failed load leaves the editor empty rather
  // than showing another题's code.
  const [loadedKey, setLoadedKey] = useState<string | undefined>(undefined);
  if (workspaceKey !== loadedKey) {
    setLoadedKey(workspaceKey);
    setCode(entry ? entry.file.content : '');
    setRunResult(undefined);
    setTestResult(undefined);
    setStdin('');
  }

  const currentItem = items.find((item) => exerciseIdOf(item) === currentId);
  const ordered = useMemo(() => items.map(exerciseIdOf).filter((id): id is number => id !== undefined), [items]);
  const position = currentId === undefined ? -1 : ordered.indexOf(currentId);
  const previousId = position > 0 ? ordered[position - 1] : undefined;
  const nextId = position >= 0 && position < ordered.length - 1 ? ordered[position + 1] : undefined;

  const canonical = language ? canonicalLanguage(language) : undefined;
  const publicCases = useMemo(() => publicSampleIds(detail.data), [detail.data]);
  const progress = currentItem ? personalProgress(currentItem) : undefined;
  const exerciseRecords = useMemo(
    () => submittedForExercise(records.data, currentId),
    [records.data, currentId],
  );

  // The deterministic recommendation the space has always had, kept inside the rail as its top
  // group: it is a way of choosing WHICH题 to open, which is the rail's own job. It is optional —
  // a read that fails leaves the rail as the plain bank.
  const adaptive = useAdaptivePractice({ serviceKey: 'programming', language: canonical ?? '' });
  const recommended = useMemo<RecommendedExercise[]>(() => {
    const candidates = adaptive.data?.candidates ?? [];
    return candidates
      .flatMap((candidate): RecommendedExercise[] => {
        const id = Number(candidate.question_source_id);
        if (!Number.isFinite(id) || id <= 0) return [];
        return [{
          id,
          label: candidate.label || `练习 #${id}`,
          reason: REASON_LABELS[candidate.reason] ?? '推荐练习',
          note: candidate.difficulty ?? undefined,
        }];
      })
      .slice(0, 3);
  }, [adaptive.data]);

  const canRun = Boolean(workspace.data) && !judge.isPending;

  const openExercise = (id: number) => {
    if (!language) return;
    void navigate({ to: '/programming/workbench', search: { language, exercise: id } as never });
  };

  const runAction = (action: JudgeAction) => {
    if (!workspace.data || currentId === undefined) return;
    judge.mutate(
      {
        action,
        projectId: workspace.data.project.id,
        entryFileId: entry?.file.id,
        code,
        stdin,
        entryFile: workspace.data.project.entry_file,
        mainClass: workspace.data.project.main_class ?? null,
        publicCaseIds: publicCases,
      },
      {
        onSuccess: (data) => {
          if (action === 'run') setRunResult(data);
          else setTestResult(data);
        },
      },
    );
  };

  if (!language) {
    return (
      <div className="space-accent space-accent--programming mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
        <ProgrammingLanguagePicker
          heading="选择编程语言"
          description="工作台按语言分开：每一门语言有自己的题目、编辑器与运行环境。选择一门即可开始。"
        />
      </div>
    );
  }

  return (
    <div className="wb space-accent space-accent--programming">
      <header className="wb__bar">
        <label htmlFor="wb-language" className="sr-only">
          切换编程语言
        </label>
        <select
          id="wb-language"
          value={language}
          onChange={(event) => {
            const next = normalizeLanguageSlug(event.target.value);
            if (!next || next === language) return;
            // A题 belongs to one language's bank, so switching language opens that language's
            // workspace without carrying an id that means nothing there.
            void navigate({ to: '/programming/workbench', search: { language: next } as never });
          }}
          className="wb__lang"
        >
          {(Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, string]>).map(([slug, label]) => (
            <option key={slug} value={slug}>
              {label}
            </option>
          ))}
        </select>

        <span className="wb__bar-sep" aria-hidden="true" />
        <div className="wb__crumb">
          {currentItem ? (
            <>
              <span className="wb__crumb-chapter">{chapterOf(currentItem)}</span>
              <span aria-hidden="true">/</span>
              <span className="wb__crumb-title">{exerciseTitle(currentItem, '练习题')}</span>
            </>
          ) : (
            <span className="wb__crumb-chapter">{canonical} 工作台</span>
          )}
        </div>

        <div className="wb__bar-actions">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={previousId === undefined}
            onClick={() => previousId !== undefined && openExercise(previousId)}
          >
            <ChevronLeft className="size-4" aria-hidden="true" />
            上一题
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={nextId === undefined}
            onClick={() => nextId !== undefined && openExercise(nextId)}
          >
            下一题
            <ChevronRight className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </header>

      <div className={cn('wb__body', railCollapsed && 'wb__body--rail-collapsed')}>
        <nav className={cn('wb__col wb__nav', railCollapsed && 'wb__nav--collapsed')} aria-label="题目导航">
          <ExerciseNav
            items={items}
            total={bank.data?.total ?? 0}
            statusCounts={bank.data?.statusCounts ?? {}}
            currentId={currentId}
            onSelect={openExercise}
            isPending={bank.isPending}
            isError={bank.isError}
            recommended={recommended}
            collapsed={railCollapsed}
            onToggleCollapsed={toggleRailCollapsed}
          />
        </nav>

        <main className="wb__col wb__main">
          <div className="wb-main__section">
            {detail.isPending ? (
              <p className="text-body text-text-secondary" role="status">
                正在读取题目…
              </p>
            ) : detail.isError ? (
              <StatusNote tone="danger">
                题目暂时无法加载。
                <button type="button" className="ml-3 underline" onClick={() => void detail.refetch()}>
                  重试
                </button>
              </StatusNote>
            ) : currentItem || currentId !== undefined ? (
              <ExerciseStatement payload={detail.data} />
            ) : (
              <p className="text-body text-text-secondary">这门语言目前没有可练习的题目。</p>
            )}
          </div>

          <div className="wb-main__section">
            <div className="wb-editor__head">
              <h2 className="text-heading font-semibold text-text-primary">代码</h2>
              {entry ? <span className="wb-editor__file">{entry.file.relative_path}</span> : null}
              <div className="wb-editor__actions">
                <Button type="button" size="sm" variant="secondary" disabled={!canRun} onClick={() => runAction('run')}>
                  {judge.isPending && judge.variables?.action === 'run' ? '正在运行…' : '运行'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={!canRun || publicCases.length === 0}
                  onClick={() => runAction('test')}
                >
                  {judge.isPending && judge.variables?.action === 'test' ? '正在测试…' : '运行测试'}
                </Button>
                <Button type="button" size="sm" disabled={!canRun} onClick={() => runAction('submit')}>
                  {judge.isPending && judge.variables?.action === 'submit' ? '正在提交…' : '提交'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={!entry || entry.starter === undefined}
                  onClick={() => entry?.starter !== undefined && setCode(entry.starter)}
                >
                  重置代码
                </Button>
              </div>
            </div>

            {workspace.isPending ? (
              <div className="wb-editor__shell wb-editor__loading" role="status">
                正在准备这道题的代码…
              </div>
            ) : workspace.isError ? (
              <StatusNote tone="danger" className="mt-3">
                这道题的代码环境暂时无法打开，因此无法运行或提交。
                <button type="button" className="ml-3 underline" onClick={() => void workspace.refetch()}>
                  重试
                </button>
              </StatusNote>
            ) : (
              <div className="wb-editor__shell">
                <CodeEditor
                  language={language}
                  value={code}
                  onChange={setCode}
                  ariaLabel={`${canonical ?? ''} 代码编辑器`}
                />
              </div>
            )}

            {judge.isError ? (
              <StatusNote tone="warning" className="mt-3">
                {judgeFailureMessage(judge.error) ?? '这次操作没有成功；代码已保存在这道题的练习里，可以稍后重试。'}
              </StatusNote>
            ) : null}
          </div>

          <div className="wb-main__section">
            <BottomPanel
              testResult={testResult}
              runResult={runResult}
              stdin={stdin}
              onStdinChange={setStdin}
              records={exerciseRecords}
              progress={progress}
              isBusy={judge.isPending}
              disabled={!workspace.data}
            />
          </div>
        </main>

        <aside className="wb__col wb__coach" aria-label="AI 教练">
          <CoachPanel
            language={canonical ?? ''}
            exerciseId={currentId}
            exerciseTitle={currentItem ? exerciseTitle(currentItem, '') : undefined}
            code={code}
            lastRun={runResult as Record<string, unknown> | undefined}
            lastTest={coachTestPayload(testResult)}
            disabled={currentId === undefined}
          />
        </aside>
      </div>
    </div>
  );
}
