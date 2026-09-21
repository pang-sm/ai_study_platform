import { createFileRoute } from '@tanstack/react-router';
import { CourseWrongPage } from '@/features/course/components/course-pages';
function CourseWrongRoute() { return <CourseWrongPage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/wrong')({ component: CourseWrongRoute });
