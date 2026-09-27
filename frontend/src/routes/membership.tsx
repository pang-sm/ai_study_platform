import { Outlet, createFileRoute } from '@tanstack/react-router';

/**
 * The membership section is a LAYOUT, not a page.
 *
 * It used to render `<MembershipPage />` directly, which made `/membership/payment` a child of a
 * parent that never rendered its children: the route existed in the generated tree, the URL
 * matched, and the payment page was never mounted — the learner stayed on the membership page
 * with no error and no warning. `exam` / `course` / `programming` are all written as layouts; the
 * membership section now composes the same way, so a child route cannot be swallowed again.
 */
export const Route = createFileRoute('/membership')({
  component: Outlet,
});
