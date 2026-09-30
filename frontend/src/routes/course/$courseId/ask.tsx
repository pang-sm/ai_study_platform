import { createFileRoute } from '@tanstack/react-router';
import { ScopedAiChatWorkspace } from '@/features/ai/components/ai-chat-page';
import { CoursePageShell } from '@/features/course/components/course-page-shell';

/**
 * The course's assistant, inside the course.
 *
 * `knowledge_point_id` and `knowledge_point_title` arrive from 学习 when the learner opened the
 * assistant from a point they were reading. The id is the turn's identity — it is what the
 * platform records and what the model is told the question is about — while the title is how the
 * page that linked here named it, and only ever display text. The composer stays EMPTY: the point
 * is the question's context, not a question asked on the learner's behalf.
 */
function pointIdFrom(value: unknown): number | undefined {
  if (typeof value === 'number') return Number.isInteger(value) && value > 0 ? value : undefined;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined;
  }
  return undefined;
}

/** Both keys are OPTIONAL: the assistant is reachable without a point, and that is its usual case. */
type CourseAskSearch = {
  knowledge_point_id?: number;
  knowledge_point_title?: string;
};

export const Route = createFileRoute('/course/$courseId/ask')({
  validateSearch: (search: Record<string, unknown>): CourseAskSearch => ({
    knowledge_point_id: pointIdFrom(search.knowledge_point_id),
    knowledge_point_title: typeof search.knowledge_point_title === 'string'
      && search.knowledge_point_title.trim()
      ? search.knowledge_point_title
      : undefined,
  }),
  component: CourseAskRoute,
});

function CourseAskRoute() {
  const { courseId } = Route.useParams();
  const { knowledge_point_id: knowledgePointId, knowledge_point_title: knowledgePointTitle } =
    Route.useSearch();
  const point = knowledgePointId === undefined
    ? undefined
    : { id: String(knowledgePointId), title: knowledgePointTitle ?? String(knowledgePointId) };

  return (
    <CoursePageShell courseId={courseId} active="ask">
      <ScopedAiChatWorkspace
        scope={{
          kind: 'course',
          courseId,
          label: courseId,
          knowledgePoint: point?.id,
          knowledgePointTitle: point?.title,
        }}
        embedded
        contextNote={point ? `当前围绕：${point.title}` : undefined}
      />
    </CoursePageShell>
  );
}
