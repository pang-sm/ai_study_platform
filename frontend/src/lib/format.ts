/**
 * Presentation-only formatters. Nothing here interprets a value — they turn a number the server
 * sent into the unit the server meant, and a timestamp into the reader's own locale.
 */

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB'];
  let size = value / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未记录';
  return date.toLocaleString('zh-CN', { dateStyle: 'short', timeStyle: 'short' });
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未记录';
  return date.toLocaleDateString('zh-CN');
}

/** Keeps a count and its noun together, so a bare number never stands on its own. */
export function count(value: number | null | undefined, noun: string): string {
  if (value === null || value === undefined) return '—';
  return `${value} ${noun}`;
}
