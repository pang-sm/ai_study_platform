import { createFileRoute } from '@tanstack/react-router';
import { CourseSetupPage } from '@/features/course/components/course-setup-page';
import { sanitizeReturnTo } from '@/features/auth/return-to';

export const Route = createFileRoute('/course/setup')({
  // Validated where it enters the app, under the same rule `/login` uses; nothing downstream
  // has to remember that it came from the address bar.
  validateSearch: (search: Record<string, unknown>) => {
    const returnTo = sanitizeReturnTo(search.returnTo);
    return returnTo ? { returnTo } : {};
  },
  component: CourseSetupRoute,
});

function CourseSetupRoute() {
  const { returnTo } = Route.useSearch();
  return <CourseSetupPage returnTo={returnTo} />;
}
