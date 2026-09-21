import { useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Panel } from '@/components/ui/panel';
import { StatusNote } from '@/components/ui/status-note';
import { FactList } from '@/components/page/fact-list';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { useDebugAgent, useDeepStudy } from '@/features/advanced/api/workflows';
import { toWorkflowSteps } from '@/features/advanced/workflow-adapters';
import { AGENT_ACTION_LABELS } from '@/lib/fact-labels';
import { enumText, usageCreditsText, vocabularyText } from '@/lib/learner-safe';
import { AiFeedback } from './ai-feedback';

/**
 * The deep-reasoning entry beside an ordinary question surface.
 *
 * It stays on the same page as the question it deepens rather than opening a second one, and it
 * states its own phase — a long retrieval is not a frozen screen. Citations are the backend's
 * own; a run that cites nothing says so.
 */
export function StrongReasoningSurface({
  context,
  courseId,
  subjectKey,
  chapterId,
  knowledgePointId,
  materialIds,
  children,
}: {
  context: string;
  courseId?: string;
  subjectKey?: string;
  chapterId?: string;
  knowledgePointId?: string;
  materialIds?: number[];
  children?: ReactNode;
}) {
  const [question, setQuestion] = useState('');
  const [phase, setPhase] = useState<'idle' | 'retrieving' | 'reasoning' | 'completed' | 'failed'>('idle');
  const deepStudy = useDeepStudy();
  const failure = deepStudy.error instanceof ApiRequestError ? deepStudy.error.status : undefined;

  const submit = () => {
    if (!question.trim()) return;
    setPhase('retrieving');
    deepStudy.mutate(
      { question: question.trim(), courseId, subjectKey, chapterId, knowledgePointId, materialIds },
      { onSuccess: () => setPhase('completed'), onError: () => setPhase('failed') },
    );
  };

  const response = deepStudy.data;
  const usage = usageCreditsText(response?.usage);
  const phaseText =
    phase === 'retrieving'
      ? '正在检索资料并推理…'
      : phase === 'completed'
        ? '已完成'
        : phase === 'failed'
          ? '未完成'
          : '待开始';

  return (
    <Panel tone="ai" className="mt-8" labelledBy="deep-study-title">
      <p className="text-metadata font-medium tracking-eyebrow text-ai-ink">深度思考 · 强推理</p>
      <h2 id="deep-study-title" className="mt-2 text-heading font-semibold text-text-primary">
        深度思考（{context}）
      </h2>
      <p className="mt-2 max-w-prose text-body text-text-secondary">
        普通提问留在上面的问答区；这里用同一份学习上下文做一次更强的推理。状态：{phaseText}。
      </p>

      <label className="mt-5 block text-body font-medium text-text-primary" htmlFor="deep-study-question">
        深度问题
      </label>
      <textarea
        id="deep-study-question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        className="mt-2 min-h-24 w-full rounded-card border border-border-default bg-surface p-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-accent focus-visible:ring-offset-2"
        placeholder="例如：为什么这一章的两个结论可以互相推导？"
      />
      <div className="mt-3">
        <Button variant="secondary" disabled={deepStudy.isPending || !question.trim()} onClick={submit}>
          {deepStudy.isPending ? '正在深度思考…' : '开始深度思考'}
        </Button>
      </div>

      {failure === 403 ? (
        <StatusNote tone="danger" className="mt-3">该高级能力需要升级后使用。</StatusNote>
      ) : failure === 429 ? (
        <StatusNote tone="danger" className="mt-3">本次额度不足，未启动深度思考。</StatusNote>
      ) : deepStudy.isError ? (
        <StatusNote tone="danger" className="mt-3">深度思考暂时不可用，请稍后再试。</StatusNote>
      ) : null}

      {response ? (
        <section className="mt-5" aria-label="深度思考证据">
          <h3 className="text-body font-medium text-text-primary">回答</h3>
          <p className="mt-2 whitespace-pre-wrap text-body text-text-primary">{response.answer}</p>
          <p className="mt-3 text-metadata text-text-secondary">
            模型：{response.model.display_name} · 请求状态：{enumText('status', response.status)}
          </p>

          <h4 className="mt-4 text-metadata font-medium tracking-eyebrow text-text-muted">引用资料</h4>
          {response.citations?.length ? (
            <ol className="mt-2 space-y-3">
              {response.citations.map((citation) => (
                <li key={`${citation.material_id}-${citation.snippet}`} className="border-l-2 border-border-default pl-3">
                  <a
                    className="text-body text-primary-ink underline hover:text-primary-hover"
                    href={resolveApiResourceUrl(`/materials/${citation.material_id}/preview`)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {citation.filename}
                  </a>
                  <p className="mt-1 text-metadata text-text-secondary">{citation.snippet}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-2 text-body text-text-secondary">后端未返回可引用资料。</p>
          )}

          {usage ? <p className="mt-3 text-metadata text-text-secondary">{usage}</p> : null}
          <AiFeedback requestId={response.request_id} workflowId="deep_study" />
        </section>
      ) : null}
      {children}
    </Panel>
  );
}

/**
 * The multi-step agent: diagnose, patch, run the exercise's own tests, re-check.
 *
 * It is advisory by construction — it never writes the project, and "apply" only replaces the
 * editor buffer — so the surface says that, shows the whole trace rather than a summary, and
 * leaves the learner in control of taking the patch. Measurements before and after the fix are
 * rendered as the numbers they are, not as the JSON they arrived in.
 *
 * What a learner reads here is the run itself: its iteration count, each step, the patch, the
 * test results before and after, the final explanation. The run's own identity — its id, the
 * requests behind each step, the provider's bookkeeping — stays in the client.
 */
export function DebugAgentSurface({ exerciseId, code, onApply }: { exerciseId: number; code: string; onApply: (code: string) => void }) {
  const agent = useDebugAgent();
  const result = agent.data;
  const usage = usageCreditsText(result?.usage);
  const failure = agent.error instanceof ApiRequestError ? agent.error.status : undefined;
  const start = () =>
    agent.mutate({
      exercise_id: exerciseId,
      files: [{ filename: 'editor-buffer', content: code }],
      goal: '诊断当前编辑器缓冲区并给出可审阅的修复建议。',
    });

  return (
    <section className="rounded-card border border-border-default bg-surface p-5 sm:p-6" aria-label="Debug Agent 工作流">
      <p className="text-metadata font-medium tracking-eyebrow text-text-muted">高级工作流 · 多步</p>
      <h2 className="mt-2 text-heading font-semibold text-text-primary">Debug Agent</h2>
      <p className="mt-2 max-w-prose text-body text-text-secondary">
        这是 advisory 工作流：不会自动或永久覆盖项目文件；“应用到编辑器”只改当前缓冲区。
      </p>
      <div className="mt-4">
        <Button variant="secondary" disabled={agent.isPending || !code.trim()} onClick={start}>
          {agent.isPending ? '正在运行 Debug Agent…' : '启动 Debug Agent'}
        </Button>
      </div>

      {failure === 403 ? (
        <StatusNote tone="danger" className="mt-3">该高级能力需要升级后使用。</StatusNote>
      ) : failure === 429 ? (
        <StatusNote tone="danger" className="mt-3">本次额度不足，未启动 Debug Agent。</StatusNote>
      ) : agent.isError ? (
        <StatusNote tone="danger" className="mt-3">工作流失败或超时，请稍后重试。</StatusNote>
      ) : null}

      {result ? (
        <div className="mt-5 space-y-5">
          <p className="text-body text-text-primary">
            状态：{enumText('status', result.status)} · 迭代：{result.iterations_used} · 执行：
            {result.executions_used}
          </p>

          <section aria-label="工作流步骤">
            <h3 className="text-metadata font-medium tracking-eyebrow text-text-muted">执行步骤</h3>
            <ol className="mt-3 space-y-3">
              {toWorkflowSteps(result.steps ?? []).map((step) => (
                <li key={step.step_index} className="border-l-2 border-programming pl-3">
                  <p className="text-body text-text-primary">
                    <span className="tabular-nums">{step.step_index}.</span>{' '}
                    {vocabularyText(AGENT_ACTION_LABELS, step.action)}
                    <span className="ml-2 text-metadata text-text-secondary">
                      {enumText('status', step.status)}
                    </span>
                  </p>
                  {typeof step.patch === 'string' && step.patch ? (
                    <pre className="mt-2 overflow-auto rounded-control bg-lab-ink p-3 text-xs text-lab-paper">{step.patch}</pre>
                  ) : null}
                  {typeof step.snippet === 'string' && step.snippet ? (
                    <p className="mt-1 text-metadata text-text-secondary">{step.snippet}</p>
                  ) : null}
                  {step.ai_request_id ? (
                    <AiFeedback requestId={step.ai_request_id} workflowId={`${result.agent_run_id}:${step.step_index}`} />
                  ) : null}
                </li>
              ))}
            </ol>
          </section>

          <section aria-label="本次运行的结果">
            <h3 className="text-metadata font-medium tracking-eyebrow text-text-muted">本次运行的结果</h3>
            <FactList
              className="mt-3"
              columns={2}
              value={{
                diagnosis: result.diagnosis,
                tests_before: result.tests_before,
                tests_after: result.tests_after,
                explanation: result.explanation,
              }}
            />
            {result.proposed_patch ? (
              <details className="mt-3">
                <summary className="text-body text-text-secondary">查看建议的改动</summary>
                <pre className="mt-2 overflow-auto rounded-control bg-lab-ink p-3 text-xs text-lab-paper">{result.proposed_patch}</pre>
              </details>
            ) : null}
            {result.final_code ? (
              <div className="mt-4">
                <Button variant="secondary" onClick={() => onApply(result.final_code!)}>
                  应用到编辑器
                </Button>
              </div>
            ) : null}
          </section>

          {usage ? <p className="text-metadata text-text-secondary">{usage}</p> : null}
        </div>
      ) : null}
    </section>
  );
}
