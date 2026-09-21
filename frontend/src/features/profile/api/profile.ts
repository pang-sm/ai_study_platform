import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { authKeys } from '@/features/auth/query-keys';
import { profileEnvelopeSchema, type UserProfile } from '@/features/auth/api/user-profile';

export const profileKeys = {
  detail: ['profile', 'detail'] as const,
  subscription: ['profile', 'subscription'] as const,
  plans: ['profile', 'subscription-plans'] as const,
  usage: ['profile', 'usage'] as const,
};

function requireOk(response: Response, error: unknown): void {
  if (!response.ok) throw new ApiRequestError(response.status, error);
}

/**
 * `GET /me/profile` answers with `{profile: user_profile}` and is typed `unknown` by the
 * OpenAPI document, so it is parsed with the same reader the session uses. A response that does
 * not match is treated as absent rather than rendered half-read.
 */
export async function fetchProfile(): Promise<UserProfile> {
  const { data, error, response } = await apiClient.GET('/me/profile', {});
  requireOk(response, error);
  const parsed = profileEnvelopeSchema.safeParse(data);
  if (!parsed.success) throw new ApiRequestError(response.status, data);
  return parsed.data.profile;
}

export function useProfile() {
  return useQuery({ queryKey: profileKeys.detail, queryFn: fetchProfile, retry: false });
}

export type ProfileUpdateInput = components['schemas']['ProfileUpdateRequest'];

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProfileUpdateInput) => {
      const { data, error, response } = await apiClient.PUT('/me/profile', { body: input });
      requireOk(response, error);
      return data;
    },
    onSuccess: () => {
      // The session carries the same serializer, so both readers are refreshed together.
      void queryClient.invalidateQueries({ queryKey: profileKeys.detail });
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

export type SubscriptionState = components['schemas']['SubscriptionStateResponse'];
export type SubscriptionPlans = components['schemas']['PlanCatalogResponse'];
export type UsageSummary = components['schemas']['UsageSummaryResponse'];

export function useSubscription() {
  return useQuery({
    queryKey: profileKeys.subscription,
    queryFn: async (): Promise<SubscriptionState> => {
      const { data, error, response } = await apiClient.GET('/subscription', {});
      if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
      return data;
    },
    retry: false,
  });
}

export function useSubscriptionPlans() {
  return useQuery({
    queryKey: profileKeys.plans,
    queryFn: async (): Promise<SubscriptionPlans> => {
      const { data, error, response } = await apiClient.GET('/subscription/plans', {});
      if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
      return data;
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useUsageSummary() {
  return useQuery({
    queryKey: profileKeys.usage,
    queryFn: async (): Promise<UsageSummary> => {
      const { data, error, response } = await apiClient.GET('/usage/summary', {});
      if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
      return data;
    },
    retry: false,
  });
}

export type ChangePasswordInput = components['schemas']['ChangePasswordRequest'];

export function useChangePassword() {
  return useMutation({
    mutationFn: async (input: ChangePasswordInput) => {
      const { data, error, response } = await apiClient.PUT('/me/password', { body: input });
      requireOk(response, error);
      return data;
    },
  });
}

export type VerifyEmailInput = components['schemas']['VerifyEmailRequest'];

export function useSendEmailCode() {
  return useMutation({
    mutationFn: async (email: string) => {
      const { data, error, response } = await apiClient.POST('/me/email/send-code', {
        body: { email },
      });
      requireOk(response, error);
      return data;
    },
  });
}

export function useVerifyEmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: VerifyEmailInput) => {
      const { data, error, response } = await apiClient.PUT('/me/email/verify', { body: input });
      requireOk(response, error);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: profileKeys.detail });
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

/**
 * The two phone flows are separate backend routes: `bind` refuses an account that already has a
 * verified number (409 `PHONE_ALREADY_BOUND`), while `change` is the one that replaces it. The
 * caller picks the flow; this module never guesses from the account's current state.
 */
export function useSendPhoneCode() {
  return useMutation({
    mutationFn: async ({ phone, flow }: { phone: string; flow: 'bind' | 'change' }) => {
      const { data, error, response } = await apiClient.POST(
        flow === 'bind' ? '/me/phone/send-code' : '/me/phone/change/send-code',
        { body: { phone } },
      );
      requireOk(response, error);
      return data;
    },
  });
}

export function useVerifyPhone() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      phone,
      code,
      flow,
    }: {
      phone: string;
      code: string;
      flow: 'bind' | 'change';
    }) => {
      const { data, error, response } = await apiClient.POST(
        flow === 'bind' ? '/me/phone/verify' : '/me/phone/change/verify',
        { body: { phone, code } },
      );
      requireOk(response, error);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: profileKeys.detail });
      void queryClient.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}
