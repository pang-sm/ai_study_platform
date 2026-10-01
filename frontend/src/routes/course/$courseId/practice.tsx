import { createFileRoute } from '@tanstack/react-router';
import { CoursePracticePage } from '@/features/course/components/course-practice-page';

/**
 * The practice surface, and the identity of the set it is on.
 *
 * `point` / `chapter` are the ACTIVE knowledge structure's own node ids, sent by 知识结构 when
 * the learner pressed 开始练习 beside one of them — they preselect the generation scope, so the
 * page never asks somebody who just chose a point which point they meant.
 *
 * `session` names the set to show: the open one a reload resumes, or a finished one a history
 * row opens. It is in the URL rather than in component state so that a reload, a bookmark or a
 * shared link lands on the same set instead of on the entry screen.
 */
type CoursePracticeSearch = { point?: number; chapter?: number; session?: number };

function nodeId(value: unknown): number | undefined {
  const parsed = typeof value === 'number' ? value : Number.parseInt(String(value ?? ''), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
}

export const Route = createFileRoute('/course/$courseId/practice')({
  validateSearch: (search: Record<string, unknown>): CoursePracticeSearch => ({
    point: nodeId(search.point),
    chapter: nodeId(search.chapter),
    session: nodeId(search.session),
  }),
  component: CoursePracticeRoute,
});

function CoursePracticeRoute() {
  const { courseId } = Route.useParams();
  const { point, chapter, session } = Route.useSearch();
  return (
    <CoursePracticePage
      courseId={courseId}
      pointId={point}
      chapterId={chapter}
      sessionId={session}
    />
  );
}
