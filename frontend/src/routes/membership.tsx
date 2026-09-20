import { createFileRoute } from '@tanstack/react-router';
import { MembershipPage } from '@/features/membership/components/membership-page';

export const Route = createFileRoute('/membership')({
  component: MembershipRoute,
});

function MembershipRoute() {
  return <MembershipPage />;
}
