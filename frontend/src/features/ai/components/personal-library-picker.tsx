import { useEffect, useId, useRef, useState, type ChangeEvent } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Search, Upload, X } from 'lucide-react';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { MaterialFileIcon, isMaterialPreviewable, materialIsUsable, materialStatusLabel, materialTypeLabel } from '@/components/materials/material-file';
import { resolveApiResourceUrl } from '@/lib/api/client';
import { serverMessage } from '@/lib/api/server-message';
import { formatBytes } from '@/lib/format';
import { cn } from '@/lib/utils';
import { ApiRequestError } from '@/features/exam/api/content-status';
import {
  LIBRARY_MATERIALS_KEY,
  listLibraryMaterials,
  uploadLibraryMaterial,
  type LibraryMaterial,
} from '@/features/library/api/library';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

/**
 * The learner's material library, opened over the composer to choose from.
 *
 * One library, whichever entry point filled it. A course upload, a file uploaded from inside
 * this dialog and a file uploaded directly to a chat are all the learner's own assets, so all
 * of them are here and all of them can be attached. `scope_type` still records where a file
 * came from — that is what the row's second line names — but it no longer decides whether its
 * owner may see it, which is why this dialog is not a personal-only picker.
 *
 * It is a real modal, not an absolutely-positioned box inside the chat card. Thrown through a
 * portal onto `document.body` and pinned with `fixed`, its overlay covers the viewport whatever
 * the chat card's own `overflow` and stacking happen to be — an `absolute` overlay resolved
 * against the nearest positioned ancestor instead, which is how the top half of a scrolled page
 * ended up grey, the bottom half white, and the footer floating over the transcript.
 *
 * The dialog is one flex column and nothing else scrolls: the header and the footer are fixed
 * size, the list is the only `overflow-y-auto` region, so the dialog can never be cut off by the
 * viewport and the actions can never drift into the middle of the page. The page behind it does
 * not scroll while it is open, and scrolling comes back when it closes.
 *
 * It loads the library ITSELF, on open. Whether a file shows here is the server's answer to
 * `GET /library/materials` at that moment — never a cache, a previous page's fetch, or the set
 * of files this session happened to upload. That is the whole reason the fetch lives in here.
 */
export function PersonalLibraryPicker({
  initialSelected,
  onCancel,
  onAdd,
}: {
  /** Ids already attached in the composer, so reopening the picker reflects the real state. */
  initialSelected: number[];
  onCancel: () => void;
  onAdd: (items: LibraryMaterial[]) => void;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Set<number>>(() => new Set(initialSelected));
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  /**
   * The library as the server holds it RIGHT NOW.
   *
   * `refetchOnMount: 'always'` with a zero stale time is what makes opening the picker its own
   * question to the server: the answer is never a cached list from another surface, nor the set
   * of files this session happened to upload. It re-asks on every open, by construction rather
   * than by remembering to call a loader.
   */
  const library = useQuery({
    queryKey: LIBRARY_MATERIALS_KEY,
    queryFn: () => listLibraryMaterials(),
    retry: false,
    staleTime: 0,
    refetchOnMount: 'always',
  });
  const items = library.data ?? [];

  // The Escape listener is registered once, so it reads the latest callback through a ref: an
  // inline arrow from the parent must not re-register it and re-run the scroll-lock effect.
  const cancelRef = useRef(onCancel);
  useEffect(() => { cancelRef.current = onCancel; }, [onCancel]);

  // Scroll lock, focus, and the keyboard way out. Restoring both on unmount is what makes the
  // page usable again after the dialog closes.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    document.body.style.overflow = 'hidden';
    searchRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        cancelRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!focusable?.length) return;
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKeyDown);
      previouslyFocused?.focus?.();
    };
  }, []);

  const onFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    // Clearing lets the same file be chosen again after a failure.
    event.target.value = '';
    if (!files.length) return;
    setUploading(true);
    setUploadError('');
    try {
      const uploaded = await Promise.all(files.map(uploadLibraryMaterial));
      // The list is refetched, not patched locally: what the learner sees next has to be the
      // server's own answer — including the files it is still parsing — so an upload shows up
      // without closing and reopening the picker. `refetch()` awaits the fresh rows.
      const fresh = await library.refetch();
      // A file the server already parsed is chosen for the learner; one still being processed is
      // listed as 处理中 and cannot be attached until its parse finishes.
      const usable = uploaded.filter((item) => materialIsUsable(item.parseStatus)).map((item) => item.materialId);
      const landed = new Set((fresh.data ?? []).map((item) => item.materialId));
      const chosen = usable.filter((materialId) => landed.has(materialId));
      if (chosen.length) setSelected((current) => new Set([...current, ...chosen]));
    } catch (error) {
      const detail = error instanceof ApiRequestError ? serverMessage(error.detail) : null;
      setUploadError(detail ?? '上传没有成功，请稍后重试。');
    } finally {
      setUploading(false);
    }
  };

  const toggle = (materialId: number) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(materialId)) next.delete(materialId);
    else next.add(materialId);
    return next;
  });

  const needle = query.trim().toLowerCase();
  const visible = needle ? items.filter((item) => item.filename.toLowerCase().includes(needle)) : items;

  return createPortal(
    <div role="presentation" className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[min(720px,calc(100vh-3rem))] w-[min(840px,calc(100vw-2rem))] flex-col overflow-hidden rounded-section border border-border-default bg-surface shadow-visual"
      >
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-border-default px-5 py-4">
          <h2 id={titleId} className="text-heading font-semibold text-text-primary">从资料库添加</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => uploadRef.current?.click()}
              disabled={uploading}
              className="inline-flex h-9 items-center gap-1.5 rounded-control border border-border-default bg-surface px-3 text-body text-text-primary hover:bg-primary-soft disabled:opacity-50"
            >
              <Upload className="size-4" />
              {uploading ? '正在上传…' : '上传资料'}
            </button>
            <button type="button" onClick={onCancel} aria-label="关闭" className="inline-flex size-9 items-center justify-center rounded-control text-text-secondary hover:bg-page-background">
              <X className="size-4" />
            </button>
          </div>
        </header>
        <input ref={uploadRef} type="file" multiple className="hidden" onChange={(event) => void onFiles(event)} />

        <div className="shrink-0 border-b border-border-default px-5 py-3">
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted" />
            <input
              ref={searchRef}
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              aria-label="搜索资料库"
              placeholder="搜索资料库"
              className="h-10 w-full rounded-control border border-border-default bg-surface pl-9 pr-3 text-body text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            />
          </div>
          {uploadError ? <p role="alert" className="mt-2 text-metadata text-danger-ink">{uploadError}</p> : null}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 py-2">
          {library.isPending ? (
            <>
              <p role="status" className="sr-only">正在读取个人资料库…</p>
              <div aria-hidden="true" className="space-y-1">
                {[0, 1, 2, 3].map((row) => (
                  <div key={row} className="flex items-center gap-3 px-3 py-3">
                    <Skeleton className="size-4" />
                    <Skeleton className="size-5" />
                    <div className="min-w-0 flex-1 space-y-2">
                      <Skeleton className="h-3.5 w-1/3" />
                      <Skeleton className="h-3 w-1/4" />
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : library.isError ? (
            <div className="px-3 py-12 text-center">
              <p className="text-body text-text-primary">资料库加载失败</p>
              <button
                type="button"
                onClick={() => void library.refetch()}
                className="mt-3 inline-flex h-9 items-center rounded-control border border-border-default bg-surface px-4 text-body text-text-primary hover:bg-primary-soft"
              >
                重试
              </button>
            </div>
          ) : visible.length ? (
            <ul className="space-y-0.5">
              {visible.map((item) => (
                <LibraryRow key={item.materialId} item={item} selected={selected.has(item.materialId)} onToggle={() => toggle(item.materialId)} />
              ))}
            </ul>
          ) : needle ? (
            <p className="px-3 py-12 text-center text-body text-text-secondary">没有找到相关资料</p>
          ) : (
            <EmptyState
              className="mx-3 my-10"
              title="资料库中还没有资料"
              description="你上传过的资料都会保存在这里，可在之后的学习中再次使用。"
              action={
                <button type="button" onClick={() => uploadRef.current?.click()} disabled={uploading} className="inline-flex h-10 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-50">
                  上传资料
                </button>
              }
            />
          )}
        </div>

        <footer className="flex shrink-0 items-center justify-between gap-3 border-t border-border-default bg-surface px-5 py-3">
          <p role="status" className="text-metadata text-text-secondary">已选择 {selected.size} 项</p>
          <div className="flex items-center gap-2">
            <button type="button" onClick={onCancel} className="inline-flex h-10 items-center rounded-control px-4 text-body text-text-secondary hover:bg-page-background">
              取消
            </button>
            <button
              type="button"
              disabled={!selected.size}
              onClick={() => onAdd(items.filter((item) => selected.has(item.materialId)))}
              className="inline-flex h-10 items-center rounded-control bg-primary px-5 text-body font-medium text-white hover:bg-primary-hover disabled:opacity-40"
            >
              添加
            </button>
          </div>
        </footer>
      </div>
    </div>,
    document.body,
  );
}

/**
 * One file. The whole row chooses it; the icon on the right opens it.
 *
 * Those are two different intentions and they are kept as two different controls rather than
 * nested inside each other, so a learner looking at a file is never one mis-click away from
 * silently changing what will be attached.
 */
function LibraryRow({ item, selected, onToggle }: { item: LibraryMaterial; selected: boolean; onToggle: () => void }) {
  const usable = materialIsUsable(item.parseStatus);
  // Type, size, then where the file came from — a course's own name, 个人资料 or 聊天上传.
  // The three scopes are how the platform decides what is retrieved automatically; only their
  // learner-facing labels belong on a row.
  const meta = [
    materialTypeLabel(item.fileType),
    item.fileSize === undefined ? undefined : formatBytes(item.fileSize),
    item.sourceLabel,
  ].filter(Boolean).join(' · ');

  return (
    <li className="flex items-center gap-1 rounded-control pr-1 hover:bg-page-background">
      <label className={cn('flex min-w-0 flex-1 items-center gap-3 px-3 py-3', usable ? 'cursor-pointer' : 'cursor-not-allowed')}>
        <input
          type="checkbox"
          checked={selected}
          disabled={!usable}
          onChange={onToggle}
          className="size-4 shrink-0 accent-primary disabled:cursor-not-allowed"
        />
        <MaterialFileIcon fileType={item.fileType} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-body text-text-primary">{item.filename}</span>
          <span className="mt-0.5 block text-metadata text-text-secondary">{meta}</span>
        </span>
        {usable ? null : (
          <span className="shrink-0 text-metadata text-text-secondary">{materialStatusLabel(item.parseStatus)}</span>
        )}
      </label>
      {isMaterialPreviewable(item.fileType) && item.canPreview && item.previewUrl ? (
        <a
          href={resolveApiResourceUrl(item.previewUrl)}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`查看 ${item.filename}`}
          className="inline-flex size-9 shrink-0 items-center justify-center rounded-control text-text-secondary hover:bg-primary-soft hover:text-primary"
        >
          <ExternalLink className="size-4" />
        </a>
      ) : null}
    </li>
  );
}
