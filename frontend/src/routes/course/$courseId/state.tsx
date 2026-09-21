import { createFileRoute } from '@tanstack/react-router';
import { CourseStatePage } from '@/features/course/components/course-pages';
function CourseStateRoute() { return <CourseStatePage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/state')({ component: CourseStateRoute });
