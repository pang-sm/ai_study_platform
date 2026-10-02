import { useId, useState } from 'react';
import { cn } from '@/lib/utils';
import { eventTypeLabel } from '@/features/records/event-labels';
import { formatDateTime } from '@/lib/format';
import { numberField, stringField } from './workbench-model';

type PanelTab = 'tests' | 'console' | 'records';

const TABS: ReadonlyArray<{ id: PanelTab; label: string }> = [
  { id: 'tests', label: '测试结果' },
  { id: 'console', label: '控制台' },
  { id: 'records', label: '提交记录' },
];

function rows(value: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(value)) return value.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null);
  return [];
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

/**
 * 测试结果 · 控制台 · 提交记录 — the three answers a run/test/submit produces.
 *
 * They share one strip because they are one gesture apart, and each shows only what the backend
 * actually returned: the test cases the judge executed, the stdout/stderr the runtime produced,
 * and the submission facts the records stream and the progress row hold. Nothing here is
 * summarised into a score, and a tab with nothing in it says so rather than showing a zero.
 */
export function BottomPanel({
  testResult,
  runResult,
  stdin,
  onStdinChange,
  records,
  progress,
  isBusy,
  disabled,
}: {
  testResult: unknown;
  runResult: unknown;
  stdin: string;
  onStdinChange: (value: string) => void;
  /** This exercise's own submissions, newest first, read off the canonical records stream. */
  records: ReadonlyArray<Record<string, unknown>>;
  /** The open exercise's `personal_progress`, which always holds its LAST submission. */
  progress: Record<string, unknown> | undefined;
  isBusy: boolean;
  disabled: boolean;
}) {
  const [tab, setTab] = useState<PanelTab>('tests');
  const baseId = useId();
  const panelId = (id: PanelTab) => `${baseId}-${id}`;

  return (
    <section aria-label="运行与提交结果">
      <div className="wb-panel__tabs" role="tablist" aria-label="运行与提交结果">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            id={`${baseId}-tab-${entry.id}`}
            aria-selected={tab === entry.id}
            aria-controls={panelId(entry.id)}
            tabIndex={tab === entry.id ? 0 : -1}
            onClick={() => setTab(entry.id)}
            onKeyDown={(event) => {
              if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
              event.preventDefault();
              const index = TABS.findIndex((candidate) => candidate.id === tab);
              const next = event.key === 'ArrowRight' ? (index + 1) % TABS.length : (index - 1 + TABS.length) % TABS.length;
              const target = TABS[next];
              if (target) setTab(target.id);
            }}
            className="wb-panel__tab"
          >
            {entry.label}
            {entry.id === 'records' && records.length ? (
              <span className="wb-panel__badge">{records.length}</span>
            ) : null}
          </button>
        ))}
      </div>

      <div
        className="wb-panel__body"
        role="tabpanel"
        id={panelId(tab)}
        aria-labelledby={`${baseId}-tab-${tab}`}
        tabIndex={0}
      >
        {disabled ? (
          <p className="text-body text-text-secondary">打开一道题目后，这里会显示运行、测试与提交的真实结果。</p>
        ) : tab === 'tests' ? (
          <TestPanel result={testResult} isBusy={isBusy} />
        ) : tab === 'console' ? (
          <ConsolePanel result={runResult} stdin={stdin} onStdinChange={onStdinChange} isBusy={isBusy} />
        ) : (
          <RecordsPanel records={records} progress={progress} />
        )}
      </div>
    </section>
  );
}

function TestPanel({ result, isBusy }: { result: unknown; isBusy: boolean }) {
  const summary = stringField(result, 'summary');
  const total = numberField(result, 'total_count');
  const passed = numberField(result, 'passed_count');
  const cases = rows((result as Record<string, unknown> | undefined)?.cases);
  const exited = result !== undefined && result !== null;

  return (
    <div>
      {isBusy ? <p className="text-body text-text-secondary">正在运行测试…</p> : null}
      {!exited && !isBusy ? (
        <p className="text-body text-text-secondary">
          点击上方「运行测试」，这里会显示每个公开样例的真实通过情况。
        </p>
      ) : null}
      {exited ? (
        <>
          <p className="text-body text-text-primary">
            测试结果：
            {total !== undefined && passed !== undefined ? `通过 ${passed} / ${total}` : (summary ?? '已返回结果')}
          </p>
          {cases.length ? (
            <ul className="wb-cases mt-3">
              {cases.map((entry, index) => {
                const ok = entry.passed === true || entry.status === 'passed';
                const expected = stringField(entry, 'expected_stdout');
                const actual = stringField(entry, 'actual_stdout');
                const stderr = stringField(entry, 'stderr');
                const reason = stringField(entry, 'reason');
                const name = stringField(entry, 'case_name') ?? `样例 ${index + 1}`;
                return (
                  <li key={stringField(entry, 'case_id') ?? index} className={cn('wb-case', ok ? 'wb-case--passed' : 'wb-case--failed')}>
                    <div className="wb-case__head">
                      <span className="wb-case__name">{name}</span>
                      <span className={cn('text-metadata font-medium', ok ? 'text-success-ink' : 'text-danger-ink')}>
                        {ok ? '通过' : '未通过'}
                      </span>
                    </div>
                    {!ok ? (
                      <div className="wb-case__io">
                        {stringField(entry, 'input') ? (
                          <div>
                            <p className="wb-sample__label">输入</p>
                            <pre className="wb-sample__value">{stringField(entry, 'input')}</pre>
                          </div>
                        ) : null}
                        {expected ? (
                          <div>
                            <p className="wb-sample__label">期望输出</p>
                            <pre className="wb-sample__value">{expected}</pre>
                          </div>
                        ) : null}
                        {actual ? (
                          <div>
                            <p className="wb-sample__label">实际输出</p>
                            <pre className="wb-sample__value">{actual}</pre>
                          </div>
                        ) : null}
                        {stderr ? <pre className="wb-console wb-console--error">{stderr}</pre> : null}
                        {reason ? <p className="mt-1 text-metadata text-text-secondary">{reason}</p> : null}
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function ConsolePanel({
  result,
  stdin,
  onStdinChange,
  isBusy,
}: {
  result: unknown;
  stdin: string;
  onStdinChange: (value: string) => void;
  isBusy: boolean;
}) {
  const stdout = stringField(result, 'stdout') ?? stringField(result, 'actual_stdout');
  const stderr = stringField(result, 'stderr');
  const compileError = stringField(result, 'compile_error');
  const exitCode = numberField(result, 'exit_code');
  const timedOut = (result as Record<string, unknown> | undefined)?.timed_out === true;
  const errorMessage = stringField(result, 'error_message');
  const exited = result !== undefined && result !== null;

  return (
    <div>
      <label htmlFor="wb-stdin" className="wb-sample__label block">
        标准输入（运行时会作为程序的输入）
      </label>
      <textarea
        id="wb-stdin"
        value={stdin}
        onChange={(event) => onStdinChange(event.target.value)}
        rows={3}
        spellCheck={false}
        placeholder="需要输入的题目在这里填写"
        className="mt-1 w-full rounded-control border border-border-default bg-surface p-2 font-mono text-metadata text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1"
      />

      <div className="mt-3">
        {isBusy ? <p className="text-body text-text-secondary">正在运行…</p> : null}
        {!exited && !isBusy ? (
          <p className="text-body text-text-secondary">点击上方「运行」，程序的标准输出与错误会显示在这里。</p>
        ) : null}
        {exited ? (
          <>
            {exitCode !== undefined || timedOut ? (
              <p className="text-metadata text-text-secondary">
                退出码：{exitCode ?? '—'}
                {timedOut ? ' · 执行超时' : ''}
              </p>
            ) : null}
            {stdout ? <pre className="wb-console mt-2">stdout{`\n`}{stdout}</pre> : null}
            {stderr ? <pre className="wb-console wb-console--error mt-2">stderr{`\n`}{stderr}</pre> : null}
            {compileError ? <pre className="wb-console wb-console--error mt-2">编译错误{`\n`}{compileError}</pre> : null}
            {errorMessage ? <pre className="wb-console wb-console--error mt-2">运行错误{`\n`}{errorMessage}</pre> : null}
            {!stdout && !stderr && !compileError && !errorMessage ? (
              <p className="mt-2 text-body text-text-secondary">本次运行没有产生输出。</p>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function RecordsPanel({
  records,
  progress,
}: {
  records: ReadonlyArray<Record<string, unknown>>;
  progress: Record<string, unknown> | undefined;
}) {
  const lastSubmitAt = text(progress?.last_submit_at);
  const lastPassed = progress?.last_submit_passed;
  const passedCount = numberField(progress, 'last_public_passed_count');
  const totalCount = numberField(progress, 'last_public_total_count');

  return (
    <div>
      {lastSubmitAt ? (
        <p className="text-body text-text-primary">
          最近一次提交：{formatDateTime(lastSubmitAt)} · {lastPassed === true ? '通过' : '未通过'}
          {totalCount !== undefined ? `（通过 ${passedCount ?? 0} / ${totalCount} 个公开样例）` : ''}
        </p>
      ) : (
        <p className="text-body text-text-secondary">这道题还没有提交记录。提交之后，这里会出现真实的提交事实。</p>
      )}

      {records.length ? (
        <ul className="wb-records mt-3">
          {records.map((entry, index) => {
            const context = typeof entry.context === 'object' && entry.context !== null ? (entry.context as Record<string, unknown>) : {};
            const summary = typeof entry.summary === 'object' && entry.summary !== null ? (entry.summary as Record<string, unknown>) : {};
            const correct = summary.correct;
            return (
              <li key={stringField(entry, 'event_id') ?? index} className="wb-records__row">
                <span className="wb-records__time">{formatDateTime(stringField(entry, 'occurred_at'))}</span>
                <span className="text-metadata text-text-secondary">
                  {eventTypeLabel(stringField(entry, 'event_type') ?? '')}
                  {typeof correct === 'boolean' ? ` · ${correct ? '通过' : '未通过'}` : ''}
                  {text(context.programming_language) ? ` · ${text(context.programming_language)}` : ''}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
