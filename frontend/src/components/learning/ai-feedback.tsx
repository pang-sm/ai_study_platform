import { useState } from 'react';
import { useAiFeedback } from './p4-api';

const reasons = [['incorrect', '不正确'], ['too_shallow', '太浅'], ['too_complex', '太复杂'], ['too_verbose', '太冗长'], ['too_brief', '太简略'], ['bad_code', '代码建议不佳'], ['slow', '响应慢'], ['poor_image', '图片质量不佳'], ['other', '其他']] as const;
export function AiFeedback({ requestId, workflowId = '' }: { requestId?: string | null; workflowId?: string }) {
  const feedback = useAiFeedback(); const [choosing, setChoosing] = useState(false);
  if (!requestId) return null;
  const send = (rating: 'up' | 'down', reason?: typeof reasons[number][0]) => feedback.mutate({ request_id: requestId, rating, reason: reason ?? null, regenerated: false, switched_model: false, workflow_id: workflowId });
  return <section className="mt-4 border-t border-lab-grid pt-4" aria-label="AI 回答反馈"><p className="text-sm text-text-secondary">这条反馈用于后续质量改进。</p><div className="mt-2 flex flex-wrap gap-2"><button type="button" className="rounded-control border border-lab-grid px-3 py-2" disabled={feedback.isPending} onClick={() => send('up')}>有帮助</button><button type="button" className="rounded-control border border-lab-grid px-3 py-2" disabled={feedback.isPending} onClick={() => setChoosing(true)}>需要改进</button></div>{choosing ? <div className="mt-3"><p>请选择需要改进的原因</p><div className="mt-2 flex flex-wrap gap-2">{reasons.map(([value, label]) => <button key={value} type="button" className="rounded-control border border-lab-grid px-3 py-2" disabled={feedback.isPending} onClick={() => send('down', value)}>{label}</button>)}</div></div> : null}{feedback.isSuccess ? <p role="status" className="mt-3 text-success-ink">反馈已记录，用于后续质量改进。</p> : null}{feedback.isError ? <p role="alert" className="mt-3 text-danger-ink">反馈暂未提交成功，请稍后重试。</p> : null}</section>;
}
