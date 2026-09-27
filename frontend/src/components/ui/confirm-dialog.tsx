import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * A question with two answers, asked before something irreversible.
 *
 * Deliberately a question and not a form: the caller states what is about to happen in its own
 * words, this shows it, and the only two ways out are the two buttons. It is an `alertdialog`, so
 * a screen reader announces it as a prompt rather than as another region of the page.
 *
 * Portalled onto `document.body` and pinned with `fixed`, like the library picker and for the
 * same reason: inside a page's own card an overlay resolves against whatever ancestor happens to
 * be positioned, which is how a dialog ends up clipped or floating over the wrong half of a
 * scrolled page. The page behind it stops scrolling while it is open, and scrolling comes back
 * when it closes.
 */
export function ConfirmDialog({
  title,
  description,
  confirmLabel = '删除',
  cancelLabel = '取消',
  pending = false,
  onConfirm,
  onCancel,
}: {
  /** The question itself, naming what is being acted on. */
  title: string;
  /** What follows from answering yes. */
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** While the decision is being carried out the buttons stop accepting a second one. */
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  // Registered once, so an inline arrow from the caller cannot re-run the scroll-lock effect.
  const cancelHandler = useRef(onCancel);
  useEffect(() => { cancelHandler.current = onCancel; }, [onCancel]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    document.body.style.overflow = 'hidden';
    // Focus lands on the safe answer, not on the destructive one: a stray Enter must not delete.
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        cancelHandler.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!focusable?.length) return;
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, []);

  return createPortal(
    <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        className="w-[min(28rem,calc(100vw-2rem))] rounded-section border border-border-default bg-surface p-5 shadow-visual"
      >
        <h2 id={titleId} className="text-heading font-semibold text-text-primary">{title}</h2>
        {description ? (
          <p id={descriptionId} className="mt-2 text-body text-text-secondary">{description}</p>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="inline-flex h-10 items-center rounded-control px-4 text-body text-text-secondary hover:bg-page-background"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            disabled={pending}
            onClick={onConfirm}
            className="inline-flex h-10 items-center rounded-control bg-danger px-5 text-body font-medium text-white hover:opacity-90 disabled:opacity-50"
          >
            {pending ? '正在删除…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
