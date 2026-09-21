import { createFileRoute } from '@tanstack/react-router';
import { PlanPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/plan')({ component: ProgrammingPlanRoute });
function ProgrammingPlanRoute() { return <PlanPage language={Route.useParams().language} />; }
