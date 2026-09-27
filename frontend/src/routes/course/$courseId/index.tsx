import { createFileRoute, redirect } from '@tanstack/react-router';

/**
 * The bare course path is not a page of its own any more.
 *
 * 概览 used to live here — a page that described the course's other tabs instead of being one of
 * them. Every link that still points at `/course/<id>` (a bookmark, an old history entry, the
 * home page's course rows) therefore lands on the course's own first working surface rather than
 * on a 404 or on a second description of the tabs.
 */
export const Route = createFileRoute('/course/$courseId/')({
  beforeLoad: ({ params }) => {
    throw redirect({ to: '/course/$courseId/ask', params: { courseId: params.courseId } });
  },
});
