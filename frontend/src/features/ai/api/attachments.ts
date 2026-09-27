import { apiClient } from '@/lib/api/client';
import { libraryMaterialFrom, type LibraryMaterial } from '@/features/library/api/library';
import { ApiRequestError } from '@/features/exam/api/content-status';

/**
 * The one upload that belongs to the chat composer: a file sent FOR this conversation.
 *
 * It is not a second library. The server files it under the `chat` scope, which records where it
 * came from; the file still lands in the learner's library and can be chosen again from any
 * course's chat. Reading the library, uploading into it and deleting from it are the library
 * module's business — this module only knows how to attach a file to the question being asked.
 */
export async function uploadChatAttachment(file: File): Promise<LibraryMaterial> {
  const { response, data, error } = await apiClient.POST('/chat/attachments/upload', {
    body: { file: file as unknown as string },
    bodySerializer: () => { const form = new FormData(); form.append('file', file); return form; },
  });
  if (!response.ok || data === undefined) throw new ApiRequestError(response.status, error);
  return libraryMaterialFrom(data as Record<string, unknown>, 'chat');
}
