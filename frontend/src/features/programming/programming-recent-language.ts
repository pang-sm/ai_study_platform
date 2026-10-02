import { normalizeLanguageSlug, type ProgrammingLanguageSlug } from './programming-language';

/**
 * The language the learner last opened a workspace in, remembered on this device.
 *
 * `GET /programming/state` names the learner's DECLARED language, and that is the first thing the
 * front door uses — but declaring one is a separate, deliberate step (设置编程学习, which also
 * picks a level and activates a plan). A learner who walked straight into a language from the
 * picker has declared nothing, and sending them back to the picker on every visit would make the
 * picker the product. This remembers only what they already did, and it is a preference, not a
 * fact: it is never shown as the learner's language anywhere, and a declared language outranks it.
 */
const KEY = 'zhixue:programming:last-language';

export function readRecentLanguage(): ProgrammingLanguageSlug | undefined {
  try {
    return normalizeLanguageSlug(window.localStorage.getItem(KEY));
  } catch {
    // Storage can be unavailable (private mode, disabled cookies). The address still carries the
    // language, so the only cost is being asked once more.
    return undefined;
  }
}

export function rememberLanguage(language: ProgrammingLanguageSlug): void {
  try {
    window.localStorage.setItem(KEY, language);
  } catch {
    /* nothing to do: the choice still travels in the address */
  }
}
