/**
 * An option letter is drawn once.
 *
 * Some papers store the option text the way the printed page writes it inline — `A. O(log n)`,
 * `A. T1 与 T2 的结点数相同` — and every surface that shows an option also draws its key in its
 * own column. Left alone the row reads "A A. O(log n)".
 *
 * Only a leading token that IS this option's own key is dropped, and only from what is drawn:
 * the label the API returned, and every derived payload (the AI explanation sends
 * `question.options` verbatim), stay exactly as the paper wrote them. Nothing here rewrites the
 * question, rewrites an option, or invents one.
 *
 * Validation: 12 of the 235 real CS408 questions store a prefixed label, across 48 option rows.
 */
export function optionLabel(key: string, label: string): string {
  const match = /^\s*([A-Da-d])\s*[.、．)）:：]\s*/.exec(label);
  const letter = match?.[1];
  if (!match || !letter || letter.toUpperCase() !== key.toUpperCase()) return label;
  const rest = label.slice(match[0].length);
  // A label that is nothing BUT its letter would become an empty row; keep it as it came.
  return rest.trim() ? rest : label;
}
