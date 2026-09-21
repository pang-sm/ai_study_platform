import { ArrowUpRight } from 'lucide-react';
import { Link } from '@tanstack/react-router';
import { LEARNING_SPACES } from '@/components/layout/primary-nav';
import { SectionHeading } from '@/components/ui/section-heading';
import { cn } from '@/lib/utils';

/**
 * The three learning spaces, as an index rather than three large cards.
 *
 * They are the product's structure, not today's work, so they come after the learner's own
 * agenda and records and they read as a table of contents: a numbered rule, the space's mode,
 * its name, and the scope that exists today. The marks are the same three accents the navigation
 * uses, which is what makes the index and the sidebar recognisable as one product — the marks
 * distinguish the spaces, they are not three colour themes.
 */
const accentRule: Record<string, string> = {
  exam: 'bg-exam',
  course: 'bg-course',
  programming: 'bg-programming',
};

function Motif({ accent }: { accent?: string }) {
  const shell = cn(
    'h-11 w-16 shrink-0 fill-none stroke-current stroke-[1.6]',
    accent === 'exam' ? 'text-exam' : accent === 'course' ? 'text-course' : 'text-programming',
  );

  if (accent === 'exam') {
    return (
      <svg viewBox="0 0 120 80" aria-hidden="true" className={shell}>
        <circle cx="31" cy="48" r="18" />
        <circle cx="31" cy="48" r="6" className="fill-current" />
        <path d="M31 48 93 15M83 15h10v10" />
      </svg>
    );
  }
  if (accent === 'course') {
    return (
      <svg viewBox="0 0 120 80" aria-hidden="true" className={shell}>
        <path d="M60 62V39M60 39 24 17M60 39 96 17" />
        <circle cx="60" cy="62" r="7" />
        <circle cx="60" cy="39" r="5" />
        <circle cx="24" cy="17" r="5" />
        <circle cx="96" cy="17" r="5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 120 80" aria-hidden="true" className={shell}>
      <path d="M16 19h47v42H16zM27 32h24M27 41h14M76 40h23M89 28l12 12-12 12" />
      <circle cx="105" cy="40" r="4" className="fill-current" />
    </svg>
  );
}

export function LearningSpaces() {
  return (
    <section aria-labelledby="worlds-title">
      <SectionHeading
        id="worlds-title"
        eyebrow="学习空间"
        title="选择你的学习方向"
        description="三个学习空间共用同一个账号、同一份学习记录与同一套用量额度。"
      />

      <ul className="mt-6 border-t border-border-default">
        {LEARNING_SPACES.map((space, index) => (
          <li key={space.to} className="border-b border-border-default">
            <Link
              to={space.to}
              className="group flex items-center gap-4 py-5 transition-colors duration-fast ease-standard hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 sm:gap-6"
            >
              <span className="flex items-center gap-3 sm:gap-4">
                <span className="w-6 text-metadata tabular-nums text-text-muted">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <span
                  aria-hidden="true"
                  className={cn('h-10 w-1 shrink-0 rounded-pill', accentRule[space.accent ?? ''])}
                />
              </span>

              <Motif accent={space.accent} />

              <span className="min-w-0 flex-1">
                <span className="block text-metadata font-medium tracking-eyebrow text-text-muted">
                  {space.eyebrow}
                </span>
                <span className="mt-1 block text-card-title font-semibold text-text-primary">
                  {space.label}
                </span>
                <span className="mt-1 block text-metadata text-text-secondary">
                  {space.detail}
                </span>
              </span>

              <span className="inline-flex shrink-0 items-center gap-1 text-body font-medium text-text-primary group-hover:text-primary-ink">
                <ArrowUpRight className="size-5" aria-hidden="true" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
