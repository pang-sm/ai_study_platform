import { Badge } from '@/components/ui/badge';

export type SubjectAvailability = 'active' | 'framework_only';

const labels: Record<SubjectAvailability, string> = {
  // "内容已开放" and not "可学习": the catalogue's `active` flag says real content exists, which
  // is not the same claim as this build having a page to study it on. The page a learner lands on
  // is what says whether they can study it.
  active: '内容已开放',
  framework_only: '内容建设中',
};

export function SubjectAvailabilityBadge({ availability }: { availability: SubjectAvailability }) {
  return <Badge tone={availability === 'active' ? 'success' : 'neutral'}>{labels[availability]}</Badge>;
}
