import { createFileRoute } from '@tanstack/react-router';
import { CourseRecordsPage } from '@/features/course/components/course-pages';
function CourseRecordsRoute() { return <CourseRecordsPage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/records')({ component: CourseRecordsRoute });
