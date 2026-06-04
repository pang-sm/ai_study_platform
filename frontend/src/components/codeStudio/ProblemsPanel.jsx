import { useRef } from "react";

/**
 * Problems panel — displays diagnostics from code analysis.
 * Pure presentational component: all data and callbacks are passed via props.
 */
export default function ProblemsPanel({
  diagnostics,
  diagnosticsLoading,
  errorCount,
  warningCount,
  currentFileName,
  code,
  activeLanguage,
  onRefresh,
  onJumpToDiagnostic,
}) {
  const refreshCalledRef = useRef(false);

  const handleRefresh = () => {
    if (refreshCalledRef.current) return;
    refreshCalledRef.current = true;
    setTimeout(() => { refreshCalledRef.current = false; }, 800);
    onRefresh(code, activeLanguage, { force: true });
  };

  return (
    <div className="code-problems-panel">
      <div className="code-problems-toolbar">
        <div className="code-problems-summary">
          <span className="code-problems-summary-item code-problems-summary-item--error">
            ● {errorCount} Errors
          </span>
          <span className="code-problems-summary-item code-problems-summary-item--warning">
            ▲ {warningCount} Warnings
          </span>
          {diagnosticsLoading && (
            <span className="code-problems-checking">Checking...</span>
          )}
        </div>
        <button
          type="button"
          className="code-action-btn code-action-btn--clear compact"
          onClick={handleRefresh}
          disabled={!code.trim() || diagnosticsLoading}
        >
          Refresh
        </button>
      </div>
      {diagnostics.length > 0 ? (
        <div className="code-problems-list">
          {diagnostics.map((item, index) => (
            <button
              type="button"
              key={`${item.severity}-${item.line}-${item.column}-${index}`}
              className={`code-problem-row code-problem-row--${item.severity}`}
              onClick={() => onJumpToDiagnostic(item)}
            >
              <span className="code-problem-row-icon">
                {item.severity === "warning" ? "▲" : "●"}
              </span>
              <span className="code-problem-row-message">{item.message}</span>
              <span className="code-problem-row-meta">
                {currentFileName}:{item.line || 1}:{item.column || 1}
                {item.source ? ` · ${item.source}` : ""}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className="code-problems-empty">
          {diagnosticsLoading ? "Checking diagnostics..." : "No problems found"}
        </div>
      )}
    </div>
  );
}
