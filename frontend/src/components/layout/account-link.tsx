import { Link } from '@tanstack/react-router';
import { UserRound } from 'lucide-react';
import { useAuth } from '@/features/auth/auth-context';

export function AccountLink() {
  const auth = useAuth();

  if (!auth.isAuthenticated || !auth.user) {
    return (
      <Link to="/login" className="rounded-control px-3 py-2 text-body text-lab-paper transition-colors hover:bg-white/10">
        登录
      </Link>
    );
  }

  const displayName = auth.user.username;

  return (
    <Link
      to="/profile"
      title={displayName}
      aria-label={`个人中心：${displayName}`}
      className="inline-flex max-w-[min(13rem,42vw)] min-w-0 items-center gap-2 rounded-control px-2 py-2 text-body text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent"
    >
      <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-white/10" aria-hidden="true">
        <UserRound className="size-4" />
      </span>
      <span className="min-w-0 truncate">{displayName}</span>
    </Link>
  );
}
