import { createFileRoute } from '@tanstack/react-router';
import { StatePage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/state')({ component: ProgrammingStateRoute });
function ProgrammingStateRoute() { return <StatePage language={Route.useParams().language} />; }
