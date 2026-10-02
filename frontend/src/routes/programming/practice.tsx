import { createFileRoute } from '@tanstack/react-router';
import { PracticePage } from '@/features/programming/components/programming-practice-page';
import { ProgrammingToolGate } from '@/features/programming/components/programming-shell';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

/**
 * 练习中心 — the bank and the recommended practice for the language in context.
 *
 * The language is a SEARCH parameter rather than a path segment, which is what keeps it from
 * being a second navigation: the tool is the page, the language is what the page is read in, and
 * changing one does not lose the other.
 */
export const Route = createFileRoute('/programming/practice')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingPracticeRoute,
});

function ProgrammingPracticeRoute() {
  const { language } = Route.useSearch();
  return (
    <ProgrammingToolGate
      slugFromUrl={language}
      to="/programming/practice"
      active="practice"
      description="练习按语言分别建立。先选一门，再开始。"
    >
      {(resolved) => <PracticePage language={resolved} />}
    </ProgrammingToolGate>
  );
}
