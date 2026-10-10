import { createFileRoute } from '@tanstack/react-router';
import { ProfilePage } from '@/features/profile/components/profile-page';
import { isProfileSectionId } from '@/features/profile/components/profile-sections';

/**
 * `section` is the one piece of the档案's state that belongs in the address bar.
 *
 * Personal-center section state lives in the URL so setup flows can return to the correct place.
 * An unknown or absent value opens the first section.
 */
export const Route = createFileRoute('/profile')({
  validateSearch: (search: Record<string, unknown>) => {
    const section = search.section;
    return typeof section === 'string' && isProfileSectionId(section) ? { section } : {};
  },
  component: ProfilePage,
});
