import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function asMarkdown(value, emptyText = "暂无分析内容") {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => `- ${item}`).join("\n") : emptyText;
  }
  return value ? String(value) : emptyText;
}

function InsightBlock({ title, tone, items }) {
  return (
    <section className={`ai-report-insight ai-report-insight--${tone}`}>
      <div className="ai-report-insight-head">
        <span className="ai-report-insight-dot" />
        <h4>{title}</h4>
      </div>
      <div className="ai-report-markdown ai-report-markdown--compact">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {asMarkdown(items)}
        </ReactMarkdown>
      </div>
    </section>
  );
}

export default function AIReportPanel({ summary = {}, loading = false }) {
  return (
    <section className="report-card ai-report-panel">
      <div className="report-section-head">
        <div>
          <h3>AI学习分析</h3>
          <p>基于所选时间范围内的学习数据自动生成</p>
        </div>
        <span className="ai-report-badge">AI深度分析</span>
      </div>

      {loading ? (
        <div className="report-loading-block">AI正在整理学习状态...</div>
      ) : (
        <div className="ai-report-grid">
          <div className="ai-report-summary">
            <h4>整体总结</h4>
            <div className="ai-report-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {asMarkdown(summary.overall_summary, "当前时间范围内暂无足够学习数据，完成更多练习或学习任务后可生成更准确的分析。")}
              </ReactMarkdown>
            </div>
          </div>

          <div className="ai-report-insights">
            <InsightBlock title="优势知识点" tone="success" items={summary.strengths} />
            <InsightBlock title="薄弱环节" tone="warning" items={summary.weaknesses} />
            <InsightBlock title="下一步建议" tone="primary" items={summary.suggestions} />
          </div>
        </div>
      )}
    </section>
  );
}
