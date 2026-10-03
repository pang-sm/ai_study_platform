/**
 * The workbench's own device-level view preferences — pure UI, never a learning fact.
 *
 * The题目栏 is the learner's map of the bank, but a learner who has already chosen what to work on
 * wants the width back for the editor. Remembering that choice is a preference about THIS device,
 * not about the learner, so it lives in localStorage and needs no row, no request and no backend
 * change: an address that carries nothing still opens the rail expanded.
 */
const RAIL_COLLAPSED_KEY = 'zhixue:programming:exercise-rail-collapsed';
const COACH_COLLAPSED_KEY = 'programming.coachCollapsed';
const COACH_MODEL_KEY = 'programming.coachModel';

export function readRailCollapsed(): boolean {
  try {
    return window.localStorage.getItem(RAIL_COLLAPSED_KEY) === '1';
  } catch {
    // Storage can be unavailable (private mode, disabled cookies). The rail simply opens expanded.
    return false;
  }
}

export function rememberRailCollapsed(collapsed: boolean): void {
  try {
    window.localStorage.setItem(RAIL_COLLAPSED_KEY, collapsed ? '1' : '0');
  } catch {
    /* nothing to do: the choice still holds for this session */
  }
}

/**
 * The AI 教练 panel's own width choice, remembered on the same device mechanism as the题目栏.
 *
 * Like the rail, this is about THIS screen, not about the learner: collapsing the coach buys the
 * editor back its width, and an address that carries nothing still opens it expanded. It is a
 * separate key from the rail's because the two collapse independently.
 */
export function readCoachCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COACH_COLLAPSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function rememberCoachCollapsed(collapsed: boolean): void {
  try {
    window.localStorage.setItem(COACH_COLLAPSED_KEY, collapsed ? '1' : '0');
  } catch {
    /* nothing to do: the choice still holds for this session */
  }
}

/**
 * The model the learner last chose for the AI 教练, remembered on this device.
 *
 * The AI 问答 page keeps no model preference anywhere — its picker is per-page state — so this is
 * deliberately its OWN key rather than a shared one: choosing a model here must not change which
 * model the AI 问答 page offers the next time it opens. `'auto'` is the sentinel for "let the
 * Router decide", the same value that page uses, and it is what an untouched device reads.
 */
export const COACH_MODEL_AUTO = 'auto';

export function readCoachModel(): string {
  try {
    return window.localStorage.getItem(COACH_MODEL_KEY) || COACH_MODEL_AUTO;
  } catch {
    return COACH_MODEL_AUTO;
  }
}

export function rememberCoachModel(modelId: string): void {
  try {
    window.localStorage.setItem(COACH_MODEL_KEY, modelId);
  } catch {
    /* nothing to do: the choice still holds for this session */
  }
}
