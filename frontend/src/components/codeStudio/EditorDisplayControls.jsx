/**
 * Editor display controls — font size + theme settings.
 * Placed in the top layout bar, left of the panel toggle buttons.
 * Pure presentational component.
 */
export default function EditorDisplayControls({
  editorFontSize,
  onDecreaseFontSize,
  onIncreaseFontSize,
  editorTheme,
  onChangeTheme,
}) {
  return (
    <div className="editor-display-controls">
      <span className="editor-display-label">字号</span>
      <button
        type="button"
        onClick={onDecreaseFontSize}
        disabled={editorFontSize <= 12}
        title="缩小编辑器字号"
      >
        A-
      </button>
      <span className="editor-font-size-value">{editorFontSize}px</span>
      <button
        type="button"
        onClick={onIncreaseFontSize}
        disabled={editorFontSize >= 24}
        title="放大编辑器字号"
      >
        A+
      </button>

      <span className="editor-display-divider" />

      <span className="editor-display-label">主题</span>
      <button
        type="button"
        className={editorTheme === "vs-dark" ? "active" : ""}
        onClick={() => onChangeTheme("vs-dark")}
        title="深色编辑器背景"
      >
        深色
      </button>
      <button
        type="button"
        className={editorTheme === "light" ? "active" : ""}
        onClick={() => onChangeTheme("light")}
        title="浅色编辑器背景"
      >
        浅色
      </button>
    </div>
  );
}
