import { createFileRoute } from '@tanstack/react-router';
import { ProfilePage } from '@/features/profile/components/profile-page';
import { isProfileSectionId } from '@/features/profile/components/profile-sections';

/**
 * `section` is the one piece of the档案's state that belongs in the address bar.
 *
 * The page is a single scroll of eight sections, so "which section am I looking at" used to
 * live only in the scroll position — and a learner sent here by a setup flow ("学习设置" → 设置课程
 * → back) landed at the top, on 个人信息, with no way to say where they had meant to go. Carrying
 * it as a search param makes the destination addressable, shareable and survivable across a
 * refresh; an unknown or absent value is simply no section, which is the top of the page.
 */
export const Route = createFileRoute('/profile')({
  validateSearch: (search: Record<string, unknown>) => {
    const section = search.section;
    return typeof section === 'string' && isProfileSectionId(section) ? { section } : {};
  },
  component: ProfilePage,
});
