import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * How long the backend refuses a second code for the same address.
 *
 * It mirrors `EMAIL_CODE_RESEND_SECONDS` in `backend/main.py`, where `_email_code_recent` refuses
 * a send inside that window with `429 请 60 秒后再试`. The countdown below is an affordance, not a
 * control: it exists so the button can say when a resend is actually possible, and every refusal
 * the server does return is what corrects it.
 */
export const RESEND_COOLDOWN_SECONDS = 60;

/**
 * A one-shot countdown that reports whole seconds left.
 *
 * The deadline is an instant, not a tally: a phone that sleeps mid-window comes back showing the
 * real time left instead of the number of ticks it happened to receive.
 */
export function useResendCooldown(): { remaining: number; start: () => void } {
  const [remaining, setRemaining] = useState(0);
  const endsAt = useRef(0);
  const counting = remaining > 0;

  const start = useCallback(() => {
    endsAt.current = Date.now() + RESEND_COOLDOWN_SECONDS * 1000;
    setRemaining(RESEND_COOLDOWN_SECONDS);
  }, []);

  useEffect(() => {
    if (!counting) return;
    const id = window.setInterval(() => {
      setRemaining(Math.max(0, Math.ceil((endsAt.current - Date.now()) / 1000)));
    }, 1000);
    return () => window.clearInterval(id);
  }, [counting]);

  return { remaining, start };
}
