import { cn } from '@/lib/utils';

export function Spinner({
  className,
  label = '加载中',
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span
      role="status"
      aria-label={label}
      className={cn(
        'inline-block size-4 animate-spin rounded-full border-2 border-border-default border-t-primary',
        className,
      )}
    />
  );
}
