/**
 * The learner data boundary — one place that decides what a learner may read.
 *
 * Every route this frontend serves belongs to a learner: there is no admin or debug surface to
 * make an exception for. So the rule has no escape hatch, and it is stated once here rather than
 * re-argued on each screen:
 *
 *  - a *coded* value (one of a closed set of codes) is shown through its Chinese label, or as
 *    `其他` / `未设置` when the product has no label for it. The code itself is never printed,
 *    not even folded away — a disclosure is still a learner reading `misconception_v2`;
 *  - a *free-text* value is shown as itself. `analysis` is a sentence the backend wrote;
 *    `status` is a code. Only `FIELD_VOCABULARIES` fields are treated as coded, so prose is
 *    never mangled into `其他`;
 *  - transport identity — request ids, agent run ids, service keys, provider names, raw payloads,
 *    ledger rows — is never rendered at all. Request ids stay in the client: they decide whether a
 *    👍/👎 control appears, they are not metadata for the learner to read;
 *  - a field the product has no label for is dropped, not dumped.
 */
import { FIELD_VOCABULARIES, factLabel } from './fact-labels';

/** An enum value the product deliberately has no words for. */
export const OTHER_LABEL = '其他';
/** An enum field the learner has not set, or the backend has not answered. */
export const UNSET_LABEL = '未设置';
/** Shown in place of an explanation whose underlying rule the backend did not name. */
export const REASON_UNAVAILABLE = '推荐依据暂不可显示';

/**
 * A coded value in the product's own words.
 *
 * `fallback` is the surface's own choice, because the honest word depends on the field: an
 * unanswered preference is `未设置`, an unrecognised code is `其他`. It is never the code.
 */
export function enumText(
  key: string,
  value: unknown,
  fallback: string = OTHER_LABEL,
): string {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  const vocabulary = FIELD_VOCABULARIES[key];
  if (!vocabulary) return value;
  return vocabulary[value] ?? fallback;
}

/** Same rule, for a caller that already knows which vocabulary a value belongs to. */
export function vocabularyText(
  vocabulary: Record<string, string>,
  value: unknown,
  fallback: string = OTHER_LABEL,
): string {
  if (typeof value !== 'string' || !value.trim()) return fallback;
  return vocabulary[value] ?? fallback;
}

/** Whether the product has Chinese words for this field name at all. */
export function factIsSaid(key: string): boolean {
  return factLabel(key) !== undefined;
}

/**
 * The settled cost of one AI call, in the product's words.
 *
 * It reads `actual_credits` — what the ledger actually settled — and nothing else. The estimate is
 * a reservation that may never be spent, tokens are not a unit a learner buys, and the provider's
 * own cost is the platform's business. When there is no settled figure yet the caller shows
 * nothing: a `0` printed before settlement would be a number the product made up.
 */
export function usageCreditsText(usage: unknown): string | undefined {
  if (typeof usage !== 'object' || usage === null) return undefined;
  const settled = (usage as Record<string, unknown>).actual_credits;
  if (typeof settled !== 'number' || !Number.isFinite(settled) || settled < 0) return undefined;
  return `本次使用 ${settled} 点 AI 额度`;
}
