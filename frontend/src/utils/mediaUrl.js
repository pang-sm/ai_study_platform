const ABSOLUTE_URL = /^https?:\/\//i;

/**
 * Resolve server-owned media paths without letting individual views prepend
 * the API prefix a second time.  The API returns canonical `/api/...` URLs;
 * `/me/...` remains supported for records returned by older deployments.
 */
export function resolveMediaUrl(path, apiBase = "/api") {
  const value = String(path || "").trim();
  if (!value || value.startsWith("data:") || ABSOLUTE_URL.test(value)) return value;
  if (value.startsWith("/api/") || value.startsWith("/uploads/")) return value;
  if (value.startsWith("/")) return `${apiBase}${value}`;
  return `${apiBase}/${value}`;
}
