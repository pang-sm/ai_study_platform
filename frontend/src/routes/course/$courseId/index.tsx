import { createFileRoute } from '@tanstack/react-router';
import { CourseWorkspace } from '@/features/course/components/course-workspace';
function CourseHomeRoute() { return <CourseWorkspace courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/')({ component: CourseHomeRoute });
