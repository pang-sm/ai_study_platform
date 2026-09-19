import { createFileRoute } from '@tanstack/react-router';
import type { WrongAnswerStatusFilter } from '@/features/exam/api/wrong-answers';
import { Cs408WrongAnswerWorkspace } from '@/features/exam/components/cs408-wrong-answer-workspace';

function parseStatus(status: unknown): WrongAnswerStatusFilter {
  return status === 'active' || status === 'resolved' ? status : 'all';
}

export const Route = createFileRoute('/exam/cs408/wrong')({ validateSearch: (search: Record<string, unknown>) => ({ module: typeof search.module === 'string' ? search.module : undefined, status: parseStatus(search.status), page: typeof search.page === 'number' && Number.isInteger(search.page) && search.page > 0 ? search.page - 1 : 0 }), component: WrongAnswerRoute });
function WrongAnswerRoute() { const { module, status, page } = Route.useSearch(); return <Cs408WrongAnswerWorkspace moduleKey={module} status={status} page={page} />; }
