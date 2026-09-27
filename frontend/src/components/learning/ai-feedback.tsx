import { useRef, useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { Check, Copy, ThumbsDown, ThumbsUp } from 'lucide-react';
import { useAiFeedback } from './p4-api';
import { resolveFeedbackReasons, type FeedbackReason, type FeedbackTarget } from '@/lib/feedback-reasons';

import { cn } from '@/lib/utils';

type Rating = 'up' | 'down';
type Reason = FeedbackReason;

export function AiFeedback({ requestId, workflowId = '', answerText = '', target = 'answer' }: {
  requestId?: string | null;
  workflowId?: string;
  answerText?: string;
  /** WHAT is being rated — selects the reason vocabulary. Defaults to an answer. */
  target?: FeedbackTarget;
}) {
  const reasons = resolveFeedbackReasons(target);
  const feedback = useAiFeedback();
  const [choosing, setChoosing] = useState(false);
  const [selectedReasons, setSelectedReasons] = useState<Reason[]>([]);
  const [comment, setComment] = useState('');
  const [selected, setSelected] = useState<Rating | null>(null);
  const [thanks, setThanks] = useState(false);
  const [copied, setCopied] = useState(false);
  const [popoverPosition, setPopoverPosition] = useState<CSSProperties>();
  const downButtonRef = useRef<HTMLButtonElement>(null);
  if (!requestId) return null;

  const finish = (rating: Rating) => {
    setSelected(rating);
    setThanks(true);
    window.setTimeout(() => setThanks(false), 1800);
  };
  const send = (rating: Rating, payload: { reasons?: Reason[]; comment?: string } = {}) => {
    feedback.mutate({
      request_id: requestId,
      rating,
      target_type: target,
      reason: payload.reasons?.[0] ?? null,
      reasons: payload.reasons ?? [],
      comment: payload.comment ?? '',
      regenerated: false,
      switched_model: false,
      workflow_id: workflowId,
    }, {
      onSuccess: () => finish(rating),
    });
  };
  const toggleReason = (reason: Reason) => setSelectedReasons((current) => current.includes(reason)
    ? current.filter((value) => value !== reason)
    : [...current, reason]);
  const submitNegative = () => {
    if (!selectedReasons.length) return;
    send('down', { reasons: selectedReasons, comment });
    setChoosing(false);
  };
  const copyAnswer = async () => {
    if (!answerText || !navigator.clipboard) return;
    await navigator.clipboard.writeText(answerText);
    // The same confirmation the code block gives: the icon becomes a tick for a moment, so the
    // copy says it worked without a second word appearing beside it.
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };
  const toggleNegative = () => {
    if (choosing) {
      setChoosing(false);
      return;
    }
    const rect = downButtonRef.current?.getBoundingClientRect();
    if (rect) {
      const width = 320;
      const margin = 12;
      const left = Math.min(Math.max(margin, rect.left), window.innerWidth - width - margin);
      const opensBelow = rect.bottom + 400 < window.innerHeight;
      setPopoverPosition(opensBelow
        ? { top: rect.bottom + 8, left }
        : { bottom: window.innerHeight - rect.top + 8, left });
    }
    setChoosing(true);
  };

  const actionClass = (active: boolean) => cn(
    'inline-flex size-8 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-primary-soft hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-50',
    active && 'bg-primary-soft text-primary',
  );

  return <section className="relative mt-3" aria-label="AI 回答操作">
    <div className="flex items-center gap-1">
      <button type="button" title={copied ? '已复制' : '复制回答'} aria-label={copied ? '已复制' : '复制回答'} className={actionClass(false)} onClick={() => void copyAnswer()}>{copied ? <Check className="size-4" /> : <Copy className="size-4" />}</button>
      <button type="button" title="有帮助" aria-label="有帮助" aria-pressed={selected === 'up'} disabled={feedback.isPending} className={actionClass(selected === 'up')} onClick={() => send('up')}><ThumbsUp className="size-4" /></button>
      <button ref={downButtonRef} type="button" title="需要改进" aria-label="需要改进" aria-pressed={selected === 'down'} aria-expanded={choosing} disabled={feedback.isPending} className={actionClass(selected === 'down')} onClick={toggleNegative}><ThumbsDown className="size-4" /></button>
      {thanks ? <span role="status" className="ml-2 inline-flex items-center gap-1 text-metadata text-success-ink"><Check className="size-3.5" />感谢反馈</span> : null}
    </div>
    {choosing ? createPortal(<div role="dialog" aria-label="负反馈" style={popoverPosition} className="fixed z-50 w-80 rounded-xl border border-border-default bg-surface p-3 shadow-lg">
      <p className="text-body font-medium text-text-primary">哪里需要改进？</p>
      <div className="mt-3 space-y-1">
        {reasons.map(([value, label]) => <label key={value} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-text-secondary hover:bg-page-background"><input type="checkbox" checked={selectedReasons.includes(value)} onChange={() => toggleReason(value)} className="size-4 accent-primary" />{label}</label>)}
      </div>
      <label className="mt-3 block text-sm text-text-secondary">补充说明（可选）<textarea aria-label="补充说明（可选）" value={comment} maxLength={1000} onChange={(event) => setComment(event.target.value)} className="mt-1 min-h-20 w-full resize-y rounded-lg border border-border-default bg-page-background px-2 py-1.5 text-body text-text-primary outline-none focus:ring-2 focus:ring-primary" /></label>
      <div className="mt-3 flex justify-end gap-2"><button type="button" className="rounded-lg px-2.5 py-1.5 text-sm text-text-secondary hover:bg-page-background" onClick={() => setChoosing(false)}>取消</button><button type="button" disabled={!selectedReasons.length || feedback.isPending} className="rounded-lg bg-primary px-2.5 py-1.5 text-sm text-white hover:bg-primary-hover disabled:opacity-50" onClick={submitNegative}>提交</button></div>
    </div>, document.body) : null}
    {feedback.isError ? <p role="alert" className="mt-2 text-metadata text-danger-ink">反馈暂未提交成功，请稍后重试。</p> : null}
  </section>;
}
