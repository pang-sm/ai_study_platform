import { useEffect, useId, useRef, useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { ChevronDown } from 'lucide-react';
import { useAuth } from '@/features/auth/auth-context';
import { useLogout } from '@/features/auth/api/auth';

/**
 * A disclosure rather than a `menu` role: the panel holds ordinary links, and the disclosure
 * pattern keeps the trigger's `aria-expanded` as the single source of truth about visibility.
 */
export function AccountMenu() {
  const auth = useAuth();
  const logout = useLogout();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

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

  const onLogout = async () => {
    setOpen(false);
    try {
      await logout.mutateAsync();
    } finally {
      await navigate({ to: '/login' });
    }
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 rounded-control px-2 py-2 text-body text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent"
      >
        <span className="max-w-[9rem] truncate">{displayName}</span>
        <ChevronDown className="size-4" aria-hidden="true" />
      </button>

      {open ? (
        <div
          id={panelId}
          className="absolute right-0 z-20 mt-2 w-56 rounded-card border border-border-default bg-surface p-2 shadow-card"
        >
          <p className="px-3 py-2 text-metadata text-text-muted">账号：{auth.user.username}</p>
          <nav aria-label="账户">
            <Link
              to="/profile"
              className="block rounded-control px-3 py-2 text-body text-text-primary hover:bg-primary-soft"
            >
              学习档案
            </Link>
            <Link
              to="/membership"
              className="block rounded-control px-3 py-2 text-body text-text-primary hover:bg-primary-soft"
            >
              会员与用量
            </Link>
          </nav>
          <button
            type="button"
            onClick={onLogout}
            disabled={logout.isPending}
            className="mt-1 block w-full rounded-control px-3 py-2 text-left text-body text-text-primary hover:bg-primary-soft disabled:opacity-50"
          >
            {logout.isPending ? '正在退出…' : '退出登录'}
          </button>
        </div>
      ) : null}
    </div>
  );
}
