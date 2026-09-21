import { useId, useRef, useState, type ComponentProps, type MutableRefObject, type Ref } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface PasswordFieldProps extends Omit<ComponentProps<'input'>, 'type'> {
  label: string;
  error?: string;
  hint?: string;
}

/**
 * The caller's `ref` and this component's own, on one node.
 *
 * The field needs the element to put the caret back after a reveal; the caller — react-hook-form
 * in every use — needs it to read the value. Assigning only one of them would leave the other
 * pointing at nothing, which is what makes a registered field silently submit as `undefined`.
 */
function mergeRefs<T>(...refs: readonly (Ref<T> | undefined)[]): (node: T | null) => void {
  return (node) => {
    for (const ref of refs) {
      if (!ref) continue;
      if (typeof ref === 'function') ref(node);
      else (ref as MutableRefObject<T | null>).current = node;
    }
  };
}

/**
 * A password control whose reveal toggle is a real control rather than a re-typed field.
 *
 * The toggle flips the input's `type` between `password` and `text` and nothing else — the input
 * element itself is never replaced, so the browser's autofill and the password manager's own
 * affordances keep working, and `autoComplete` reaches the input untouched.
 *
 * The layout is a grid with the parts placed explicitly rather than in source order. Visually the
 * toggle sits on the label's line, at the right; in the DOM it comes *after* the input, so the
 * keyboard reaches the field first and the control that acts on it second. Marking it up in
 * visual order instead would put a button named "显示密码" before the password field in the tab
 * sequence, which is the wrong thing to meet first.
 *
 * It is a `<button type="button">` with its own visible text, so it is announced by name and
 * `aria-pressed` states which of the two it currently is.
 */
export function PasswordField({
  label,
  error,
  hint,
  id,
  className,
  ref,
  ...props
}: PasswordFieldProps) {
  const generatedId = useId();
  const inputId = id ?? props.name ?? generatedId;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ');
  const [revealed, setRevealed] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const attachRef = mergeRefs(ref, inputRef);

  const toggle = () => {
    setRevealed((current) => !current);
    // The toggle does not keep focus: it hands it back to the field it just changed, so the next
    // keystroke continues the password instead of activating the button again.
    const input = inputRef.current;
    if (!input) return;
    const { selectionStart, selectionEnd } = input;
    input.focus();
    if (selectionStart !== null && selectionEnd !== null) {
      input.setSelectionRange(selectionStart, selectionEnd);
    }
  };

  return (
    <div className={cn('grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2', className)}>
      <label
        htmlFor={inputId}
        className="col-start-1 row-start-1 block text-body font-medium text-text-primary"
      >
        {label}
      </label>

      <input
        {...props}
        ref={attachRef}
        id={inputId}
        type={revealed ? 'text' : 'password'}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={cn(
          'col-span-2 row-start-2 h-11 w-full rounded-control border bg-surface px-3 text-body text-text-primary',
          'placeholder:text-text-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
          error ? 'border-danger' : 'border-border-default',
        )}
      />

      <button
        type="button"
        onClick={toggle}
        aria-pressed={revealed}
        aria-controls={inputId}
        className={cn(
          'col-start-2 row-start-1 inline-flex min-h-6 items-center gap-1 rounded-control px-1',
          'text-metadata text-text-secondary hover:text-text-primary',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
        )}
      >
        {revealed ? (
          <EyeOff className="size-4" aria-hidden="true" />
        ) : (
          <Eye className="size-4" aria-hidden="true" />
        )}
        {revealed ? '隐藏密码' : '显示密码'}
      </button>

      {hint ? (
        <p id={hintId} className="col-span-2 row-start-3 text-metadata text-text-muted">
          {hint}
        </p>
      ) : null}

      {error ? (
        <p id={errorId} role="alert" className="col-span-2 row-start-4 text-metadata text-danger-ink">
          {error}
        </p>
      ) : null}
    </div>
  );
}
