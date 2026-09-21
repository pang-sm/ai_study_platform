import { createFileRoute } from '@tanstack/react-router';
import { CoursePracticePage } from '@/features/course/components/course-pages';
function CoursePracticeRoute() { return <CoursePracticePage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/practice')({ component: CoursePracticeRoute });
