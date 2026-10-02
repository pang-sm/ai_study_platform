import type { ReactNode } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { BackLink } from '@/components/page/back-link';
import { Container } from '@/components/ui/container';
import { routePath } from '@/lib/router';
import { canonicalLanguage, normalizeLanguageSlug, programmingLanguages, type ProgrammingLanguageSlug } from '../programming-language';
import './programming-shell.css';

/**
 * The frame the one remaining non-workspace page shares (计划).
 *
 * It used to be the space's tool frame: a strip of four tools under a language line, with every
 * programming page inside it. Those tools are regions of the workspace now, so the strip is gone —
 * what is left is the line that says which language the page is read in and the control that
 * changes it, which is the one thing a per-language page still needs.
 */
export function ProgrammingShell({
  language,
  children,
}: {
  /** The language this page is scoped to, when one is known. */
  language?: ProgrammingLanguageSlug;
  children: ReactNode;
}) {
  const canonical = language ? canonicalLanguage(language) : undefined;
  return (
    <div className="programming-shell space-accent space-accent--programming">
      <Container>
        <div className="programming-head">
          <BackLink to="/programming" label="返回编程学习" />
          <div className="programming-head__identity">
            <p className="programming-head__name">
              {canonical ? `编程学习 · ${canonical}` : '编程学习'}
            </p>
            {language ? <LanguageSwitcher language={language} to="/programming/plan" /> : null}
          </div>
        </div>
      </Container>
      <Container className="programming-page">{children}</Container>
    </div>
  );
}

/**
 * The language the page is being read in, changed without leaving it.
 *
 * It navigates rather than writing a preference, because "which language is open" is a property of
 * the page being read and there is no stored current-language pointer in the API to write. A
 * native `<select>` is used for the same reason the course and 408 switchers use one: keyboard and
 * screen-reader support come with the element.
 */
function LanguageSwitcher({ language, to }: { language: ProgrammingLanguageSlug; to: string }) {
  const navigate = useNavigate();
  return (
    <select
      aria-label="切换编程语言"
      value={language}
      onChange={(event) => {
        const next = normalizeLanguageSlug(event.target.value);
        if (!next || next === language) return;
        void navigate({ to: routePath(to), search: { language: next } as never });
      }}
      className="programming-language-select"
    >
      {(Object.entries(programmingLanguages) as Array<[ProgrammingLanguageSlug, string]>).map(
        ([slug, label]) => (
          <option key={slug} value={slug}>
            {label}
          </option>
        ),
      )}
    </select>
  );
}
