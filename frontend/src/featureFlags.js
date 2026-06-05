/**
 * Shared feature flag utilities.
 * Reads from window.__publicFeatures to avoid prop-drilling.
 */

function normalizeFeatureValue(value) {
  if (value === undefined || value === null) return true;
  if (value === true || value === 1 || value === "1") return true;
  if (value === false || value === 0 || value === "0") return false;
  if (typeof value === "string") {
    const n = value.trim().toLowerCase();
    if (n === "true") return true;
    if (n === "false") return false;
  }
  return true;
}

/** Check if a feature is enabled. Default: true (open). */
export function isFeatureEnabled(key) {
  if (typeof window !== "undefined" && window.__publicFeatures) {
    return normalizeFeatureValue(window.__publicFeatures[key]);
  }
  return true;
}

/** Guard: alert and return false if feature is disabled. */
export function guardFeature(key, message) {
  if (!isFeatureEnabled(key)) {
    alert(message || "该功能暂时维护中，请稍后再试");
    return false;
  }
  return true;
}
