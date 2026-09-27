import { File, FileCode, FileImage, FileText, Presentation } from 'lucide-react';
import { FILE_TYPE_LABELS } from '@/lib/fact-labels';
import { cn } from '@/lib/utils';

/**
 * How a stored material file is NAMED and MARKED, in one place.
 *
 * The course library and the personal library are different libraries with different
 * lifecycles, and neither may list the other's rows. But a file is a file: the same
 * `file_type` code has to read as the same word in both, or a learner comparing the two
 * sees two vocabularies for one thing. So the vocabulary and the icon live here, and each
 * library supplies its own data, its own rows and its own actions.
 *
 * The codes are the server's — `pdf` / `image` / `docx` / `pptx` / `text` / `code`, exactly
 * what `ALLOWED_UPLOAD_TYPES` and `detect_material_type` produce. An unrecognised or absent
 * code reads as `文件` rather than `其他`: this is an extension, not an enum a learner
 * failed to set.
 */

/** The file's type, in the product's words. */
export function materialTypeLabel(fileType: string | null | undefined): string {
  const code = (fileType ?? '').trim().toLowerCase();
  return FILE_TYPE_LABELS[code] ?? '文件';
}

/**
 * The parse state, as three things a learner can act on.
 *
 * `success` is the only state in which a material can be attached to a question or is
 * fully searchable; the chat and RAG contracts both require it. Everything else — waiting,
 * parsing, a partial index — reads as `处理中`, and `failed` reads as what it is. The
 * distinction between the unfinished states is the server's business and no learner action
 * follows from it.
 */
export function materialStatusLabel(parseStatus: string | null | undefined): string {
  const status = (parseStatus ?? '').trim().toLowerCase();
  if (status === 'success') return '可用';
  if (status === 'failed') return '解析失败';
  return '处理中';
}

/** Whether a material in this parse state can be used at all (attached, cited, searched). */
export function materialIsUsable(parseStatus: string | null | undefined): boolean {
  return (parseStatus ?? 'success').trim().toLowerCase() === 'success';
}

/** The stored `file_type` codes a browser can render inline. */
const PREVIEWABLE_TYPES = new Set(['pdf', 'image', 'text', 'code']);

/**
 * Which file types this product renders in the browser at all.
 *
 * The single client-side statement of the rule the server enforces in `PREVIEWABLE_FILE_TYPES`.
 * It exists so no surface writes its own `if (file_type === 'pdf')` list and drifts from the
 * others: what the library page offers as 查看 and what the picker offers as a preview are the
 * same question, and it has one answer.
 *
 * PDF, images and plain text — including markdown and code, which are text — are rendered. The
 * Office formats (PowerPoint, Word) have no reliable inline renderer in any browser, so they are
 * download-only, and a control that cannot do anything is not offered at all rather than offered
 * and then refused.
 */
export function isMaterialPreviewable(fileType: string | null | undefined): boolean {
  return PREVIEWABLE_TYPES.has((fileType ?? '').trim().toLowerCase());
}

export function MaterialFileIcon({ fileType, className }: { fileType?: string | null; className?: string }) {
  const code = (fileType ?? '').trim().toLowerCase();
  const Icon = ICONS[code] ?? File;
  return <Icon aria-hidden="true" className={cn('size-5 shrink-0 text-text-muted', className)} />;
}

const ICONS: Record<string, typeof File> = {
  pdf: FileText,
  docx: FileText,
  text: FileText,
  pptx: Presentation,
  image: FileImage,
  code: FileCode,
};
