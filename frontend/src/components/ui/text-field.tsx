import type { ComponentProps } from 'react';
import { cn } from '@/lib/utils';

export interface TextFieldProps extends ComponentProps<'input'> {
  label: string;
  error?: string;
  hint?: string;
}

/**
 * A labelled text control with its error text wired to the input through `aria-describedby`, so
 * the message is read out as part of the field rather than passing by as loose text. `type` and
 * every other native attribute are passed through unchanged.
 */
export function TextField({ label, error, hint, id, className, ...props }: TextFieldProps) {
  const inputId = id ?? props.name;
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ');

  return (
    <div>
      <label htmlFor={inputId} className="block text-body font-medium text-text-primary">
        {label}
      </label>
      {hint ? (
        <p id={hintId} className="mt-1 text-metadata text-text-muted">
          {hint}
        </p>
      ) : null}
      <input
        {...props}
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={cn(
          'mt-2 h-11 w-full rounded-control border bg-surface px-3 text-body text-text-primary',
          'placeholder:text-text-muted',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2',
          error ? 'border-danger' : 'border-border-default',
          className,
        )}
      />
      {error ? (
        <p id={errorId} role="alert" className="mt-2 text-metadata text-danger-ink">
          {error}
        </p>
      ) : null}
    </div>
  );
}
