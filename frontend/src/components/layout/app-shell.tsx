import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link } from '@tanstack/react-router';
import { Menu, X } from 'lucide-react';
import { AccountMenu } from './account-menu';
import { BottomNav, PrimaryNav } from './primary-nav';

/**
 * The product shell: one identity, three learning spaces, and the capabilities they share.
 *
 * Wide screens get a persistent grouped column beside the content — the navigation is part of
 * the page rather than a menu to open. Below that width the same groups arrive as a panel the
 * header's control opens, and a phone additionally gets a bottom bar for the five destinations
 * a learner moves between most. The panel is a real disclosure rendered into the document; the
 * icon-only button it replaced opened nothing, so a phone had no navigation at all.
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
    // The panel is a disclosure, not a modal: content behind it stays reachable. That makes
    // "the click landed somewhere else" a real way out, and without this the panel would sit
    // open over the page it is no longer being used for.
    //
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
        <div className="flex h-16 items-center gap-4 px-4 sm:px-6">
          <Link to="/" className="inline-flex shrink-0 items-center" aria-label="智学平台首页">
            <img
              src="/brand/zhixue-v2/08_智学平台_Desktop_Header_Lockup.png"
              alt="智学平台"
              className="hidden h-[42px] w-auto object-contain sm:block"
            />
            <img
              src="/brand/zhixue-v2/04_智学平台_图标标识_Icon_Only_transparent.png"
              alt="智学平台"
              className="size-9 object-contain sm:hidden"
            />
          </Link>

          <div className="ml-auto flex items-center gap-2">
            <AccountMenu />
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
                <X className="size-5" aria-hidden="true" />
              ) : (
                <Menu className="size-5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </header>

      <div className="lg:flex">
        {/* Named so it is distinguishable from any other complementary landmark a page adds —
            `landmark-unique` is about the pair, and an unnamed one makes the whole set
            ambiguous to a screen reader's landmark list. */}
        <aside
          aria-label="学习空间导航"
          className="hidden shrink-0 border-r border-border-default bg-surface lg:block lg:w-sidebar"
        >
          <div className="sticky top-16 max-h-[calc(100vh-4rem)] overflow-y-auto py-6">
            <PrimaryNav variant="sidebar" />
            <div className="mx-3 mt-6 border-t border-border-default px-3 pt-5">
              <p className="text-metadata text-text-muted">
                一个账号、一套额度，三个学习空间共用。
              </p>
            </div>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          {menuOpen ? (
            // Still a disclosure rather than a modal: there is no backdrop and no focus trap, so
            // it closes on Escape or on the destination it opens. On a tablet it is a sheet the
            // width of the sidebar instead of a full takeover, because at that size the page
            // beside it is still readable and worth leaving visible.
            <div
              ref={panelRef}
              id={panelId}
              className="fixed bottom-0 left-0 top-16 z-20 w-full overflow-y-auto border-b border-border-default bg-surface sm:w-80 sm:border-b-0 sm:border-r lg:hidden"
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

          {/* The bottom bar owns the last strip of a phone's screen, so the content is padded
              clear of it rather than having its final line hidden underneath. */}
          <main id="main-content" className="pb-16 md:pb-0">
            {children}
          </main>
        </div>
      </div>

      <BottomNav />
    </div>
  );
}
