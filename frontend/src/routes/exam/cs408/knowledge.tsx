import { createFileRoute } from '@tanstack/react-router';
import { Cs408KnowledgeWorkspace } from '@/features/exam/components/cs408-knowledge-workspace';

/**
 * The module is not defaulted, on purpose.
 *
 * It used to fall back to `data_structure`, so `/exam/cs408/knowledge` — the exact URL a learner
 * reaches from any CS408 link that forgot to carry a module — silently opened 数据结构. On a
 * four-part exam where the parts are sat and studied separately, that is the page answering a
 * question it was never asked. Absent a module, the page now asks which one.
 */
export const Route = createFileRoute('/exam/cs408/knowledge')({
  validateSearch: (search: Record<string, unknown>) => ({ module: typeof search.module === 'string' ? search.module : undefined }),
  component: KnowledgeRoute,
});

function KnowledgeRoute() {
  const { module } = Route.useSearch();
  return <Cs408KnowledgeWorkspace moduleKey={module} />;
}
