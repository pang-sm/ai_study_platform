/**
 * The stand-in for the workbench's real code editor, used in every test.
 *
 * CodeMirror measures text with `Range.getClientRects()`, which jsdom does not implement — the
 * editor throws on every layout pass there. Rendering a plain textarea with the SAME label instead
 * keeps the two things the tests are actually about: that the editor is present and named, and
 * that the page around it prints only what the backend sent. It carries `value`/`onChange` on the
 * same contract, so a test that needs code in the buffer can type it.
 */
export function CodeEditor({
  value,
  onChange,
  ariaLabel,
}: {
  value: string;
  onChange: (next: string) => void;
  editable?: boolean;
  ariaLabel: string;
}) {
  return (
    <textarea
      aria-label={ariaLabel}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
