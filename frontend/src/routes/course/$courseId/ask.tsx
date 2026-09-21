import { createFileRoute } from '@tanstack/react-router';
import { CourseAskPage } from '@/features/course/components/course-pages';
function CourseAskRoute() { return <CourseAskPage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/ask')({ component: CourseAskRoute });
