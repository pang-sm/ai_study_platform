/**
 * Join class names, dropping falsy values.
 * Minimal by design — no external dependency needed for this stage.
 */
export function cn(...inputs: Array<string | false | null | undefined>): string {
  return inputs.filter(Boolean).join(' ');
}
