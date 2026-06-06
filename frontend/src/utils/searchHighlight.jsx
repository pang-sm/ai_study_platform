/** Safely split text and wrap keyword matches in <mark> elements. */
export function highlightText(text, keyword) {
  if (!text || !keyword) return text || "";
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = String(text).split(new RegExp(`(${escaped})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === keyword.toLowerCase()
      ? <mark key={i} className="search-highlight-mark">{part}</mark>
      : part
  );
}
