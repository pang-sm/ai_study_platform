import { createFileRoute } from '@tanstack/react-router';
import { LearningReportSurface } from '@/features/learning-intelligence/learning-intelligence-surfaces';
import { reportScopeFromSearch } from '@/features/learning-intelligence/presentation';

export const Route = createFileRoute('/reports')({
  validateSearch: (search) => ({ space: typeof search.space === 'string' ? search.space : undefined, courseId: typeof search.courseId === 'string' ? search.courseId : undefined, module: typeof search.module === 'string' ? search.module : undefined, language: typeof search.language === 'string' ? search.language : undefined }),
  component: ReportsRoute,
});

function ReportsRoute() { return <LearningReportSurface scope={reportScopeFromSearch(Route.useSearch())} />; }
