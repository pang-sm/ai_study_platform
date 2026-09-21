import { createFileRoute } from '@tanstack/react-router';
import { ExercisesPage } from '@/features/programming/components/programming-pages';
import { AdaptivePractice } from '@/components/learning/adaptive-practice';
export const Route = createFileRoute('/programming/$language/exercises/')({ component: ProgrammingExercisesRoute });
function ProgrammingExercisesRoute() { const language = Route.useParams().language; return <><AdaptivePractice serviceKey="programming" language={language} /><ExercisesPage language={language} /></>; }
