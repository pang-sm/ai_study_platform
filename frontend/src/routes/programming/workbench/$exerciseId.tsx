import { createFileRoute } from '@tanstack/react-router';
import { WorkbenchPage } from '@/features/programming/components/programming-practice-page';
import { ProgrammingToolGate } from '@/features/programming/components/programming-shell';
import { validateProgrammingSearch } from '@/features/programming/programming-context';

/**
 * The Workbench, at the space's own level rather than under a language.
 *
 * SSOT §11 lists the Programming Workbench as a functional domain of its own, and §72 keeps it
 * distinct from the Programming Agent — so it is addressed by what it opens (an exercise) and not
 * by a language path segment. It is reached from an exercise, never from the strip: it is not a
 * place to stand, it is what opening a question does, the same way `/course/<id>/study` is reached
 * from 知识结构.
 */
export const Route = createFileRoute('/programming/workbench/$exerciseId')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingWorkbenchRoute,
});

function ProgrammingWorkbenchRoute() {
  const { language } = Route.useSearch();
  const { exerciseId } = Route.useParams();
  return (
    <ProgrammingToolGate
      slugFromUrl={language}
      to="/programming/practice"
      active="practice"
      description="练习属于某一门语言。先选一门，再打开它的题目。"
    >
      {(resolved) => <WorkbenchPage language={resolved} exerciseId={Number(exerciseId)} />}
    </ProgrammingToolGate>
  );
}
