import { cn } from '@/lib/utils';

export type SubjectAvailability = 'active' | 'framework_only';

const labels: Record<SubjectAvailability, string> = {
  active: '可学习',
  framework_only: '内容建设中',
};

const classes: Record<SubjectAvailability, string> = {
  active: 'border-success/25 bg-success-soft text-emerald-800',
  framework_only: 'border-warning/30 bg-warning-soft text-text-secondary',
};

export function SubjectAvailabilityBadge({ availability }: { availability: SubjectAvailability }) {
  return (
    <span className={cn('inline-flex min-h-6 items-center border px-2 text-metadata font-medium', classes[availability])}>
      {labels[availability]}
    </span>
  );
}
