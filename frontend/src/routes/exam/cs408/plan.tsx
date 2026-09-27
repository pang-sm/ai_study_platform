import { createFileRoute, useSearch } from '@tanstack/react-router';
import { Cs408StudyPlanWorkspace } from '@/features/exam/components/cs408-study-plan-workspace';

// `?module=` is carried onto this tab by the strip above, like every other tool tab. It is NOT
// part of this route's contract — nothing here is scoped by it, and declaring it would make the
// parameter required of every link that opens this page. So it is read loosely and used for the
// one thing it is good for: seeding which paper the adjustment opens on.
export const Route = createFileRoute('/exam/cs408/plan')({ component: Cs408PlanRoute });
function Cs408PlanRoute() {
  const search = useSearch({ strict: false }) as { module?: unknown };
  return <Cs408StudyPlanWorkspace moduleKey={typeof search.module === 'string' ? search.module : undefined} />;
}
