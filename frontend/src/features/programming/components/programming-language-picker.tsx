import { ArrowRight } from 'lucide-react';
import { useNavigate } from '@tanstack/react-router';
import { programmingLanguages, type ProgrammingLanguageSlug } from '../programming-language';
import { rememberLanguage } from '../programming-recent-language';

/**
 * The front door's one question: which language.
 *
 * It asks and nothing else — no tools, no progress, no today-list. Choosing one opens that
 * language's workspace, which is where every other thing the space does already happens. Four
 * separate banks are why the question is asked rather than answered for the learner.
 */
export function ProgrammingLanguagePicker({
  heading,
  description,
}: {
  heading: string;
  description?: string;
}) {
  const navigate = useNavigate();
  return (
    <section aria-labelledby="programming-language-picker-title">
      <h1
        id="programming-language-picker-title"
        className="text-page-title font-semibold tracking-[-0.02em] text-text-primary"
      >
        {heading}
      </h1>
      {description ? (
        <p className="mt-2 max-w-reading text-body leading-relaxed text-text-secondary">{description}</p>
      ) : null}

      <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, string]>).map(([slug, label]) => (
          <li key={slug}>
            <button
              type="button"
              onClick={() => {
                rememberLanguage(slug);
                void navigate({ to: '/programming/workbench', search: { language: slug } as never });
              }}
              className="flex h-full w-full flex-col gap-2 rounded-card border border-border-default bg-surface p-5 text-left transition-colors hover:border-primary hover:bg-primary-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              <span className="text-card-title font-semibold text-text-primary">{label}</span>
              <span className="mt-auto inline-flex items-center gap-1 text-metadata text-text-muted">
                进入工作台
                <ArrowRight className="size-4" aria-hidden="true" />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
