import { useMemo } from 'react';
import CodeMirror, { EditorView, type Extension } from '@uiw/react-codemirror';
import { cpp } from '@codemirror/lang-cpp';
import { java } from '@codemirror/lang-java';
import { python } from '@codemirror/lang-python';
import type { ProgrammingLanguageSlug } from '../../programming-language';

/**
 * The code editor: CodeMirror 6, with the language's own grammar.
 *
 * The product had no editor component — the old Workbench used a bare `textarea`, so a题 had no
 * line numbers, no highlighting and no indentation assist. CodeMirror is a real editor with all
 * three, and its default setup carries the rest a code surface is expected to have (undo history,
 * bracket matching, auto-indent, completion).
 *
 * C and C++ share a grammar: `@codemirror/lang-cpp` lexes both, which is how the backend's own
 * `normalize_project_language` treats them when it stores a project's `language`.
 */
const GRAMMAR: Readonly<Record<ProgrammingLanguageSlug, () => Extension>> = {
  python: python,
  c: cpp,
  cpp: cpp,
  java: java,
};

export function CodeEditor({
  language,
  value,
  onChange,
  editable = true,
  ariaLabel,
}: {
  language: ProgrammingLanguageSlug;
  value: string;
  onChange: (next: string) => void;
  editable?: boolean;
  ariaLabel: string;
}) {
  // The label is set on the editable surface itself, which is the element that carries
  // `role=textbox` — a label on the surrounding div would name the wrapper and leave the field
  // the learner actually types into unnamed.
  const extensions = useMemo(
    () => [GRAMMAR[language](), EditorView.contentAttributes.of({ 'aria-label': ariaLabel })],
    [language, ariaLabel],
  );
  return (
    <CodeMirror
      value={value}
      height="100%"
      extensions={extensions}
      editable={editable}
      onChange={(next) => onChange(next)}
      basicSetup={{ tabSize: 4 }}
    />
  );
}
