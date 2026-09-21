import { createFileRoute } from '@tanstack/react-router';
import { CourseKnowledgePage } from '@/features/course/components/course-pages';
function CourseKnowledgeRoute() { return <CourseKnowledgePage courseId={Route.useParams().courseId} />; }
export const Route = createFileRoute('/course/$courseId/knowledge')({ component: CourseKnowledgeRoute });
