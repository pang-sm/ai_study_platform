import { createFileRoute } from '@tanstack/react-router';
import { CourseStudyPage } from '@/features/course/components/course-pages';
function CourseStudyRoute() { return <CourseStudyPage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/study')({ component: CourseStudyRoute });
