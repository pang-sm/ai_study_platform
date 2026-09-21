import { factLabel } from '@/lib/fact-labels';
import { enumText } from '@/lib/learner-safe';
import { cn } from '@/lib/utils';

/**
 * The one way a payload becomes readable facts.
 *
 * Values are shown as a definition list — label, then the value the server sent — because that is
 * what these payloads are: named measurements, not prose. Three rules keep it honest:
 *
 *  - a key with a known Chinese label gets a row; a key without one does NOT get an invented
 *    label and is NOT dumped either — it is dropped. An unmapped field is a name the product has
 *    not decided how to say, and printing the server's own key is showing the transport;
 *  - `allow` narrows a payload to the fields a surface has actually chosen to explain, so a rich
 *    backend object (`facts`, `metrics`, `domain_context`) cannot widen the interface on its own;
 *  - a coded *value* is translated through the vocabulary its own field name declares, never by
 *    guessing and never by printing the code; `null` prints as `—`, never as `0`, because the
 *    reports are explicit that a missing metric is not a zero.
 */
type Primitive = string | number | boolean | null | undefined;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isPrimitive(value: unknown): value is Primitive {
  return (
    value === null ||
    value === undefined ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  );
}

/** A primitive as the product reads it: a coded field through its label, anything else as itself. */
function factText(key: string, value: Primitive): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'string') return enumText(key, value);
  return String(value);
}

/** A list of only primitives reads as one line; anything else is rendered as nested facts. */
function primitiveListText(key: string, items: unknown[]): string | undefined {
  if (!items.length) return undefined;
  if (!items.every(isPrimitive)) return undefined;
  return items.map((item) => factText(key, item)).join('、');
}

function FactValue({ fieldKey, value }: { fieldKey: string; value: unknown }) {
  if (isPrimitive(value)) return <span className="tabular-nums">{factText(fieldKey, value)}</span>;
  if (Array.isArray(value)) {
    const joined = primitiveListText(fieldKey, value);
    if (joined !== undefined) return <span className="tabular-nums">{joined}</span>;
    return (
      <ul className="space-y-2">
        {value.map((item, index) => (
          <li key={index} className="border-l-2 border-border-default pl-3">
            <FactValue fieldKey={fieldKey} value={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (isRecord(value)) return <FactList value={value} className="mt-2" />;
  return <span>—</span>;
}

export function FactList({
  value,
  className,
  columns = 2,
  allow,
}: {
  value: unknown;
  className?: string;
  columns?: 1 | 2;
  /** The only field names this surface will explain. Omit to explain every field the product can name. */
  allow?: readonly string[];
}) {
  const entries = isRecord(value)
    ? Object.entries(value).filter(([key, item]) => item !== undefined && factLabel(key) && (!allow || allow.includes(key)))
    : [];

  if (!entries.length) return null;

  return (
    <dl className={cn('grid gap-x-6 gap-y-3', columns === 2 && 'sm:grid-cols-2', className)}>
      {entries.map(([key, item]) => (
        <div key={key} className="border-b border-border-default pb-2">
          <dt className="text-metadata text-text-secondary">{factLabel(key)}</dt>
          <dd className="mt-1 text-body text-text-primary">
            <FactValue fieldKey={key} value={item} />
          </dd>
        </div>
      ))}
    </dl>
  );
}
