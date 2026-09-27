import { createFileRoute } from '@tanstack/react-router';
import { TermsPage } from '@/features/legal/terms-page';

export const Route = createFileRoute('/terms')({
  // Readable while signed out, exactly like the sign-in screens: someone has to be able to read
  // the terms before deciding to register, so this renders without the product shell.
  staticData: { layout: 'bare' },
  component: TermsPage,
});
