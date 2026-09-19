import { useQueries } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import { ApiRequestError } from './content-status';

export type ExamSubjectDashboardSummary = components['schemas']['ExamSubjectDashboardSummaryResponse'];

export const cs408Modules = [
  { key: 'data_structure', number: '01', name: '数据结构' },
  { key: 'computer_organization', number: '02', name: '计算机组成原理' },
  { key: 'operating_system', number: '03', name: '操作系统' },
  { key: 'computer_network', number: '04', name: '计算机网络' },
] as const;

async function requestDashboardSummary(subjectKey: string): Promise<ExamSubjectDashboardSummary> {
  const { data, error, response } = await apiClient.GET('/exam/11408/subjects/{subject_key}/dashboard-summary', {
    params: { path: { subject_key: subjectKey } },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

export function useCs408DashboardSummaries() {
  return useQueries({
    queries: cs408Modules.map((module) => ({
      queryKey: ['exam', 'cs408', 'dashboard-summary', module.key] as const,
      queryFn: () => requestDashboardSummary(module.key),
      retry: 1,
    })),
  });
}
