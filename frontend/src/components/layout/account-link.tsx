import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { ChevronDown, UserRound } from 'lucide-react';
import { useLogout } from '@/features/auth/api/auth';
import { useAuth } from '@/features/auth/auth-context';

export function AccountLink() {
  const auth = useAuth();
  const logout = useLogout();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    const onPointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown);
    firstLinkRef.current?.focus({ preventScroll: true });
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [open]);

  if (!auth.isAuthenticated || !auth.user) {
    return (
      <Link to="/login" className="rounded-control px-3 py-2 text-body text-lab-paper transition-colors hover:bg-white/10">
        登录
      </Link>
    );
  }

  const displayName = auth.user.username;
  const close = () => setOpen(false);
  const onLogout = async () => {
    try {
      await logout.mutateAsync();
    } finally {
      close();
      await navigate({ to: '/login' });
    }
  };

  return (
    <div ref={rootRef} className="relative min-w-0">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls="account-menu"
        aria-label={`账号菜单：${displayName}`}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex max-w-[min(13rem,42vw)] items-center gap-2 rounded-control px-2 py-2 text-body text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent"
      >
        <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-pill bg-white/10" aria-hidden="true">
          <UserRound className="size-4" />
        </span>
        <span className="min-w-0 truncate">{displayName}</span>
        <ChevronDown className="size-4 shrink-0" aria-hidden="true" />
      </button>
      {open ? (
        <div id="account-menu" className="absolute right-0 top-full z-40 mt-2 w-64 max-w-[calc(100vw-2rem)] rounded-card border border-border-default bg-surface p-2 text-text-primary shadow-card">
          <div className="border-b border-border-default px-3 py-2">
            <p className="break-all text-body font-medium" data-account-full-name>{auth.user.username}</p>
            {auth.user.nickname && auth.user.nickname !== auth.user.username ? (
              <p className="truncate text-metadata text-text-secondary">{auth.user.nickname}</p>
            ) : null}
          </div>
          <nav aria-label="账号菜单" className="grid gap-1 py-1">
            <Link ref={firstLinkRef} to="/profile" onClick={close} className="rounded-control px-3 py-2 text-body hover:bg-neutral-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">个人中心</Link>
            <Link to="/membership" onClick={close} className="rounded-control px-3 py-2 text-body hover:bg-neutral-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">会员与额度</Link>
            <button type="button" onClick={() => void onLogout()} disabled={logout.isPending} className="rounded-control px-3 py-2 text-left text-body text-danger-ink hover:bg-danger-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60">
              {logout.isPending ? '正在退出…' : '退出登录'}
            </button>
          </nav>
        </div>
      ) : null}
    </div>
  );
}
