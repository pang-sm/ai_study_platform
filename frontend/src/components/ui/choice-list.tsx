import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

type ChoiceRowProps = {
  type: 'checkbox' | 'radio';
  name: string;
  value: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  /** A short fact that belongs beside the label — a count, a state. Never a second label. */
  meta?: ReactNode;
};

/**
 * A row in a set of native inputs.
 *
 * The input is a real `<input>` of the caller's type, so keyboard operation, grouping and the
 * checked state announced by assistive technology are the platform's, not this component's. The
 * whole row is the label, which makes the target large enough to hit on a phone; the visible text
 * is the row's content, so nothing here needs an `aria-label` that could drift from it.
 */
function ChoiceRow({ type, name, value, checked, onChange, children, meta }: ChoiceRowProps) {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-start gap-3 border-b border-border-default py-3',
        'has-[:focus-visible]:outline-none has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary has-[:focus-visible]:ring-offset-2',
      )}
    >
      <input
        type={type}
        name={name}
        value={value}
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 shrink-0 accent-primary focus-visible:outline-none"
      />
      <span className="min-w-0 flex-1 text-body text-text-primary">{children}</span>
      {meta ? <span className="shrink-0 text-metadata text-text-secondary">{meta}</span> : null}
    </label>
  );
}

export function CheckboxRow(props: Omit<ChoiceRowProps, 'type'>) {
  return <ChoiceRow {...props} type="checkbox" />;
}

export function RadioRow(props: Omit<ChoiceRowProps, 'type'>) {
  return <ChoiceRow {...props} type="radio" />;
}
