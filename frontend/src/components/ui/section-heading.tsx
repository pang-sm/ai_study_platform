import { cn } from '@/lib/utils';

/**
 * The editorial header every section uses: an eyebrow, a title, an optional line of context and
 * an optional action on the far side.
 *
 * It exists so the type scale and the section rhythm are declared once. Before this, each
 * surface repeated the same three elements by hand and drifted — some sections had no eyebrow,
 * some titled at body size, and the level of emphasis stopped meaning anything.
 */
export function SectionHeading({
  id,
  eyebrow,
  title,
  description,
  action,
  as: Heading = 'h2',
  className,
}: {
  id?: string;
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
  as?: 'h2' | 'h3';
  className?: string;
}) {
  return (
    <div className={cn('flex flex-wrap items-end justify-between gap-x-6 gap-y-3', className)}>
      <div className="min-w-0">
        {eyebrow ? (
          <p className="text-metadata font-medium tracking-eyebrow text-text-muted">{eyebrow}</p>
        ) : null}
        <Heading
          id={id}
          className={cn(
            'font-semibold text-text-primary',
            Heading === 'h2' ? 'text-section-title' : 'text-heading',
            eyebrow ? 'mt-1' : undefined,
          )}
        >
          {title}
        </Heading>
        {description ? (
          <p className="mt-2 max-w-prose text-body text-text-secondary">{description}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
