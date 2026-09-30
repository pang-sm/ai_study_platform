import { createFileRoute } from '@tanstack/react-router';
import { CoursePracticePage } from '@/features/course/components/course-pages';
import { searchIdentifier } from '@/lib/router';

/**
 * `chapter` narrows the practice book to the chapter 学习 sent the learner from.
 *
 * It is the CHAPTER, never the knowledge point: the workbook carries no mapping from a learner's
 * own structure points to questions, and passing a point id here would file a question under a
 * point it was never written for. Absent, the page is the whole course — which is what every
 * other route into it already showed.
 */
type CoursePracticeSearch = { chapter?: string | number };

export const Route = createFileRoute('/course/$courseId/practice')({
  validateSearch: (search: Record<string, unknown>): CoursePracticeSearch => ({
    chapter: searchIdentifier(search.chapter),
  }),
  component: CoursePracticeRoute,
});

function CoursePracticeRoute() {
  const { courseId } = Route.useParams();
  const { chapter } = Route.useSearch();
  return <CoursePracticePage courseId={courseId} chapter={typeof chapter === 'string' ? chapter : undefined} />;
}
