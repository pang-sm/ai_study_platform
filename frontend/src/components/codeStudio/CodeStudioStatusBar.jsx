/**
 * Editor status bar — line/col, language, diagnostic status, editor display settings.
 * Pure presentational component.
 */
export default function CodeStudioStatusBar({
  editorCursor,
  codeLineCount,
  activeLanguage,
  diagnosticStatus,
  diagnosticErrors,
  diagnosticWarnings,
  editorFontSize,
  editorTheme,
  onDecreaseFontSize,
  onIncreaseFontSize,
  onChangeTheme,
}) {
  return (
    <div className="code-editor-statusbar">
      <span>行 {editorCursor.line}，列 {editorCursor.column}</span>
      <span>{codeLineCount} 行</span>
      <span>空格: 4</span>
      <span>UTF-8</span>
      <span>LF</span>
      <span>{activeLanguage}</span>
      <span className="code-editor-status-run">
        <span
          className={`code-status-run-dot ${
            activeLanguage === "Java"
              ? "code-status-run-dot--warn"
              : "code-status-run-dot--ok"
          }`}
        />
        环境：
        {activeLanguage === "Java" ? "AI 分析" : `${activeLanguage} 可运行`}
      </span>
      {diagnosticStatus !== "unsupported" && diagnosticStatus !== "idle" && (
        <span className="code-editor-status-diag">
          {diagnosticStatus === "checking" ? (
            <>
              <span className="code-diag-dot code-diag-dot--checking" />
              代码：检查中
            </>
          ) : diagnosticStatus === "ok" ? (
            <>
              <span className="code-diag-dot code-diag-dot--ok" />
              代码：编译通过
            </>
          ) : diagnosticStatus === "warning" ? (
            <>
              <span className="code-diag-dot code-diag-dot--warn" />
              代码：{diagnosticWarnings} 个警告
            </>
          ) : diagnosticStatus === "error" ? (
            <>
              <span className="code-diag-dot code-diag-dot--err" />
              代码：{diagnosticErrors} 个错误
            </>
          ) : null}
        </span>
      )}
      <span className="code-editor-settings">
        <button
          type="button"
          className="code-font-btn"
          onClick={onDecreaseFontSize}
          disabled={editorFontSize <= 12}
          title="缩小字号"
        >
          A-
        </button>
        <span className="code-font-value">{editorFontSize}px</span>
        <button
          type="button"
          className="code-font-btn"
          onClick={onIncreaseFontSize}
          disabled={editorFontSize >= 24}
          title="放大字号"
        >
          A+
        </button>
        <button
          type="button"
          className={`code-theme-btn ${editorTheme === "vs-dark" ? "code-theme-btn--active" : ""}`}
          onClick={() => onChangeTheme("vs-dark")}
          title="深色编辑器背景"
        >
          深色
        </button>
        <button
          type="button"
          className={`code-theme-btn ${editorTheme === "light" ? "code-theme-btn--active" : ""}`}
          onClick={() => onChangeTheme("light")}
          title="浅色编辑器背景"
        >
          浅色
        </button>
      </span>
    </div>
  );
}
