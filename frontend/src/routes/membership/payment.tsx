import { createFileRoute } from '@tanstack/react-router';
import { MembershipPaymentPage } from '@/features/membership/components/payment-page';
import { isOrderableTier, ORDERABLE_TIERS, type OrderableTier } from '@/features/membership/api/subscription';

/**
 * `tier` is required, and there is no default.
 *
 * A payment page that guessed which tier was being bought would be a checkout that can charge for
 * something the learner did not choose — so an absent or unorderable tier is not coerced into one.
 * The route falls back to the first orderable tier only so the page has something to render, and
 * it says which tier that is on screen.
 */
export const Route = createFileRoute('/membership/payment')({
  validateSearch: (search: Record<string, unknown>): { tier: OrderableTier } => ({
    tier: isOrderableTier(search.tier) ? search.tier : ORDERABLE_TIERS[0],
  }),
  component: PaymentRoute,
});

function PaymentRoute() {
  const { tier } = Route.useSearch();
  return <MembershipPaymentPage tier={tier} />;
}
