import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSession, type AuthUser } from './api/auth';
import { authKeys } from './query-keys';

export type AuthState = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  isError: boolean;
  /** Re-reads the session from the server. Used after a login or logout completes. */
  refresh: () => Promise<unknown>;
};

const AuthContext = createContext<AuthState | null>(null);

/**
 * The single authority on "is this visitor signed in".
 *
 * Components read this instead of probing `/me` themselves, so one slow or failed probe cannot
 * disagree with another about the same browser. The route guard reads the SAME query key
 * through the router context, so a guard decision and a rendered header can never disagree.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const session = useSession();
  const queryClient = useQueryClient();

  const value = useMemo<AuthState>(
    () => ({
      user: session.data ?? null,
      isAuthenticated: Boolean(session.data),
      isLoading: session.isPending,
      isError: session.isError,
      refresh: () => queryClient.refetchQueries({ queryKey: authKeys.session }),
    }),
    [session.data, session.isPending, session.isError, queryClient],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return value;
}
