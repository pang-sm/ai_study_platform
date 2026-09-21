import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { evictUserPrivateQueries } from '../session-cache';
import { authKeys } from '../query-keys';
import { meEnvelopeSchema, type AuthUser } from './user-profile';

export { authKeys };
export type { AuthUser };

/**
 * The one session probe.
 *
 * Only a definitive refusal — 401/403 — answers `null`, because that is the normal answer to a
 * question the app is allowed to ask and not a failure the caller should have to catch. A
 * network failure, an unexpected status, or a body that is not the session envelope all THROW
 * instead. Treating any of those as "signed out" would let a captive portal, a proxy block page
 * or a backend regression silently present every visitor as a signed-out user, and would send a
 * signed-in learner to a login screen without a word.
 */
export async function fetchSession(): Promise<AuthUser | null> {
  const { data, error, response } = await apiClient.POST('/me', { body: {} });
  if (response.status === 401 || response.status === 403) return null;
  if (!response.ok) throw new ApiRequestError(response.status, error);
  const parsed = meEnvelopeSchema.safeParse(data);
  if (!parsed.success) throw new ApiRequestError(response.status, data);
  return parsed.data.user;
}

export function useSession() {
  return useQuery({
    queryKey: authKeys.session,
    queryFn: fetchSession,
    staleTime: 60_000,
    retry: false,
  });
}

export type LoginInput = components['schemas']['UserLogin'];

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: LoginInput) => {
      const { data, error, response } = await apiClient.POST('/login', { body: input });
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
    onSuccess: () => {
      // A different account's facts may already be cached under these keys, so the session
      // is re-read and every user-private entry is dropped rather than trusted.
      evictUserPrivateQueries(queryClient);
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

export type EmailLoginSendInput = components['schemas']['EmailLoginSendCodeRequest'];
export type EmailLoginInput = components['schemas']['EmailLoginRequest'];

/**
 * The emailed-code sign-in, as two steps: ask for a code, then present it.
 *
 * The code is mailed to the address already verified on an account (`_user_by_verified_email`),
 * so this is a second way into an existing account, never a way to create one — there is no
 * sign-up path here and the screen must not imply one. Delivery depends on the deployment having
 * SMTP configured; when it does not, the backend answers 503 with its own sentence and that
 * sentence is what the learner reads.
 */
export function useSendLoginCode() {
  return useMutation({
    mutationFn: async (input: EmailLoginSendInput) => {
      const { data, error, response } = await apiClient.POST('/auth/email-login/send-code', {
        body: input,
      });
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
  });
}

/** Step 2: the code is consumed and a real session cookie is set — the same one `/login` sets. */
export function useEmailLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: EmailLoginInput) => {
      const { data, error, response } = await apiClient.POST('/auth/email-login', { body: input });
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
    onSuccess: () => {
      // Same reason as the password flow: another account's facts may already be cached.
      evictUserPrivateQueries(queryClient);
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await apiClient.POST('/logout', {});
      if (!response.ok) throw new ApiRequestError(response.status, error);
    },
    onSettled: () => {
      evictUserPrivateQueries(queryClient);
      queryClient.setQueryData(authKeys.session, null);
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

export type RegisterEmailSendInput = components['schemas']['RegisterEmailSendCodeRequest'];
export type RegisterEmailVerifyInput = components['schemas']['RegisterEmailVerifyRequest'];
export type RegisterInput = components['schemas']['UserCreate'];

/** Step 1 of registration: a code is mailed to the address before any account exists. */
export function useSendRegisterCode() {
  return useMutation({
    mutationFn: async (input: RegisterEmailSendInput) => {
      const { data, error, response } = await apiClient.POST('/auth/register/send-code', {
        body: input,
      });
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
  });
}

/**
 * Step 2: verifying the code is what sets the `register_email_proof` cookie that
 * `POST /register` demands. Without a completed verification the backend answers
 * `400 请先完成邮箱验证`, so the page must not offer step 3 before this resolves.
 */
export function useVerifyRegisterCode() {
  return useMutation({
    mutationFn: async (input: RegisterEmailVerifyInput) => {
      const { data, error, response } = await apiClient.POST('/auth/register/verify-code', {
        body: input,
      });
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: RegisterInput) => {
      const { data, error, response } = await apiClient.POST('/register', { body: input });
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
    onSuccess: () => {
      evictUserPrivateQueries(queryClient);
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}
