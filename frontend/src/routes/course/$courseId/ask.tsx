import { createFileRoute } from '@tanstack/react-router';
import { ScopedAiChatWorkspace } from '@/features/ai/components/ai-chat-page';
import { CoursePageShell } from '@/features/course/components/course-page-shell';

function CourseAskRoute() {
  const { courseId } = Route.useParams();
  return (
    <CoursePageShell courseId={courseId} active="ask">
      <ScopedAiChatWorkspace scope={{ kind: 'course', courseId, label: courseId }} embedded />
    </CoursePageShell>
  );
}
export const Route = createFileRoute('/course/$courseId/ask')({ component: CourseAskRoute });
