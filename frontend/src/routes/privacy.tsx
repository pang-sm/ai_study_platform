import { createFileRoute } from '@tanstack/react-router';
import { PrivacyPage } from '@/features/legal/privacy-page';

export const Route = createFileRoute('/privacy')({
  // Same reason as `/terms`: these documents are read before there is an account to sign in with.
  staticData: { layout: 'bare' },
  component: PrivacyPage,
});
