import { useMemo } from 'react';
import { Navigate, createFileRoute } from '@tanstack/react-router';
import { LoadingState } from '@/components/page/loading-state';
import { ProgrammingLanguagePicker } from '@/features/programming/components/programming-language-picker';
import { useProgrammingLanguage, validateProgrammingSearch } from '@/features/programming/programming-context';
import { readRecentLanguage } from '@/features/programming/programming-recent-language';

/**
 * 编程学习's front door: one question, or none.
 *
 * A learner who has already been working goes straight back to the workspace for the language they
 * were using — the address, then the language they last opened on this device, then the one their
 * own settings declare — so the common case never sees this page at all. Everyone else is asked
 * which language, and choosing one opens its workspace immediately: there is no second home page
 * between the question and the work (SSOT: the space is a workspace, not a set of entry points).
 */
export const Route = createFileRoute('/programming/')({
  validateSearch: validateProgrammingSearch,
  component: ProgrammingFrontDoor,
});

function ProgrammingFrontDoor() {
  const { language: fromUrl } = Route.useSearch();
  const declared = useProgrammingLanguage(fromUrl);
  const recent = useMemo(() => (fromUrl ? undefined : readRecentLanguage()), [fromUrl]);
  const language = fromUrl ?? recent ?? declared.language;

  if (language) {
    return <Navigate to="/programming/workbench" search={{ language }} replace />;
  }
  if (declared.pending) {
    return (
      <div className="space-accent space-accent--programming mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
        <LoadingState label="正在读取你的语言设置…" />
      </div>
    );
  }
  return (
    <div className="space-accent space-accent--programming mx-auto w-full max-w-content px-5 py-10 sm:px-8 lg:px-12">
      <ProgrammingLanguagePicker
        heading="选择编程语言"
        description="工作台按语言分开：每一门语言有自己的题目、编辑器与运行环境。选择一门即可开始。"
      />
    </div>
  );
}
