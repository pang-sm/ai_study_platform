import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * A short piece of state attached to a real object — a member tier, a subject's availability,
 * a queue count. Each tone pairs a soft background with its text-safe ink, so the label stays
 * readable at metadata size instead of borrowing the fill colour as a text colour.
 */
export type BadgeTone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'ai';

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'bg-neutral-soft text-text-secondary',
  brand: 'bg-primary-soft text-primary-ink',
  success: 'bg-success-soft text-success-ink',
  warning: 'bg-warning-soft text-warning-ink',
  danger: 'bg-danger-soft text-danger-ink',
  ai: 'bg-ai-soft text-ai-ink',
};

export function Badge({
  tone = 'neutral',
  children,
  className,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-pill px-2.5 py-0.5 text-metadata font-medium',
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
