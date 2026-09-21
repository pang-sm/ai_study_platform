import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * The three surfaces a learning page is allowed to build from.
 *
 * `plain` is an object surface — bounded because it holds something the learner acts on.
 * `focus` is the page's single most important action; it is tinted with the brand's subtle
 * step and marked with a heavier left rule so "what to do next" cannot be read as one more
 * card in a grid. `ai` marks a surface whose content came from a model call, which matters
 * because that is also the surface that spends the learner's AI 额度.
 */
export type PanelTone = 'plain' | 'focus' | 'ai';

const toneClasses: Record<PanelTone, string> = {
  plain: 'border-border-default bg-surface',
  focus: 'border-focus-border bg-focus-surface border-l-4 border-l-primary',
  ai: 'border-ai-accent/30 bg-ai-soft',
};

export function Panel({
  tone = 'plain',
  className,
  children,
  labelledBy,
}: {
  tone?: PanelTone;
  className?: string;
  children: ReactNode;
  /** The heading whose text names this panel, so the panel is a real region to a screen reader. */
  labelledBy?: string;
}) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={cn('rounded-card border p-5 sm:p-6', toneClasses[tone], className)}
    >
      {children}
    </section>
  );
}
