import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Panel } from '@/components/ui/panel';
import { SectionHeading } from '@/components/ui/section-heading';
import { StatusNote } from '@/components/ui/status-note';
import { FactList } from '@/components/page/fact-list';
import { PageHeader } from '@/components/page/page-header';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { eventTypeLabel } from '@/features/records/event-labels';
import { useApplyPlanProposal, useLearningReport, usePlanProposal, useWrongAnalysis, type LearningReport, type PlanProposal, type WrongAnalysis } from './api';
import { safeActionHref, type LearningScope } from './presentation';
import { AiFeedback } from '@/components/learning/ai-feedback';
import { REASON_LABELS, originLabel } from '@/lib/fact-labels';
import { usageCreditsText, vocabularyText } from '@/lib/learner-safe';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** The report's six metric blocks, in the order a learner reads them. */
const REPORT_BLOCKS: ReadonlyArray<{ key: string; label: string; note: string }> = [
  { key: 'activity', label: '学习活动', note: '本周期内产生的事件与学习天数' },
  { key: 'practice', label: '练习', note: '提交过的练习及其判分结果' },
  { key: 'review', label: '复习', note: '待复习与已安排的复习项' },
  { key: 'plan', label: '计划', note: '计划任务的完成情况' },
  { key: 'materials', label: '资料', note: '资料的打开与提问' },
  { key: 'programming', label: '编程', note: '运行、测试与提交的次数' },
];

function FailureCopy({ error, unavailable = false }: { error: unknown; unavailable?: boolean }) {
  const status = error instanceof ApiRequestError ? error.status : undefined;
  const message =
    unavailable && status === 409
      ? '题面内容未能由后端证明，深度分析不可用。'
      : status === 403
        ? '该能力当前不可用，需要相应权限。'
        : status === 429
          ? '本次额度不足，未发起请求。'
          : '请求暂时不可用，请稍后重试。';
  return (
    <StatusNote tone="danger" className="mt-3">
      {message}
    </StatusNote>
  );
}

/* ------------------------------------------------------------------ learning report */

export function LearningReportSurface({ scope }: { scope: LearningScope }) {
  const report = useLearningReport();
  const [includeNarrative, setIncludeNarrative] = useState(false);
  const data = report.data;

  return (
    <div className="mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
      <PageHeader
        eyebrow="共享学习核心"
        title="学习报告"
        description="结构化指标由已记录的学习事实计算，先于 AI 叙述；两部分分开呈现，不会混在一起。"
      />

      <div className="mt-6 flex flex-wrap items-center gap-5">
        <label className="inline-flex items-center gap-2 text-body text-text-primary">
          <input
            type="checkbox"
            checked={includeNarrative}
            onChange={(event) => setIncludeNarrative(event.target.checked)}
          />
          包含 AI 叙述（会消耗额度）
        </label>
        <Button
          disabled={report.isPending}
          onClick={() => report.mutate({ scope, includeNarrative })}
        >
          {report.isPending ? '正在生成…' : '生成学习报告'}
        </Button>
      </div>

      {report.isError ? <FailureCopy error={report.error} /> : null}

      {data ? (
        <ReportResult report={data} />
      ) : (
        <EmptyState
          className="mt-8"
          title="选择「生成学习报告」后查看当前上下文的学习事实。"
          description="报告只读取当前学习空间里已经记录的事件、练习、复习与计划。"
        />
      )}
    </div>
  );
}

function InsightList({ title, items }: { title: string; items: Array<Record<string, unknown>> }) {
  return (
    <section>
      <h3 className="text-metadata font-medium tracking-eyebrow text-text-muted">{title}</h3>
      {items.length ? (
        <ul className="mt-3 space-y-4">
          {items.map((item, index) => {
            const text = typeof item.text === 'string' ? item.text : undefined;
            const origin = typeof item.origin === 'string' ? item.origin : undefined;
            const href = safeActionHref(item);
            return (
              <li key={`${String(item.rule ?? 'item')}-${index}`} className="border-l-2 border-border-default pl-4">
                <p className="text-body text-text-primary">{text ?? '后端未返回可显示的要点。'}</p>
                {origin ? (
                  <p className="mt-1 text-metadata text-text-secondary">
                    来源：{originLabel(origin) ?? '后端规则'}
                  </p>
                ) : null}
                {href ? (
                  <Link
                    to={href as '/review'}
                    className="mt-2 inline-block text-body text-primary-ink underline hover:text-primary-hover"
                  >
                    {typeof item.action_label === 'string' ? item.action_label : '查看关联学习项'}
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-3 text-body text-text-secondary">本周期没有触发这类规则。</p>
      )}
    </section>
  );
}

function EventTypeFacts({ value }: { value: unknown }) {
  if (!isRecord(value)) return null;
  const entries = Object.entries(value).filter(([, count]) => typeof count === 'number');
  if (!entries.length) return null;
  return (
    <ul className="mt-2 space-y-1">
      {entries.map(([eventType, count]) => (
        <li key={eventType} className="flex items-baseline justify-between gap-4 text-body">
          <span className="text-text-secondary">{eventTypeLabel(eventType)}</span>
          <span className="tabular-nums text-text-primary">{String(count)}</span>
        </li>
      ))}
    </ul>
  );
}

function ReportResult({ report }: { report: LearningReport }) {
  const coverage = isRecord(report.data_coverage) ? report.data_coverage : undefined;
  const available = coverage && Array.isArray(coverage.available_blocks) ? (coverage.available_blocks as unknown[]) : [];
  const unavailable = coverage && Array.isArray(coverage.unavailable) ? (coverage.unavailable as Array<Record<string, unknown>>) : [];
  const recent = coverage && Array.isArray(coverage.recent_events) ? (coverage.recent_events as Array<Record<string, unknown>>) : [];
  const metrics = isRecord(report.structured_metrics) ? report.structured_metrics : {};
  const narrativeUsage = usageCreditsText(report.narrative?.usage);

  return (
    <div className="mt-10 space-y-12">
      <section>
        <SectionHeading title="统计周期" as="h2" />
        <FactList className="mt-4" value={report.report_period} />
      </section>

      <section>
        <SectionHeading
          title="结构化指标"
          as="h2"
          description="每个数字都由后端按已记录的事实计算；本学习空间没有的数据块显示为「—」，不会写成 0。"
        />
        <div className="mt-5 space-y-6">
          {REPORT_BLOCKS.map((block) => {
            const value = metrics[block.key];
            return (
              <section key={block.key} className="border-t border-border-default pt-4">
                <h3 className="text-heading font-semibold text-text-primary">{block.label}</h3>
                <p className="mt-1 text-metadata text-text-secondary">{block.note}</p>
                {value === null || value === undefined ? (
                  <p className="mt-3 text-body text-text-secondary">本学习空间没有这类数据。</p>
                ) : (
                  <>
                    <FactList className="mt-3" value={value} />
                    {isRecord(value) && value.by_event_type ? (
                      <div className="mt-3">
                        <p className="text-metadata text-text-secondary">按事件类型</p>
                        <EventTypeFacts value={value.by_event_type} />
                      </div>
                    ) : null}
                  </>
                )}
              </section>
            );
          })}
        </div>
      </section>

      <section>
        <SectionHeading
          title="确定性要点"
          as="h2"
          description="由命名规则从上面的指标得出，每条都标明来源。"
        />
        <div className="mt-5 grid gap-8 lg:grid-cols-2">
          <InsightList title="本周期做成了什么" items={report.highlights ?? []} />
          <InsightList title="需要注意什么" items={report.attention_items ?? []} />
        </div>
      </section>

      <section>
        <SectionHeading title="AI 叙述" as="h2" description="这是报告里唯一由模型生成的部分，不是对能力的确定性判断。" />
        {report.narrative ? (
          <Panel tone="ai" className="mt-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ai">AI 生成</Badge>
              <span className="text-metadata text-text-secondary">
                来源：{originLabel(report.narrative.origin) ?? 'AI 生成'}
              </span>
            </div>
            <p className="mt-4 whitespace-pre-wrap text-body text-text-primary">{report.narrative.text}</p>
            {narrativeUsage ? (
              <p className="mt-3 text-metadata text-text-secondary">{narrativeUsage}</p>
            ) : null}
            <AiFeedback requestId={report.narrative.request_id} workflowId={report.report_id} />
          </Panel>
        ) : (
          <div className="mt-5">
            <StatusNote tone="info">
              {report.narrative_error
                ? '本次没有生成 AI 叙述；报告的结构化部分不受影响。'
                : '未请求 AI 叙述。'}
            </StatusNote>
          </div>
        )}
      </section>

      <section>
        <SectionHeading title="数据覆盖" as="h2" description="报告能覆盖哪些数据块，以及没有哪些。" />
        <div className="mt-4 space-y-3">
          {available.length ? (
            <p className="text-body text-text-secondary">
              本次可用：
              {available
                .map((block) => REPORT_BLOCKS.find((entry) => entry.key === block)?.label ?? '其他数据块')
                .join('、')}
            </p>
          ) : null}
          {unavailable.length ? (
            <div>
              <p className="text-body text-text-secondary">本学习空间没有：</p>
              <ul className="mt-2 space-y-1">
                {unavailable.map((entry, index) => (
                  <li key={index} className="text-body text-text-primary">
                    {REPORT_BLOCKS.find((block) => block.key === entry.block)?.label ?? '其他数据块'}
                    {typeof entry.reason === 'string'
                      ? ` · ${vocabularyText(REASON_LABELS, entry.reason, '原因未说明')}`
                      : ''}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <h3 className="mt-6 text-metadata font-medium tracking-eyebrow text-text-muted">最近学习事件</h3>
        {recent.length ? (
          <ol className="mt-3 border-t border-border-default">
            {recent.map((event, index) => (
              <li key={String(event.event_id ?? index)} className="border-b border-border-default py-3">
                <p className="text-body text-text-primary">
                  {eventTypeLabel(typeof event.event_type === 'string' ? event.event_type : '')}
                </p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-3 text-body text-text-secondary">本周期没有记录到事件。</p>
        )}
      </section>

      <p className="text-metadata text-text-secondary">生成时间：{report.generated_at}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ wrong-answer analysis */

export function WrongAnalysisSurface({ stateId, sourceProven }: { stateId: number | undefined; sourceProven: boolean }) {
  const analysis = useWrongAnalysis();
  const disabled = !stateId || !sourceProven || analysis.isPending;
  return (
    <section className="mt-5" aria-label="深度错因分析">
      <h3 className="text-metadata font-medium tracking-eyebrow text-text-muted">深度错因分析（AI，单次调用）</h3>
      <p className="mt-2 max-w-prose text-body text-text-secondary">
        作答事实先于 AI 解释显示；AI 的解释不是对能力的确定性判断。
      </p>
      <div className="mt-3">
        <Button
          variant="secondary"
          disabled={disabled}
          title={!sourceProven ? '题面内容不可证明，无法安全分析' : undefined}
          onClick={() => stateId && analysis.mutate(stateId)}
        >
          {analysis.isPending ? '正在分析…' : '分析这道错题'}
        </Button>
      </div>
      {!sourceProven ? (
        <p className="mt-2 text-metadata text-text-secondary">题面内容不可证明，因此不发起分析。</p>
      ) : null}
      {analysis.isError ? <FailureCopy error={analysis.error} unavailable /> : null}
      {analysis.data ? <WrongAnalysisResultView result={analysis.data} /> : null}
    </section>
  );
}

function WrongAnalysisResultView({ result }: { result: WrongAnalysis }) {
  const facts = result.facts;
  return (
    <div className="mt-5 space-y-5">
      <Panel tone="plain" labelledBy="wrong-facts-title">
        <p className="text-metadata font-medium tracking-eyebrow text-text-muted">
          事实 · {originLabel(result.fact_origin) ?? '后端记录'}
        </p>
        <h4 id="wrong-facts-title" className="mt-1 text-heading font-semibold text-text-primary">
          作答事实
        </h4>
        <FactList
          className="mt-3"
          value={{
            question: facts.question,
            user_answer: facts.user_answer,
            wrong_count: facts.wrong_count,
            state_status: facts.state_status,
            first_wrong_at: facts.first_wrong_at,
            last_wrong_at: facts.last_wrong_at,
          }}
          columns={1}
        />
      </Panel>

      <Panel tone="ai" labelledBy="wrong-analysis-title">
        <p className="text-metadata font-medium tracking-eyebrow text-ai-ink">
          AI 分析 · {originLabel(result.analysis_origin) ?? 'AI 生成'}
        </p>
        <h4 id="wrong-analysis-title" className="mt-1 text-heading font-semibold text-text-primary">
          AI 对错因的解释
        </h4>
        <FactList className="mt-3" value={result.analysis} columns={1} />
        <p className="mt-3 text-metadata text-text-secondary">
          AI 的解释不是对能力的确定性判断，也不写入学习事实。
        </p>
        <AiFeedback requestId={result.request_id} workflowId={`wrong-analysis-${result.state_id}`} />
      </Panel>

      <p className="text-metadata text-text-secondary">生成时间：{result.generated_at}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ plan adjustment */

export function DynamicPlanSurface({ scope }: { scope: LearningScope }) {
  const proposalMutation = usePlanProposal();
  const apply = useApplyPlanProposal(scope);
  const [goal, setGoal] = useState('');
  const [proposal, setProposal] = useState<PlanProposal>();
  const [stale, setStale] = useState(false);

  const generate = () => {
    setStale(false);
    proposalMutation.mutate({ scope, goal }, { onSuccess: setProposal });
  };
  const accept = () =>
    proposal &&
    apply.mutate(proposal, {
      onError: (error) => {
        if (error instanceof ApiRequestError && error.status === 409) setStale(true);
      },
      onSuccess: () => setProposal(undefined),
    });

  return (
    <section className="mt-10 border-t border-border-default pt-8" aria-labelledby="dynamic-plan-title">
      <SectionHeading
        id="dynamic-plan-title"
        eyebrow="计划"
        title="调整计划"
        description="先生成建议，看清差异后再决定是否应用；生成建议本身不会改动当前计划。"
      />

      <label className="mt-5 block text-body font-medium text-text-primary" htmlFor="plan-adjustment-goal">
        本次想达成的目标（可留空）
      </label>
      <input
        id="plan-adjustment-goal"
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
        maxLength={300}
        className="mt-2 h-11 w-full rounded-control border border-border-default bg-surface px-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        placeholder="例如：这周把操作系统复习完"
      />
      <div className="mt-4">
        <Button
          variant="secondary"
          disabled={proposalMutation.isPending || apply.isPending}
          onClick={generate}
        >
          {proposalMutation.isPending ? '正在生成建议…' : '生成调整建议'}
        </Button>
      </div>

      {proposalMutation.isError ? <FailureCopy error={proposalMutation.error} /> : null}
      {stale ? (
        <StatusNote tone="danger" className="mt-4">
          计划已经变化，未应用旧建议。请重新生成建议后再决定。
        </StatusNote>
      ) : null}
      {apply.isError && !stale ? <FailureCopy error={apply.error} /> : null}
      {apply.isSuccess ? (
        <StatusNote tone="success" className="mt-4">
          已按你确认的建议应用 {apply.data.applied_count} 项调整；相关计划与学习事实正在刷新。
        </StatusNote>
      ) : null}

      {proposal ? <ProposalView proposal={proposal} onApply={accept} applying={apply.isPending} /> : null}
    </section>
  );
}

function ProposalView({ proposal, onApply, applying }: { proposal: PlanProposal; onApply: () => void; applying: boolean }) {
  const changes = proposal.proposed_changes ?? [];
  const usage = usageCreditsText(proposal.usage);
  return (
    <section className="mt-8" aria-label="计划调整建议">
      <h3 className="text-heading font-semibold text-text-primary">这次建议</h3>
      <p className="mt-2 max-w-prose text-body text-text-primary">{proposal.reason}</p>
      <p className="mt-2 text-metadata text-text-secondary">
        涉及任务：{proposal.affected_tasks?.length ? `${proposal.affected_tasks.length} 项` : '无'}
      </p>

      <div className="mt-5 grid gap-8 lg:grid-cols-2">
        <section>
          <h4 className="text-metadata font-medium tracking-eyebrow text-text-muted">当前计划</h4>
          <FactList className="mt-3" value={proposal.plan_snapshot} />
        </section>
        <section>
          <h4 className="text-metadata font-medium tracking-eyebrow text-text-muted">调整后（仅建议）</h4>
          {changes.length ? (
            <ol className="mt-3 space-y-4">
              {changes.map((change, index) => (
                <li key={`${String(change.op ?? 'change')}-${index}`} className="border-b border-border-default pb-3">
                  <FactList value={change} columns={1} />
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-body text-text-secondary">没有可应用的变更。</p>
          )}
        </section>
      </div>

      <p className="mt-4 text-metadata text-text-secondary">这份建议还没有成为当前的计划事实。</p>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <Button disabled={applying || changes.length === 0} onClick={onApply}>
          {applying ? '正在应用…' : '应用这次调整'}
        </Button>
        <AiFeedback requestId={proposal.request_id} workflowId={proposal.proposal_id} />
      </div>
      {usage ? <p className="mt-3 text-metadata text-text-secondary">{usage}</p> : null}
    </section>
  );
}
