import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useResendCooldown } from '../use-resend-cooldown';

/**
 * What the caller learned from asking the server to mail a code.
 *
 * The countdown is started by the caller's answer rather than by the click, because only the
 * server knows whether a send happened: a refused send inside the resend window means a code IS
 * already outstanding, and a failed one means the button should stay where it was.
 */
export type SendCodeOutcome = 'sent' | 'rate-limited' | 'failed';

/**
 * The one send-a-code control, shared by sign-in and registration.
 *
 * Four states, in the order a visitor meets them: 发送验证码 → 正在发送… → 重新发送（59s） → 重新发送验证码.
 * The countdown is the backend's own window on screen, so the button is never offering a resend
 * the server would refuse.
 */
export function SendCodeButton({
  onSend,
  pending,
}: {
  onSend: () => Promise<SendCodeOutcome>;
  pending: boolean;
}) {
  const { remaining, start } = useResendCooldown();
  const [sent, setSent] = useState(false);
  const counting = remaining > 0;

  const handleClick = async () => {
    const outcome = await onSend();
    if (outcome === 'failed') return;
    setSent(true);
    start();
  };

  const label = pending
    ? '正在发送…'
    : counting
      ? `重新发送（${remaining}s）`
      : sent
        ? '重新发送验证码'
        : '发送验证码';

  return (
    <Button type="button" variant="secondary" onClick={handleClick} disabled={pending || counting}>
      {label}
    </Button>
  );
}
