import { useQueries, useQuery } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';
import { cs408Modules } from './dashboard-summary';

export type Cs408Plan = components['schemas']['ExamStudyPlanResponse'];
export type MembershipEntitlements = components['schemas']['MembershipEntitlementsResponse'];

export const examPlanEntitlementKey = ['membership', 'entitlements', 'exam_11408'] as const;
export const cs408PlanKey = (subjectKey: string) => ['exam', 'cs408', 'plan', subjectKey] as const;

async function requestEntitlement(): Promise<MembershipEntitlements> {
  const { data, error, response } = await apiClient.GET('/membership/entitlements', { params: { query: { service_key: 'exam_11408' } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

async function requestPlan(subjectKey: string): Promise<Cs408Plan> {
  const { data, error, response } = await apiClient.GET('/exam/11408/subjects/{subject_key}/study-plan', { params: { path: { subject_key: subjectKey } } });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useExamPlanEntitlement() {
  return useQuery({ queryKey: examPlanEntitlementKey, queryFn: requestEntitlement, retry: false });
}

export function useCs408StudyPlans(enabled: boolean) {
  return useQueries({
    queries: cs408Modules.map((module) => ({
      queryKey: cs408PlanKey(module.key), queryFn: () => requestPlan(module.key), enabled, retry: false, refetchOnWindowFocus: true,
    })),
  });
}
