/**
 * The auth keys live in their own module so that `api/auth.ts` and `session-cache.ts` can both
 * name the session entry without importing each other.
 */
export const authKeys = {
  session: ['auth', 'session'] as const,
};
