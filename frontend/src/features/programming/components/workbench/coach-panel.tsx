import { useEffect, useRef, useState } from 'react';
import { PanelRightClose, PanelRightOpen, Send, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AiFeedback } from '@/components/learning/ai-feedback';
import { AssistantMarkdown } from '@/features/ai/components/assistant-markdown';
import { ModelSelector } from '@/features/ai/components/model-selector';
import { usageCreditsText } from '@/lib/learner-safe';
import { useCodeCoach, type CoachTurn } from '../../api/programming';
import { stringField } from './workbench-model';

type Turn = { question: string; answer: string; requestId?: string; usage?: unknown };

/**
 * The quick ways in. Each is a real question with real context behind it — the endpoint already
 * receives the题面 by id, the code, the last run and the last test's cases, so a preset does not
 * have to describe the situation the learner is looking at.
 */
const QUICK_ASK: ReadonlyArray<{ id: string; label: string; question: string }> = [
  { id: 'hint', label: '给我提示', question: '这道题的解题思路是什么？先给我一个提示，不要直接给出完整代码。' },
  { id: 'error', label: '分析错误', question: '我的代码为什么没有通过？请结合运行/测试结果定位问题。' },
  { id: 'explain', label: '解释代码', question: '请解释我这段代码在做什么，以及每一步的作用。' },
  { id: 'optimize', label: '优化思路', question: '这段代码有哪些可以改进或优化的地方？' },
];

/**
 * AI 教练 — the space's assistant, scoped to the work on screen.
 *
 * It is not a second chat product: it is the `programming.explain` capability asked about THIS
 * exercise, and the endpoint is what carries the context — the exercise by id (the backend loads
 * the题面 and its knowledge points), the code, the last run's own stdout/stderr, the last test's
 * failing cases, and the turns already exchanged. Nothing here composes that context as prose, so
 * the answer is about the learner's actual failure rather than a generic one.
 *
 * It costs AI 额度, which is why it lives in its own rail rather than beside 运行, and why the
 * settled cost of a completed call is stated under its answer. When the capability is unavailable
 * — no qualified model, no permission, no budget — the failure is shown as a failure: no answer is
 * invented to keep the panel looking busy.
 */
export function CoachPanel({
  language,
  exerciseId,
  exerciseTitle,
  code,
  lastRun,
  lastTest,
  disabled,
  modelId,
  onModelChange,
  collapsed,
  onToggleCollapsed,
}: {
  language: string;
  exerciseId: number | undefined;
  exerciseTitle: string | undefined;
  code: string;
  lastRun: Record<string, unknown> | undefined;
  lastTest: Record<string, unknown> | undefined;
  disabled: boolean;
  /**
   * The learner's model choice, owned by the workspace rather than by this panel.
   *
   * The panel is remounted whenever the open题 changes (the thread is per-题), so a choice kept
   * here would be thrown away on every switch. It lives one level up so switching题 clears the
   * thread WITHOUT losing which model the learner is using.
   */
  modelId: string;
  onModelChange: (modelId: string) => void;
  /** The learner's own width choice for this rail; the chat is hidden, never destroyed. */
  collapsed: boolean;
  onToggleCollapsed: () => void;
}) {
  const coach = useCodeCoach();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState<string | undefined>();
  const [failedQuestion, setFailedQuestion] = useState<string | undefined>();
  const threadRef = useRef<HTMLDivElement>(null);
  // The transcript's scroll position, tracked while it is on screen. The node is unmounted when
  // the panel is collapsed, so the position is remembered here and restored on reopen.
  const scrollTopRef = useRef(0);

  useEffect(() => {
    if (!collapsed && threadRef.current) threadRef.current.scrollTop = scrollTopRef.current;
  }, [collapsed]);

  const ask = (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || coach.isPending || disabled) return;
    const history: CoachTurn[] = turns
      .flatMap((turn): CoachTurn[] => [
        { role: 'user', content: turn.question },
        { role: 'assistant', content: turn.answer },
      ])
      .slice(-8);
    setDraft('');
    setFailedQuestion(undefined);
    setPendingQuestion(trimmed);
    coach.mutate(
      { language, code, question: trimmed, exerciseId, lastRun, lastTest, history, modelId },
      {
        onSuccess: (data) => {
          setTurns((current) => [
            ...current,
            {
              question: trimmed,
              answer: stringField(data, 'answer') ?? '',
              requestId: stringField(data, 'request_id'),
              usage: data.usage,
            },
          ]);
          setPendingQuestion(undefined);
        },
        onError: () => {
          setPendingQuestion(undefined);
          setFailedQuestion(trimmed);
        },
      },
    );
  };

  // Collapsed, the coach is a 44px rail: the mark and the way back, and nothing that could
  // overflow. The thread's state above survives — collapsing hides the conversation, it does not
  // end it, and toggling never fires a request.
  if (collapsed) {
    return (
      <div className="wb-coach wb-coach--rail">
        <span className="wb-coach__rail-mark" aria-hidden="true">
          <Sparkles className="size-4" />
        </span>
        <button
          type="button"
          className="wb-coach__rail-toggle"
          aria-label="展开 AI 教练"
          aria-expanded={false}
          title="展开 AI 教练"
          onClick={onToggleCollapsed}
        >
          <PanelRightOpen className="size-4" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="wb-coach">
      <div className="wb-coach__head">
        <div className="wb-coach__head-row">
          <p className="wb-coach__title">
            <Sparkles className="size-4" aria-hidden="true" />
            AI 教练
          </p>
          <div className="wb-coach__head-actions">
            {/* The same picker AI 问答 uses, fed by the same entitled menu for this capability. It
                renders nothing when the backend offers no model for this learner. */}
            <ModelSelector
              capability="programming.explain"
              value={modelId}
              onChange={onModelChange}
              menuPlacement="down"
              align="right"
            />
            <button
              type="button"
              className="wb-coach__collapse"
              aria-label="收起 AI 教练"
              aria-expanded
              title="收起 AI 教练"
              onClick={onToggleCollapsed}
            >
              <PanelRightClose className="size-4" aria-hidden="true" />
            </button>
          </div>
        </div>
        <p className="wb-coach__scope">
          {exerciseTitle ? `当前题目：${exerciseTitle}` : '打开一道题目后，教练会围绕这道题回答。'}
        </p>
        <div className="wb-coach__quick">
          {QUICK_ASK.map((entry) => (
            <Button
              key={entry.id}
              type="button"
              variant="secondary"
              size="sm"
              disabled={disabled || coach.isPending || !code.trim()}
              onClick={() => ask(entry.question)}
            >
              {entry.label}
            </Button>
          ))}
        </div>
      </div>

      <div
        className="wb-coach__thread"
        ref={threadRef}
        onScroll={(event) => {
          scrollTopRef.current = event.currentTarget.scrollTop;
        }}
      >
        {!turns.length && !pendingQuestion && !failedQuestion ? (
          <p className="text-body text-text-secondary">
            {disabled
              ? '先打开一道题目；教练会用当前语言、题目、代码与最近一次运行结果作答。'
              : '可以直接用上面的快捷入口，或在下面输入你的问题。教练会结合当前代码与最近一次运行/测试结果回答。'}
          </p>
        ) : null}

        {turns.map((turn, index) => (
          <div key={`${index}-${turn.question}`} className="wb-coach__turn">
            <p className="wb-coach__question">{turn.question}</p>
            <div className="wb-coach__answer">
              {turn.answer ? (
                <AssistantMarkdown content={turn.answer} />
              ) : (
                <p className="text-body text-text-secondary">这次回答没有返回可显示的内容，可以再问一次。</p>
              )}
            </div>
            {usageCreditsText(turn.usage) ? (
              <p className="mt-2 text-metadata text-text-secondary">{usageCreditsText(turn.usage)}</p>
            ) : null}
            {turn.requestId ? (
              <div className="mt-2">
                <AiFeedback requestId={turn.requestId} workflowId="programming_ai_explain" />
              </div>
            ) : null}
          </div>
        ))}

        {pendingQuestion ? (
          <div className="wb-coach__turn">
            <p className="wb-coach__question">{pendingQuestion}</p>
            <p className="wb-coach__pending" role="status">
              正在分析…
            </p>
          </div>
        ) : null}

        {failedQuestion ? (
          <div className="wb-coach__turn">
            <p className="wb-coach__question">{failedQuestion}</p>
            <p className="mt-2 text-body text-danger-ink">
              这次分析没有成功，可能是暂时没有可用模型或额度不足。可以稍后重试。
            </p>
            <div className="mt-2">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={coach.isPending || !code.trim()}
                onClick={() => ask(failedQuestion)}
              >
                重试
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      <div className="wb-coach__compose">
        <label htmlFor="wb-coach-input" className="sr-only">
          向 AI 教练提问
        </label>
        <textarea
          id="wb-coach-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={2}
          placeholder="提问，例如：为什么这里会死循环？"
          className="w-full rounded-control border border-border-default bg-surface p-2 text-metadata text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-accent focus-visible:ring-offset-1"
        />
        <div className="mt-2 flex items-center justify-end">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={disabled || coach.isPending || !draft.trim() || !code.trim()}
            onClick={() => ask(draft)}
          >
            <Send className="size-4" aria-hidden="true" />
            发送
          </Button>
        </div>
      </div>
    </div>
  );
}
