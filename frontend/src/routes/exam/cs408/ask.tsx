import { createFileRoute } from '@tanstack/react-router';
import { Cs408AskWorkspace } from '@/features/exam/components/cs408-ask-workspace';
import { searchIdentifier } from '@/lib/router';

/**
 * The paper's assistant, as a page OF the paper.
 *
 * `module` is not defaulted for the same reason it is not defaulted anywhere else in 408: which
 * of the four papers a question is about is the learner's answer to give, and a page that picked
 * one would be answering it for them. Absent a module, the page asks.
 *
 * `knowledge_point` is the canonical id of the node the learner came from, and
 * `knowledge_point_title` is how the page that linked here named it — a display string only. The
 * id is what the turn carries; the title is what the learner reads, so the two can never be
 * conflated, and a URL without the title still states which point is open.
 *
 * The id keeps the type the URL carried (`searchIdentifier`): a code such as `1.1` arrives as a
 * NUMBER, and coercing it to a string here is what would make the router quote it back. Note that
 * the router's own JSON parsing is what rounds a hypothetical code like `3.10` into `3.1` — no
 * code in this content has that shape (measured: all 1,126 codes across the four modules survive
 * the round trip), and that is the thing to re-check if a future code ends in a zero.
 */
export const Route = createFileRoute('/exam/cs408/ask')({
  validateSearch: (search: Record<string, unknown>) => ({
    module: typeof search.module === 'string' ? search.module : undefined,
    knowledge_point: searchIdentifier(search.knowledge_point),
    knowledge_point_title: typeof search.knowledge_point_title === 'string' && search.knowledge_point_title.trim()
      ? search.knowledge_point_title
      : undefined,
  }),
  component: AskRoute,
});

function AskRoute() {
  const { module, knowledge_point: knowledgePoint, knowledge_point_title: knowledgePointTitle } = Route.useSearch();
  return (
    <Cs408AskWorkspace
      moduleKey={module}
      knowledgePoint={knowledgePoint === undefined ? undefined : String(knowledgePoint)}
      knowledgePointTitle={knowledgePointTitle}
    />
  );
}
