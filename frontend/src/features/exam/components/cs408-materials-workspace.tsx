import { useRef, useState } from 'react';
import { Download, ExternalLink, Search, Trash2 } from 'lucide-react';
import { LoadingState } from '@/components/page/loading-state';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { StatusNote } from '@/components/ui/status-note';
import {
  MaterialFileIcon,
  isMaterialPreviewable,
  materialStatusLabel,
  materialTypeLabel,
} from '@/components/materials/material-file';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { formatBytes, formatDateTime } from '@/lib/format';
import { cn } from '@/lib/utils';
// The ONE frontend declaration of the server's allow-list. It lives in the course space's API
// module today, and a second copy here would be exactly the drift this page must not create.
import { MATERIAL_UPLOAD_ACCEPT } from '@/features/course/api/course';
import { cs408Modules } from '../api/dashboard-summary';
import {
  deleteMaterialErrorMessage,
  examMaterialUploadError,
  useExamMaterialDelete,
  useExamMaterialUpload,
  useExamSubjectMaterials,
  type ExamMaterialItem,
} from '../api/materials';
import { ExamPageShell } from './exam-page-shell';
import { Cs408SubjectChooser } from './cs408-subject-chooser';

/**
 * One template for the header row and every data row, so the columns cannot drift apart.
 *
 * The action column is sized to its widest honest content — the three buttons together, since a
 * row with fewer of them keeps its last column in the same place instead of the buttons sliding
 * left — and the type/size and status columns to a type name, a byte count and a state word.
 */
const MATERIAL_GRID =
  'sm:grid sm:grid-cols-[minmax(0,1fr)_10rem_5rem_16.5rem] sm:items-center sm:gap-4';

/**
 * A 408 paper's 资料库, inside the paper's own workspace.
 *
 * It is a first-level page of the paper rather than something bolted onto the outline, because
 * that is what it is in 专业学习: material belongs to the subject it was uploaded for, and the
 * subject's tabs are where a learner looks for it. What the page reads is the module-scoped
 * route, so what it lists is this paper's material and nothing else — switching the module above
 * switches the library with it.
 *
 * The files are real or they are not shown. There is no placeholder row, no count of anything
 * nobody uploaded, and no example file: an empty library is an empty state with an upload button,
 * which is the only honest thing a page with no files can say.
 */
export function Cs408MaterialsWorkspace({ moduleKey }: { moduleKey?: string }) {
  const module = cs408Modules.find((entry) => entry.key === moduleKey);
  if (!module) {
    return (
      <ExamPageShell cs408Tab="materials">
        <Cs408SubjectChooser
          to="/exam/cs408/materials"
          description="资料按四门课分别存放。先选一门，再看它的资料。"
        />
      </ExamPageShell>
    );
  }
  return <Cs408SubjectMaterials module={module} />;
}

function Cs408SubjectMaterials({ module }: { module: (typeof cs408Modules)[number] }) {
  const query = useExamSubjectMaterials(module.key);
  const upload = useExamMaterialUpload(module.key);
  const remove = useExamMaterialDelete(module.key);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState('');
  const [pendingDelete, setPendingDelete] = useState<ExamMaterialItem | null>(null);

  const items = query.data?.items ?? [];
  const needle = search.trim().toLowerCase();
  const visible = needle
    ? items.filter((item) => (item.original_filename ?? '').toLowerCase().includes(needle))
    : items;

  const confirmDelete = () => {
    if (!pendingDelete) return;
    // The dialog closes either way: a failure is stated in the list's own error note, where the
    // learner can see which row it was about, rather than as a modal that will not go away.
    remove.mutate(pendingDelete.id, { onSettled: () => setPendingDelete(null) });
  };

  return (
    <ExamPageShell cs408Tab="materials" moduleKey={module.key}>
      <section aria-labelledby="cs408-materials-title">
        {/* The tabs above say 资料库 and the shell says which paper; naming both again as the
            page's biggest element is the second title bar this workspace removed. The heading
            stays for the document, unseen. */}
        <h1 id="cs408-materials-title" className="sr-only">
          资料库 · {module.name}
        </h1>

        {/* ONE file input for the page, and ONE visible control pointing at it. The toolbar
            carries that control only when there is a library to act on; an empty library is the
            empty state's job, and two 上传资料 controls on one screen is a second call to action
            for the same action — the learner has to read both to find out they are the same.
            The input is named for what it IS (choosing a file) rather than for the action, so a
            screen reader meeting both does not hear the same control twice. */}
        <input
          ref={uploadRef}
          type="file"
          className="sr-only"
          aria-label="选择要上传的文件"
          accept={MATERIAL_UPLOAD_ACCEPT}
          disabled={upload.isPending}
          onChange={(event) => {
            const file = event.target.files?.[0];
            // Clearing the input lets the same file be chosen again after a failure; without
            // it the second selection fires no change event and the retry looks ignored.
            event.target.value = '';
            if (file) upload.mutate(file);
          }}
        />

        {items.length > 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="relative min-w-56 flex-1 sm:max-w-sm">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
              />
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                aria-label="搜索资料"
                placeholder="搜索资料"
                className="h-11 w-full rounded-control border border-border-default bg-surface pl-9 pr-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              />
            </div>
            <button
              type="button"
              disabled={upload.isPending}
              onClick={() => uploadRef.current?.click()}
              className="inline-flex h-11 shrink-0 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            >
              {upload.isPending ? '正在上传…' : '上传资料'}
            </button>
          </div>
        ) : null}

        {upload.isError ? (
          <StatusNote tone="danger" className="mt-4">{examMaterialUploadError(upload.error)}</StatusNote>
        ) : null}
        {upload.isSuccess ? (
          <StatusNote tone="success" className="mt-4">已上传到{module.name}</StatusNote>
        ) : null}
        {remove.isError ? (
          <StatusNote tone="danger" className="mt-4">{deleteMaterialErrorMessage(remove.error)}</StatusNote>
        ) : null}

        {query.isPending ? (
          <LoadingState label="正在读取资料…" className="mt-8" rows={4} />
        ) : query.isError ? (
          <StatusNote tone="danger" className="mt-8">
            资料暂时无法加载。
            <button type="button" className="ml-3 underline" onClick={() => void query.refetch()}>
              重试
            </button>
          </StatusNote>
        ) : items.length === 0 ? (
          <EmptyState
            className="mt-8"
            title="还没有资料"
            description="上传课件、讲义或笔记，它们会成为这门科目自己的资料。"
            action={
              <button
                type="button"
                onClick={() => uploadRef.current?.click()}
                disabled={upload.isPending}
                className="inline-flex h-11 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50"
              >
                上传资料
              </button>
            }
          />
        ) : (
          <>
            <div
              className={cn(
                'mt-8 hidden border-b border-border-default pb-2 text-metadata font-medium text-text-muted',
                MATERIAL_GRID,
              )}
            >
              <span>名称</span>
              <span>类型 · 大小</span>
              <span>状态</span>
              <span className="text-right">操作</span>
            </div>
            {visible.length ? (
              <ul className="border-t border-border-default sm:border-t-0">
                {visible.map((item) => (
                  <MaterialRow key={item.id} item={item} onDelete={setPendingDelete} />
                ))}
              </ul>
            ) : (
              <p className="mt-8 text-body text-text-secondary">没有找到相关资料</p>
            )}
          </>
        )}

        {pendingDelete ? (
          <ConfirmDialog
            title={`删除“${pendingDelete.original_filename ?? '未命名资料'}”？`}
            description="删除后，该资料将无法继续用于新的问答，但历史聊天中的文件记录会保留。"
            pending={remove.isPending}
            onConfirm={confirmDelete}
            onCancel={() => setPendingDelete(null)}
          />
        ) : null}
      </section>
    </ExamPageShell>
  );
}

/**
 * ONE material, in this paper's library.
 *
 * The name is a LABEL, not a control: opening the file is what 查看 is for, and a name that also
 * opens a tab is a second, invisible way to do the same thing. 查看 appears only where a browser
 * can really render the type and the server says this file can still be served — a control that
 * explains its own uselessness is worse than no control.
 */
function MaterialRow({ item, onDelete }: { item: ExamMaterialItem; onDelete: (item: ExamMaterialItem) => void }) {
  const canView = isMaterialPreviewable(item.file_type) && item.can_preview && item.preview_url !== null;
  const canDownload = item.can_download && item.download_url !== null;
  const sizeText = [
    materialTypeLabel(item.file_type),
    item.file_size === undefined ? undefined : formatBytes(item.file_size),
  ].filter(Boolean).join(' · ');

  return (
    <li className="border-b border-border-default">
      <div className={cn('py-4', MATERIAL_GRID)}>
        <div className="flex min-w-0 items-center gap-3">
          <MaterialFileIcon fileType={item.file_type} />
          <span title={item.original_filename ?? undefined} className="truncate text-body font-medium text-text-primary">
            {item.original_filename ?? '未命名资料'}
          </span>
        </div>
        <div className="mt-1 sm:mt-0">
          <p className="text-metadata text-text-secondary">{sizeText}</p>
          {item.created_at ? <p className="mt-0.5 text-metadata text-text-muted">{formatDateTime(item.created_at)}</p> : null}
        </div>
        <p className="mt-1 text-metadata text-text-secondary sm:mt-0">{materialStatusLabel(item.parse_status)}</p>
        <div className="mt-3 flex items-center gap-2 sm:mt-0 sm:justify-end">
          {canView ? (
            <a
              href={resolveApiResourceUrl(item.preview_url as string)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-metadata text-text-primary hover:bg-primary-soft"
            >
              <ExternalLink className="size-3.5" />
              查看
            </a>
          ) : null}
          {canDownload ? (
            <a
              href={resolveApiResourceUrl(item.download_url as string)}
              className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-metadata text-text-primary hover:bg-primary-soft"
            >
              <Download className="size-3.5" />
              下载
            </a>
          ) : null}
          <button
            type="button"
            onClick={() => onDelete(item)}
            className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-metadata text-danger-ink hover:bg-danger-soft"
          >
            <Trash2 className="size-3.5" />
            删除
          </button>
        </div>
      </div>
    </li>
  );
}
