import { createFileRoute } from '@tanstack/react-router';
import { CourseMaterialsPage } from '@/features/course/components/course-pages';
function CourseMaterialsRoute() { return <CourseMaterialsPage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/materials')({ component: CourseMaterialsRoute });
