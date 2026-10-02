/**
 * The workbench's own device-level view preferences — pure UI, never a learning fact.
 *
 * The题目栏 is the learner's map of the bank, but a learner who has already chosen what to work on
 * wants the width back for the editor. Remembering that choice is a preference about THIS device,
 * not about the learner, so it lives in localStorage and needs no row, no request and no backend
 * change: an address that carries nothing still opens the rail expanded.
 */
const RAIL_COLLAPSED_KEY = 'zhixue:programming:exercise-rail-collapsed';

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
