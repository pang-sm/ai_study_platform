import { createFileRoute } from '@tanstack/react-router';
import { CoursePlanPage } from '@/features/course/components/course-pages';
function CoursePlanRoute() { return <CoursePlanPage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/plan')({ component: CoursePlanRoute });
