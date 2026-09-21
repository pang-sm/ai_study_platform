import { Button } from './button';

/**
 * The one submit row for a settings-style form: the action, then whatever the last attempt said.
 *
 * The three states are mutually exclusive by construction — a form that is still saving cannot
 * also be reporting that it saved — so they are rendered from one row instead of three places
 * that could each disagree about which is current. The two messages carry different roles on
 * purpose: a success is a polite `status`, a failure interrupts as an `alert`.
 */
export function SaveRow({
  label = '保存',
  pendingLabel = '正在保存…',
  isPending,
  saved,
  savedLabel = '已保存。',
  error,
}: {
  label?: string;
  pendingLabel?: string;
  isPending: boolean;
  saved: boolean;
  savedLabel?: string;
  error: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <Button type="submit" disabled={isPending}>
        {isPending ? pendingLabel : label}
      </Button>
      {saved ? (
        <p role="status" className="text-body text-success-ink">
          {savedLabel}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-body text-danger-ink">
          {error}
        </p>
      ) : null}
    </div>
  );
}
