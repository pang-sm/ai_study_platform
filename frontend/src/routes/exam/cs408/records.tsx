import { createFileRoute } from '@tanstack/react-router';
import { Cs408LearningRecordsWorkspace } from '@/features/exam/components/cs408-learning-records-workspace';

export const Route = createFileRoute('/exam/cs408/records')({ validateSearch: (search: Record<string, unknown>) => ({ module: typeof search.module === 'string' ? search.module : undefined }), component: Cs408RecordsRoute });
function Cs408RecordsRoute() { return <Cs408LearningRecordsWorkspace moduleKey={Route.useSearch().module} />; }
