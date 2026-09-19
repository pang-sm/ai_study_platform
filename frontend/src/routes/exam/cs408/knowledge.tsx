import { createFileRoute } from '@tanstack/react-router';
import { Cs408KnowledgeWorkspace } from '@/features/exam/components/cs408-knowledge-workspace';

const fallbackModule = 'data_structure';

export const Route = createFileRoute('/exam/cs408/knowledge')({
  validateSearch: (search: Record<string, unknown>) => ({ module: typeof search.module === 'string' ? search.module : fallbackModule }),
  component: KnowledgeRoute,
});

function KnowledgeRoute() {
  const { module } = Route.useSearch();
  return <Cs408KnowledgeWorkspace moduleKey={module} />;
}
