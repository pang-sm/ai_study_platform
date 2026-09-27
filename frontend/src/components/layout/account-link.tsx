import { Link } from '@tanstack/react-router';
import { UserRound } from 'lucide-react';
import { useAuth } from '@/features/auth/auth-context';

/**
 * The learner's own name, and a door to their profile.
 *
 * It used to be a disclosure holding three links. Every one of those destinations lives on the
 * profile page — the archive, the membership and usage record, and signing out — so the panel
 * was a second copy of one page's table of contents, and the copy had to be kept in step with
 * it. Clicking the name now opens that page directly, which is what the panel was for.
 */
export function AccountLink() {
  const auth = useAuth();

  if (!auth.isAuthenticated || !auth.user) {
    // Only reachable if a shell is rendered for a signed-out visitor, which the route guard
    // otherwise prevents. Offering the action is cheaper than rendering an empty control.
    return (
      <Link
        to="/login"
        className="rounded-control px-3 py-2 text-body text-lab-paper transition-colors hover:bg-white/10"
      >
        登录
      </Link>
    );
  }

  const displayName = auth.user.nickname || auth.user.username;

  return (
    <Link
      to="/profile"
      // The accessible name is the learner's own at every width. A phone's header carries a
      // mark, this control and the navigation control, so only the mark and the icon survive
      // there — but the control must still announce whose profile it opens.
      aria-label={`打开学习档案：${displayName}`}
      className="inline-flex items-center gap-1.5 rounded-control px-2 py-2 text-body text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent"
    >
      <UserRound className="size-6 sm:hidden" aria-hidden="true" />
      <span className="hidden max-w-[9rem] truncate sm:inline">{displayName}</span>
    </Link>
  );
}
