import { ContentUnavailableState } from '@/features/exam/components/content-unavailable-state';
import { ExamPageShell } from '@/features/exam/components/exam-page-shell';
import type { ExamContextItem } from '@/features/exam/components/exam-context-nav';

type FoundationPage = 'overview' | 'setup' | 'subjects' | 'cs408' | 'unavailable';

const pageCopy: Record<Exclude<FoundationPage, 'unavailable'>, { title: string; description: string; activeItem: ExamContextItem }> = {
  overview: { title: '我的备考', description: '选择备考方向、科目与目标年份。', activeItem: 'overview' },
  setup: { title: '设置我的备考', description: '方向、科目和目标年份将在这里设置。', activeItem: 'setup' },
  subjects: { title: '科目', description: '在这里查看可加入备考的全国统考科目。', activeItem: 'subjects' },
  cs408: { title: '计算机学科专业基础 408', description: 'CS408 学习工作区将在后续步骤接入真实学习内容。', activeItem: 'cs408' },
};

export function ExamFoundationPage({ page }: { page: FoundationPage }) {
  if (page === 'unavailable') {
    return <ExamPageShell activeItem="subjects"><ContentUnavailableState subjectName="该科目" /></ExamPageShell>;
  }

  const copy = pageCopy[page];
  return (
    <ExamPageShell activeItem={copy.activeItem}>
      <section className="max-w-reading border-b border-lab-grid/45 pb-12" aria-labelledby="exam-page-title">
        <h1 id="exam-page-title" className="text-page-title font-bold tracking-[-0.04em]">{copy.title}</h1>
        <p className="mt-4 text-body leading-7 text-text-secondary">{copy.description}</p>
      </section>
    </ExamPageShell>
  );
}
