import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { components } from '@/types/api';
import { apiClient } from '@/lib/api/client';
import {
  LIBRARY_MATERIALS_KEY,
  deleteLibraryMaterial,
  deleteMaterialErrorMessage,
} from '@/features/library/api/library';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from './content-status';

/**
 * ONE 408 subject's material library, as the exam space reads and writes it.
 *
 * This is not a second material system and must not become one. It talks to the module-scoped
 * routes the backend exposes over the SAME `study_materials` table, through the same upload
 * pipeline, the same parse run and the same storage quota the course library uses — the only
 * difference is the scope, which is the subject's, and the server decides what that means.
 *
 * Deleting is the shared library delete for the same reason: the row is the same row, so a
 * subject's page and the library must not have two ways to remove one.
 */

export type ExamMaterialItem = components['schemas']['ExamSubjectMaterialItem'];

export type ExamSubjectMaterials = {
  subjectKey: string;
  courseId: string;
  items: ExamMaterialItem[];
  total: number;
};

/** The subject's own query key, so an upload, a delete and a re-read agree on what is stale. */
export const examMaterialsKey = (subjectKey: string) => ['exam', 'cs408', subjectKey, 'materials'] as const;

async function requestSubjectMaterials(subjectKey: string): Promise<ExamSubjectMaterials> {
  const { data, error, response } = await apiClient.GET(
    '/exam/11408/subjects/{subject_key}/materials',
    { params: { path: { subject_key: subjectKey } } },
  );
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return {
    subjectKey: data.subject_key,
    courseId: data.course_id,
    items: data.items,
    total: data.total,
  };
}

export function useExamSubjectMaterials(subjectKey: string | undefined) {
  return useQuery({
    queryKey: examMaterialsKey(subjectKey ?? ''),
    enabled: Boolean(subjectKey),
    retry: false,
    queryFn: () => requestSubjectMaterials(subjectKey as string),
  });
}

/**
 * Upload one file INTO this subject.
 *
 * The subject is in the path and nowhere else — there is no field a caller could pass that
 * would file the file under a different scope than the page it was uploaded from.
 */
export function useExamMaterialUpload(subjectKey: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const { data, error, response } = await apiClient.POST(
        '/exam/11408/subjects/{subject_key}/materials',
        {
          params: { path: { subject_key: subjectKey } },
          body: { file: file as unknown as string },
          bodySerializer: () => {
            const form = new FormData();
            form.append('file', file);
            return form;
          },
        },
      );
      if (!response.ok) throw new ApiRequestError(response.status, error);
      return data;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: examMaterialsKey(subjectKey) });
      // The library lists the same file — it is the learner's own — so it is stale too.
      void client.invalidateQueries({ queryKey: LIBRARY_MATERIALS_KEY });
    },
  });
}

export function useExamMaterialDelete(subjectKey: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (materialId: number) => deleteLibraryMaterial(materialId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: examMaterialsKey(subjectKey) });
      void client.invalidateQueries({ queryKey: LIBRARY_MATERIALS_KEY });
    },
  });
}

/** Why an upload was refused, in words a learner can act on. */
export function examMaterialUploadError(error: unknown): string {
  if (error instanceof ApiRequestError) {
    const message = serverMessage(error.detail);
    if (message) return message;
    if (error.status === 401 || error.status === 403) return '登录状态已失效，重新登录后就可以继续上传。';
    if (error.status === 413) return '这个文件太大了，换一个小一些的再试。';
  }
  return '上传没有成功，请稍后重试。';
}

export { deleteMaterialErrorMessage };
