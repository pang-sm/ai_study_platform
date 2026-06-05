/**
 * Shown when a feature is disabled via platform settings.
 */
export default function FeatureUnavailable({ featureName, onGoHome }) {
  return (
    <div
      className="empty-state"
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 64,
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 48, marginBottom: 16 }}>🛠️</div>
      <h2 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#0f172a", margin: "0 0 8px" }}>
        {featureName} 维护中
      </h2>
      <p style={{ fontSize: "0.95rem", color: "#64748b", margin: "0 0 24px", maxWidth: 400 }}>
        该功能暂时维护中，请稍后再试。如需帮助请联系管理员。
      </p>
      <button
        className="primary-button"
        onClick={onGoHome || (() => window.history.back())}
        style={{ padding: "10px 32px" }}
      >
        返回首页
      </button>
    </div>
  );
}
