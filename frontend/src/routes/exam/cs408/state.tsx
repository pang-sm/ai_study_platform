import { createFileRoute } from '@tanstack/react-router';
import { Cs408StudentTwinWorkspace } from '@/features/exam/components/cs408-student-twin-workspace';

export const Route = createFileRoute('/exam/cs408/state')({ validateSearch: (search: Record<string, unknown>) => ({ module: typeof search.module === 'string' ? search.module : undefined }), component: Cs408StateRoute });
function Cs408StateRoute() { return <Cs408StudentTwinWorkspace moduleKey={Route.useSearch().module} />; }
