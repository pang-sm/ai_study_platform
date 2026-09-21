import { Outlet, createFileRoute } from '@tanstack/react-router';
import { ExercisesPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/exercises')({ component: () => <Outlet /> });
export function ExercisesRoute() { return <ExercisesPage language={Route.useParams().language} />; }
