import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { Menu, X } from 'lucide-react';
import { AccountLink } from './account-link';
import { PrimaryNav } from './primary-nav';

/**
 * The product shell: one branded header, one row of destinations, and the page below it.
 *
 * There is no column beside the content any more. A permanent sidebar spent a fifth of a wide
 * screen restating seven links the header can hold in one line, and on a narrow one it either
 * disappeared or had to be opened anyway — so the same navigation now lives in the header at
 * both sizes, and the content owns the full width everywhere.
 *
 * Below the width where seven names fit, the header's control opens the panel. The panel is a
 * real disclosure rendered into the document, not a modal: there is no backdrop and no focus
 * trap, so Escape, the control and a click elsewhere all close it, and each returns focus to
 * the control that opened it.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  // Closing has three causes — Escape, the toggle, and a click outside — and all three have to
  // hand focus back to the same place. Recording that here, rather than in each handler, is what
  // keeps them from disagreeing.
  const restoreFocus = useRef(false);
  // Whether the press that is about to become a click began inside this widget.
  //
  // It has to be recorded at press time, not read off the click's target: opening the panel
  // replaces the control's icon, and the node that was pressed is detached by the time the click
  // finishes bubbling. `contains()` on a detached node is false for its own ancestors, so asking
  // at click time answered "outside" for the very click that opened the panel — and the panel
  // closed on the same interaction that asked for it.
  const pressStartedInside = useRef(false);

  // Registered from mount, not while the panel is open: the press that OPENS the panel happens
  // before this state exists, so a recorder that only listened while open would misread the
  // opening press as coming from outside and close the panel on the same interaction.
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      pressStartedInside.current = Boolean(
        target && (panelRef.current?.contains(target) || triggerRef.current?.contains(target)),
      );
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      restoreFocus.current = true;
      setMenuOpen(false);
    };
    // The close is decided at click time rather than at press time because the browser moves
    // focus as part of the press, and that move lands after a pointerdown handler has run.
    // Deciding at click time means the decision is made on the focus the interaction actually
    // left behind: if it went to something the learner aimed at, focus stays there; if it was
    // dropped onto the document, it comes back to the control that owns this panel.
    const onClick = () => {
      const startedInside = pressStartedInside.current;
      pressStartedInside.current = false;
      if (startedInside) return;
      const active = document.activeElement;
      restoreFocus.current = active === null || active === document.body;
      setMenuOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('click', onClick);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('click', onClick);
    };
  }, [menuOpen]);

  // Focus goes into the navigation once it exists, so the next Tab continues inside the panel
  // instead of walking the page behind it. It is set with `preventScroll` because the panel is
  // already on screen; scrolling would move the page for a reason the learner did not ask for.
  useEffect(() => {
    if (menuOpen) panelRef.current?.querySelector<HTMLElement>('a[href]')?.focus({ preventScroll: true });
  }, [menuOpen]);

  // ...and comes back to the control that opened it, but only when the close was caused by an
  // interaction. An unmount or a route change must not pull the caret to the header.
  useEffect(() => {
    if (menuOpen || !restoreFocus.current) return;
    restoreFocus.current = false;
    triggerRef.current?.focus({ preventScroll: true });
  }, [menuOpen]);

  return (
    <div className="min-h-screen bg-page-background text-text-primary">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-3 focus:z-50 focus:rounded-control focus:bg-surface focus:px-4 focus:py-2 focus:text-body focus:text-primary-ink"
      >
        跳到主要内容
      </a>

      <header className="sticky top-0 z-30 border-b border-lab-grid/60 bg-lab-ink text-lab-paper">
        <div className="mx-auto flex h-20 w-full max-w-content items-center gap-4 px-5 sm:px-8 lg:px-12">
          {/* The mark is set at brand scale rather than at the size that merely fits the bar:
              it is the one piece of identity on every page, so it carries the header instead of
              sitting in it as a control-sized thumbnail. */}
          <Link to="/" className="inline-flex shrink-0 items-center" aria-label="智学平台首页">
            <img
              src="/brand/zhixue-v2/08_智学平台_Desktop_Header_Lockup.png"
              alt="智学平台"
              className="hidden h-[54px] w-auto object-contain lg:block"
            />
            <img
              src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png"
              alt="智学平台"
              className="size-11 object-contain lg:hidden"
            />
          </Link>

          <div className="hidden min-w-0 flex-1 lg:block">
            <PrimaryNav variant="header" />
          </div>

          <div className="ml-auto flex items-center gap-2 lg:ml-4">
            <AccountLink />
            <button
              ref={triggerRef}
              type="button"
              aria-expanded={menuOpen}
              aria-controls={panelId}
              onClick={() => {
                restoreFocus.current = menuOpen;
                setMenuOpen((value) => !value);
              }}
              className="inline-flex size-11 items-center justify-center rounded-control text-lab-paper transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent lg:hidden"
            >
              <span className="sr-only">{menuOpen ? '关闭导航菜单' : '打开导航菜单'}</span>
              {menuOpen ? (
                <X className="size-6" aria-hidden="true" />
              ) : (
                <Menu className="size-6" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </header>

      {menuOpen ? (
        <div
          ref={panelRef}
          id={panelId}
          className="fixed bottom-0 left-0 right-0 top-20 z-20 overflow-y-auto border-b border-border-default bg-lab-ink pb-8 text-lab-paper lg:hidden"
        >
          <PrimaryNav
            variant="drawer"
            ariaLabel="主导航（移动）"
            onNavigate={() => {
              // Following a destination removes the panel and the link inside it, so without
              // this the browser would drop focus onto the document body.
              restoreFocus.current = true;
              setMenuOpen(false);
            }}
          />
        </div>
      ) : null}

      <main id="main-content">{children}</main>
    </div>
  );
}
