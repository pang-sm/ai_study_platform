import { createFileRoute } from '@tanstack/react-router';
import { ExerciseDetailPage } from '@/features/programming/components/programming-pages';
export const Route = createFileRoute('/programming/$language/exercises/$exerciseId')({ component: ProgrammingExerciseDetailRoute });
function ProgrammingExerciseDetailRoute() { const { language, exerciseId } = Route.useParams(); return <ExerciseDetailPage language={language} exerciseId={Number(exerciseId)} />; }
