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
    // `search` is stated even though 课程问答 takes no parameters of its own: the route declares
    // a search schema (the knowledge point 学习 can hand it), so the router asks the redirect to
    // say what the empty case is rather than assume it.
    throw redirect({ to: '/course/$courseId/ask', params: { courseId: params.courseId }, search: {} });
  },
});
