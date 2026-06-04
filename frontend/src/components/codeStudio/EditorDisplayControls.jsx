/**
 * Editor display controls — font size + theme settings.
 * Polished toolbar capsule placed in the top bar, left of panel toggle buttons.
 * Pure presentational component.
 */
export default function EditorDisplayControls({
  editorFontSize,
  onDecreaseFontSize,
  onIncreaseFontSize,
  editorTheme,
  onChangeTheme,
}) {
  const isDark = editorTheme === "vs-dark";

  return (
    <div className="editor-display-toolbar" aria-label="编辑器显示设置">
      <div className="editor-display-section">
        <span className="editor-display-icon">Aa</span>
        <span className="editor-display-label">字号</span>
        <button
          type="button"
          className="editor-display-mini-btn"
          onClick={onDecreaseFontSize}
          disabled={editorFontSize <= 12}
          title="减小编辑器字号"
        >
          A−
        </button>
        <span className="editor-display-value" title="当前字号">
          {editorFontSize}px
        </span>
        <button
          type="button"
          className="editor-display-mini-btn"
          onClick={onIncreaseFontSize}
          disabled={editorFontSize >= 24}
          title="增大编辑器字号"
        >
          A+
        </button>
      </div>

      <span className="editor-display-separator" />

      <div className="editor-display-section">
        <span className="editor-display-label">主题</span>
        <button
          type="button"
          className={`editor-display-theme-btn ${isDark ? "is-active" : ""}`}
          onClick={() => onChangeTheme("vs-dark")}
          title="深色编辑器背景"
        >
          深色
        </button>
        <button
          type="button"
          className={`editor-display-theme-btn ${!isDark ? "is-active" : ""}`}
          onClick={() => onChangeTheme("light")}
          title="浅色编辑器背景"
        >
          浅色
        </button>
      </div>
    </div>
  );
}
