import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ExamProfile = components['schemas']['ExamPrepProfileResponse'];
export type ExamProfileUpsert = components['schemas']['ExamPrepProfileUpsert'];
export const examProfileKey = ['exam', 'profile'] as const;

async function requestProfile(): Promise<ExamProfile> {
  const { data, error, response } = await apiClient.GET('/exam/prep/profile');
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function saveProfile(body: ExamProfileUpsert): Promise<ExamProfile> {
  const { data, error, response } = await apiClient.PUT('/exam/prep/profile', { body });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useExamProfile() {
  return useQuery({ queryKey: examProfileKey, queryFn: requestProfile, retry: false });
}

export function useSaveExamProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveProfile,
    onSuccess: (profile) => queryClient.setQueryData(examProfileKey, profile),
  });
}
