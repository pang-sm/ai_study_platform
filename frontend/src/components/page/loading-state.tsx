import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/**
 * Loading, in the shape of whatever is coming: blocks of skeleton rather than a spinner in the
 * middle of the page, plus one polite announcement for a screen reader (the skeleton itself is
 * hidden from assistive technology, since it carries no information).
 */
export function LoadingState({
  label,
  rows = 3,
  className,
}: {
  label: string;
  rows?: number;
  className?: string;
}) {
  return (
    <div className={cn('space-y-3', className)}>
      <p role="status" className="sr-only">
        {label}
      </p>
      <div aria-hidden="true" className="space-y-3">
        {Array.from({ length: rows }, (_, index) => (
          <Skeleton
            key={index}
            className={cn('h-4', index === 0 ? 'w-1/3' : index === rows - 1 ? 'w-2/3' : 'w-full')}
          />
        ))}
      </div>
    </div>
  );
}
