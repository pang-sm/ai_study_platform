import type { QueryClient } from '@tanstack/react-query';
import { authKeys } from './query-keys';

/**
 * Query keys that carry NO user state and therefore survive a logout.
 *
 * This list is an ALLOW-list, not a deny-list: anything not named here is treated as
 * user-private and evicted. A missed entry costs one refetch after the next sign-in, while the
 * opposite default — keeping keys unless they are known-private — would leave one learner's
 * records readable by the next one on a shared browser.
 *
 * - `exam/catalog`                    the exam/subject catalog (same for every caller)
 * - `exam/subject-content-status/*`   whether a subject has content at all
 * - `exam/scientific-capabilities`    which scientific components are user-visible
 */
const PUBLIC_QUERY_KEYS: readonly (readonly unknown[])[] = [
  ['exam', 'catalog'],
  ['exam', 'subject-content-status'],
  ['exam', 'scientific-capabilities'],
];

function startsWithKey(queryKey: readonly unknown[], prefix: readonly unknown[]): boolean {
  return (
    prefix.length <= queryKey.length &&
    prefix.every((segment, index) => segment === queryKey[index])
  );
}

/**
 * Drops every user-private cache entry. Public catalog reads are left in place.
 *
 * The session entry itself is kept: it is written explicitly by the login and logout flows
 * (which must not be raced by an eviction that then re-fetches a value they already know).
 */
export function evictUserPrivateQueries(queryClient: QueryClient): void {
  queryClient.removeQueries({
    predicate: (query) => {
      if (startsWithKey(query.queryKey, authKeys.session)) return false;
      return !PUBLIC_QUERY_KEYS.some((publicKey) => startsWithKey(query.queryKey, publicKey));
    },
  });
}
