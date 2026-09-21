import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * One component for loading progress, notices and failures, so a learner meets the same
 * three states in the same shape on every surface.
 *
 * The live region is chosen by the caller, not inferred: `status` announces politely and is
 * right for "正在读取…" and confirmations, while `alert` interrupts and is reserved for
 * something that actually went wrong. A failure a caller forgets to mark would be announced
 * too late, which is why the default is the louder of the two.
 */
export type StatusTone = 'info' | 'success' | 'warning' | 'danger';

export function statusRole(tone: StatusTone): 'status' | 'alert' {
  return tone === 'danger' || tone === 'warning' ? 'alert' : 'status';
}

const toneClasses: Record<StatusTone, string> = {
  info: 'border-border-default bg-neutral-soft text-text-secondary',
  success: 'border-success/30 bg-success-soft text-success-ink',
  warning: 'border-warning/30 bg-warning-soft text-warning-ink',
  danger: 'border-danger/30 bg-danger-soft text-danger-ink',
};

export function StatusNote({
  tone = 'info',
  role,
  children,
  className,
}: {
  tone?: StatusTone;
  role?: 'status' | 'alert';
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      role={role ?? statusRole(tone)}
      className={cn('rounded-control border px-3 py-2 text-body', toneClasses[tone], className)}
    >
      {children}
    </p>
  );
}
