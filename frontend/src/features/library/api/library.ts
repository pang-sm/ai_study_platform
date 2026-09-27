import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { serverMessage } from '@/lib/api/server-message';
import { ApiRequestError } from '@/features/exam/api/content-status';

/**
 * The learner's material library — ONE list, read and written from one place.
 *
 * The course space's 资料 page and the chat composer's 从资料库添加 both show this same set: a
 * course upload, a personal upload and a file uploaded from inside the picker are all the
 * learner's own assets. Two surfaces reading the same collection must not each define what that
 * collection is, so the query, the type and the delete all live here and every surface imports
 * them. What differs per surface is only what it DOES with a row — the page views, downloads and
 * deletes; the picker chooses.
 */

/** Where a library file came from. It decides automatic retrieval, and it labels the row. */
export type MaterialScopeType = 'course' | 'personal' | 'chat';

export type LibraryMaterial = {
  materialId: number;
  filename: string;
  fileType: string;
  /** Bytes, when the server reported them. */
  fileSize?: number;
  createdAt?: string;
  parseStatus: string;
  scopeType: MaterialScopeType;
  /** The file's origin in the learner's words — a course's name, `个人资料` or `聊天上传`. */
  sourceLabel: string;
  /** Whether the server will serve this file inline. */
  canPreview?: boolean;
  previewUrl?: string;
  canDownload?: boolean;
  downloadUrl?: string;
};

/** The library's one query key, so a write anywhere invalidates exactly this list. */
export const LIBRARY_MATERIALS_KEY = ['library', 'materials'] as const;

/**
 * The wire shape, read defensively.
 *
 * `GET /library/materials` answers the library's own payload, while the two upload endpoints
 * answer smaller ones, so every field is optional here and each call site supplies the scope its
 * own endpoint implies.
 */
type RawMaterial = {
  id?: number;
  material_id?: number;
  filename?: string | null;
  file_type?: string | null;
  file_size?: number | null;
  size?: number | null;
  created_at?: string | null;
  parse_status?: string | null;
  scope_type?: string | null;
  source_label?: string | null;
  can_preview?: boolean | null;
  preview_url?: string | null;
  can_download?: boolean | null;
  download_url?: string | null;
};

/** The words a scope is shown with when the server did not send its own label. */
const SCOPE_LABELS: Record<MaterialScopeType, string> = {
  course: '课程资料',
  personal: '个人资料',
  chat: '聊天上传',
};

export function libraryMaterialFrom(value: RawMaterial, fallbackScope: MaterialScopeType): LibraryMaterial {
  const materialId = value.material_id ?? value.id;
  if (typeof materialId !== 'number' || !value.filename) throw new Error('invalid material response');
  const rawScope = (value.scope_type ?? '').trim().toLowerCase();
  const scopeType = rawScope === 'course' || rawScope === 'personal' || rawScope === 'chat' ? rawScope : fallbackScope;
  const previewUrl = typeof value.preview_url === 'string' && value.preview_url ? value.preview_url : undefined;
  const downloadUrl = typeof value.download_url === 'string' && value.download_url ? value.download_url : undefined;
  return {
    materialId,
    filename: value.filename,
    fileType: value.file_type ?? '',
    fileSize: value.file_size ?? value.size ?? undefined,
    createdAt: value.created_at ?? undefined,
    parseStatus: value.parse_status ?? 'pending',
    scopeType,
    sourceLabel: value.source_label || SCOPE_LABELS[scopeType],
    canPreview: value.can_preview === true && previewUrl !== undefined,
    previewUrl,
    canDownload: value.can_download === true && downloadUrl !== undefined,
    downloadUrl,
  };
}

function requireData<T>(response: Response, data: T | undefined, error: unknown): T {
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return data;
}

/**
 * Every file in the learner's library, as the server currently holds it.
 *
 * Deliberately NOT filtered down to the parsed ones: a surface that silently dropped a file
 * still being parsed made the file look lost, when all that had happened was that its parse had
 * not finished. Which rows can be CHOSEN is decided by the row's own state; which rows EXIST is
 * the server's answer alone.
 *
 * `course` is only the fallback for a row that arrives with no scope at all — the same default
 * the `scope_type` column itself declares.
 */
export async function listLibraryMaterials(q = ''): Promise<LibraryMaterial[]> {
  const { response, data, error } = await apiClient.GET('/library/materials', { params: { query: { q } } });
  const payload = requireData(response, data, error) as { materials?: RawMaterial[] };
  return (payload.materials ?? []).flatMap((item: RawMaterial) => {
    try { return [libraryMaterialFrom(item, 'course')]; } catch { return []; }
  });
}

/** A file uploaded into the library itself, which is the `personal` scope. */
export async function uploadLibraryMaterial(file: File): Promise<LibraryMaterial> {
  const { response, data, error } = await apiClient.POST('/personal-materials/upload', {
    body: { file: file as unknown as string },
    bodySerializer: () => { const form = new FormData(); form.append('file', file); return form; },
  });
  return libraryMaterialFrom(requireData(response, data, error) as RawMaterial, 'personal');
}

/**
 * Remove ONE asset from the learner's own library.
 *
 * Scope-blind by design: the server decides ownership and soft-deletes, so a caller never has to
 * know which door a row came through. History keeps its metadata — only future use ends.
 */
export async function deleteLibraryMaterial(materialId: number): Promise<void> {
  const { response, error } = await apiClient.DELETE('/library/materials/{material_id}', {
    params: { path: { material_id: materialId } },
  });
  if (!response.ok) throw new ApiRequestError(response.status, error);
}

/** Why a delete was refused, in words a learner can act on. */
export function deleteMaterialErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    const message = serverMessage(error.detail);
    if (message) return message;
    if (error.status === 401 || error.status === 403) return '登录状态已失效，重新登录后就可以继续操作。';
  }
  return '删除没有成功，请稍后重试。';
}

export function useLibraryMaterials() {
  return useQuery({ queryKey: LIBRARY_MATERIALS_KEY, queryFn: () => listLibraryMaterials(), retry: false });
}

/**
 * Deleting re-reads the library rather than patching the removed row out locally: the next list
 * has to be the server's own answer, including anything else that moved with it.
 */
export function useLibraryDelete() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (materialId: number) => deleteLibraryMaterial(materialId),
    onSuccess: () => void client.invalidateQueries({ queryKey: LIBRARY_MATERIALS_KEY }),
  });
}
