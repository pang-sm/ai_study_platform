import { createFileRoute } from '@tanstack/react-router';
import { ExercisesPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/')({ component: ProgrammingLanguageRoute });
function ProgrammingLanguageRoute() { return <ExercisesPage language={Route.useParams().language} />; }
