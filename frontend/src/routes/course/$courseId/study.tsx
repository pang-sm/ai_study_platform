import { createFileRoute } from '@tanstack/react-router';
import { CourseStudyPage } from '@/features/course/components/course-study-page';

/**
 * The knowledge point the learner has open, when the page names one.
 *
 * It is kept as a NUMBER rather than coerced to a string: the router quotes a numeric-looking
 * STRING back into the URL, so `?knowledge_point_id=12` validated as `"12"` would be written
 * back as `?knowledge_point_id=%2212%22`. A point id is a number on the server, so it is a
 * number here.
 *
 * An absent value is not an error — it means "no point has been chosen yet", and the page
 * answers that by opening the one the learner's own record suggests, then writing it here.
 */
function pointIdFrom(value: unknown): number | undefined {
  if (typeof value === 'number') return Number.isInteger(value) && value > 0 ? value : undefined;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
  }
  return undefined;
}

export const Route = createFileRoute('/course/$courseId/study')({
  validateSearch: (search: Record<string, unknown>) => ({
    knowledge_point_id: pointIdFrom(search.knowledge_point_id),
  }),
  component: CourseStudyRoute,
});

function CourseStudyRoute() {
  const { courseId } = Route.useParams();
  const { knowledge_point_id: knowledgePointId } = Route.useSearch();
  return <CourseStudyPage courseId={courseId} selectedPointId={knowledgePointId} />;
}
