import { useEffect, useState } from "react";

const API_BASE = "/api";

const TYPE_LABELS = {
  today: "今日总结",
  weekly: "本周报告",
  monthly: "本月报告",
  course: "课程报告",
  exam: "考前复盘",
  growth: "成长档案",
};

export default function SharedReportPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [report, setReport] = useState(null);

  useEffect(() => {
    const pathname = window.location.pathname;
    const match = pathname.match(/\/shared\/reports\/([^/?#]+)/);
    const token = match ? match[1] : null;

    if (!token) {
      setError("报告分享链接格式不正确。");
      setLoading(false);
      return;
    }

    fetch(`${API_BASE}/shared/reports/${encodeURIComponent(token)}`)
      .then(async (res) => {
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.detail || "该报告分享链接不存在或已被撤销。");
        }
        setReport(data);
      })
      .catch((e) => {
        setError(e.message || "加载分享报告失败。");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="shared-report-shell">
        <div className="shared-report-card">
          <div className="shared-report-loading">正在加载分享报告...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="shared-report-shell">
        <div className="shared-report-card">
          <div className="shared-report-error">
            <div className="shared-report-error-icon">!</div>
            <h2>报告不可用</h2>
            <p>{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!report) return null;

  return (
    <div className="shared-report-shell">
      <div className="shared-report-card">
        <div className="shared-report-header">
          <h1>AI 学习报告分享</h1>
          <p className="shared-report-subtitle">学习报告 · 只读分享</p>
        </div>

        <div className="shared-report-body">
          <h2 className="shared-report-title">{report.title}</h2>

          <div className="shared-report-meta">
            {report.report_type && (
              <span className={`report-type-tag report-type-${report.report_type}`}>
                {TYPE_LABELS[report.report_type] || report.report_type}
              </span>
            )}
            {report.course_name && <span>{report.course_name}</span>}
            {report.start_date && (
              <span>
                {new Date(report.start_date).toLocaleDateString("zh-CN")}
                {report.end_date
                  ? ` ~ ${new Date(report.end_date).toLocaleDateString("zh-CN")}`
                  : ""}
              </span>
            )}
            {report.created_at && (
              <span>生成于 {new Date(report.created_at).toLocaleString("zh-CN")}</span>
            )}
          </div>

          {report.summary && (
            <p className="shared-report-summary">{report.summary}</p>
          )}

          {report.metrics && Object.keys(report.metrics).length > 0 && (
            <div className="report-metrics-cards">
              {Object.entries(report.metrics).map(([k, v]) => (
                <div key={k} className="report-metric-card small">
                  <div className="report-metric-value">
                    {typeof v === "number" && v < 1 && v > 0
                      ? `${Math.round(v * 100)}%`
                      : v}
                  </div>
                  <div className="report-metric-label">{k}</div>
                </div>
              ))}
            </div>
          )}

          <div className="report-content-box">
            <div className="report-content-text">{report.content}</div>
          </div>

          {(report.suggestions || []).length > 0 && (
            <div className="report-suggestions">
              <h4>建议</h4>
              <ul>
                {report.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="shared-report-footer">
          由 AI Study Platform 生成
        </div>
      </div>
    </div>
  );
}
