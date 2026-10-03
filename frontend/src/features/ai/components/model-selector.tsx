import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useModelOptions } from '../api/ai-chat';

/**
 * A compact concrete-model picker. The router still validates every explicit choice.
 */
export function ModelSelector({
  capability,
  value,
  onChange,
  disabled,
  menuPlacement = 'up',
  align = 'left',
}: {
  capability: string;
  value: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  /** Which way the menu opens. The chat composer sits at the bottom, so it opens up by default. */
  menuPlacement?: 'up' | 'down';
  /** Which edge of the trigger the menu lines up with. */
  align?: 'left' | 'right';
}) {
  const models = useModelOptions(capability);
  // Accept the prior array shape during query-cache hydration; fresh API data has the preview
  // envelope below. This keeps an in-flight navigation from losing the control.
  const legacyOptions = Array.isArray(models.data) ? models.data : null;
  const options = legacyOptions ?? models.data?.options ?? [];
  const recommended = legacyOptions ? null : models.data?.recommended ?? null;

  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', close); return () => document.removeEventListener('mousedown', close);
  }, []);
  if (options.length === 0) return null;
  const autoLabel = recommended ? `自动（推荐：${recommended.label}）` : '自动';
  const label = value === 'auto' ? autoLabel : options.find((option) => option.id === value)?.label ?? autoLabel;

  return (
    <div ref={root} className="relative min-w-0">
      <button type="button" disabled={disabled} onClick={() => setOpen((state) => !state)} aria-label="选择回答使用的模型" aria-haspopup="menu" aria-expanded={open} className="inline-flex h-8 min-w-0 max-w-full items-center gap-1 rounded-lg px-2 text-sm text-text-secondary hover:bg-primary-soft disabled:opacity-50">
        <span className="truncate">{label}</span><ChevronDown className="size-3.5 shrink-0" />
      </button>
      {open ? <div role="menu" className={cn('absolute z-20 min-w-56 rounded-xl border border-border-default bg-surface p-1 shadow-lg', menuPlacement === 'up' ? 'bottom-10' : 'top-10', align === 'right' ? 'right-0' : 'left-0')}>
        <Choice active={value === 'auto'} onClick={() => { onChange('auto'); setOpen(false); }}>{autoLabel}</Choice>
        {options.map((option) => <Choice key={option.id} active={value === option.id} onClick={() => { onChange(option.id); setOpen(false); }}>{option.label}</Choice>)}
      </div> : null}
    </div>
  );
}

function Choice({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button type="button" role="menuitem" onClick={onClick} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm text-text-primary hover:bg-primary-soft"><Check className={cn('size-3.5 text-primary', active ? 'opacity-100' : 'opacity-0')} />{children}</button>;
}
