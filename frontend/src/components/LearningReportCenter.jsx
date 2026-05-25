import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { COURSE_OPTIONS, getSubjectLabel, normalizeSubject } from "../courseOptions.js";

const API_BASE = "/api";

const REPORT_TYPES = [
  { value: "today", label: "今日总结", icon: "📅" },
  { value: "weekly", label: "本周报告", icon: "📊" },
  { value: "monthly", label: "本月报告", icon: "📈" },
  { value: "course", label: "课程报告", icon: "📚" },
  { value: "exam", label: "考前复盘", icon: "📝" },
  { value: "growth", label: "成长档案", icon: "🌱" },
];

const TYPE_LABELS = Object.fromEntries(REPORT_TYPES.map((t) => [t.value, t.label]));

export default function LearningReportCenter({ user }) {
  // Generation settings
  const [reportType, setReportType] = useState("weekly");
  const [courseScope, setCourseScope] = useState("all");
  const [selectedCourse, setSelectedCourse] = useState("");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [goal, setGoal] = useState("");

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");
  const [preview, setPreview] = useState(null);

  // Save state
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  // History
  const [history, setHistory] = useState([]);
  const [histLoading, setHistLoading] = useState(false);
  const [histPage, setHistPage] = useState(1);
  const [histTotal, setHistTotal] = useState(0);
  const [histTypeFilter, setHistTypeFilter] = useState("");

  // Detail modal
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const pageSize = 20;

  // ── History ──

  const fetchHistory = async (page = 1) => {
    setHistLoading(true);
    try {
      const params = new URLSearchParams({
        username: user.username,
        page: String(page),
        page_size: String(pageSize),
      });
      if (histTypeFilter) params.set("report_type", histTypeFilter);
      const res = await fetch(`${API_BASE}/learning/reports?${params}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "加载历史报告失败");
      }
      const data = await res.json();
      setHistory(data.items || []);
      setHistTotal(data.total || 0);
      setHistPage(data.page || 1);
    } catch (e) {
      // silent
    } finally {
      setHistLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory(1);
  }, [histTypeFilter]);

  // ── Generate ──

  const handleGenerate = async () => {
    setGenError("");
    setPreview(null);
    setSaveMsg("");
    setGenerating(true);
    try {
      const body = {
        username: user.username,
        report_type: reportType,
        course_id: courseScope === "specific" ? normalizeSubject(selectedCourse) : "",
        course_name: courseScope === "specific" ? getSubjectLabel(selectedCourse) || selectedCourse : "",
        goal: goal.trim(),
      };
      if (customStart) body.start_date = customStart;
      if (customEnd) body.end_date = customEnd;

      const res = await fetch(`${API_BASE}/learning/reports/generate-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 429) {
          throw new Error(data.detail || "今日学习报告生成次数已达上限，请明天再试或升级会员。");
        }
        throw new Error(data.detail || "学习报告生成失败，请稍后重试。");
      }
      setPreview(data);
    } catch (e) {
      setGenError(e.message || "学习报告生成失败，请稍后重试。");
    } finally {
      setGenerating(false);
    }
  };

  // ── Save ──

  const handleSave = async () => {
    if (!preview) return;
    setSaving(true);
    setSaveMsg("");
    try {
      const body = {
        username: user.username,
        course_id: courseScope === "specific" ? normalizeSubject(selectedCourse) : "",
        course_name: courseScope === "specific" ? getSubjectLabel(selectedCourse) || selectedCourse : "",
        report_type: reportType,
        title: preview.title,
        summary: preview.summary || "",
        content: preview.content,
        metrics: preview.metrics,
        suggestions: preview.suggestions,
        start_date: preview.start_date,
        end_date: preview.end_date,
      };
      const res = await fetch(`${API_BASE}/learning/reports/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "保存失败");
      setSaveMsg("报告已保存到历史记录。");
      fetchHistory(1);
    } catch (e) {
      setSaveMsg(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  // ── Delete ──

  const handleDelete = async (reportId) => {
    if (!window.confirm("确定删除该报告？")) return;
    try {
      const res = await fetch(
        `${API_BASE}/learning/reports/${reportId}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "删除失败");
      fetchHistory(histPage);
    } catch (e) {
      alert(e.message || "删除失败");
    }
  };

  // ── Detail ──

  const handleViewDetail = async (reportId) => {
    setDetailLoading(true);
    setDetail(null);
    try {
      const res = await fetch(
        `${API_BASE}/learning/reports/${reportId}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "加载失败");
      setDetail(data);
    } catch (e) {
      alert(e.message || "加载报告详情失败");
    } finally {
      setDetailLoading(false);
    }
  };

  // ── Helpers ──

  const totalPages = Math.max(1, Math.ceil(histTotal / pageSize));

  const courseOptions = useMemo(
    () => [
      { value: "", label: "选择课程..." },
      ...COURSE_OPTIONS.map((c) => ({ value: c.value, label: c.label })),
    ],
    []
  );

  return (
    <div className="report-center">
      {/* ── Settings ── */}
      <section className="report-section">
        <h3>报告生成设置</h3>

        <div className="report-type-cards">
          {REPORT_TYPES.map((t) => (
            <button
              key={t.value}
              className={`report-type-card ${reportType === t.value ? "active" : ""}`}
              onClick={() => setReportType(t.value)}
            >
              <span className="report-type-icon">{t.icon}</span>
              <span className="report-type-label">{t.label}</span>
            </button>
          ))}
        </div>

        <div className="report-settings-row">
          <div className="report-setting">
            <label className="field-label">课程范围</label>
            <select
              className="field"
              value={courseScope}
              onChange={(e) => setCourseScope(e.target.value)}
            >
              <option value="all">全部课程</option>
              <option value="specific">指定课程</option>
            </select>
          </div>
          {courseScope === "specific" && (
            <div className="report-setting">
              <label className="field-label">选择课程</label>
              <select
                className="field"
                value={selectedCourse}
                onChange={(e) => setSelectedCourse(e.target.value)}
              >
                {courseOptions.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="report-settings-row">
          <div className="report-setting">
            <label className="field-label">开始日期（可选）</label>
            <input
              type="datetime-local"
              className="field"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
            />
          </div>
          <div className="report-setting">
            <label className="field-label">结束日期（可选）</label>
            <input
              type="datetime-local"
              className="field"
              value={customEnd}
              onChange={(e) => setCustomEnd(e.target.value)}
            />
          </div>
        </div>

        <div className="report-setting" style={{ marginBottom: 16 }}>
          <label className="field-label">学习目标（可选）</label>
          <input
            className="field"
            placeholder="例如：准备期末考试、复盘数据结构薄弱点"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
        </div>

        <button
          className="primary-button"
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating ? "AI 正在生成学习报告..." : "生成报告预览"}
        </button>

        {genError && <div className="report-error">{genError}</div>}
      </section>

      {/* ── Preview ── */}
      {preview && (
        <section className="report-section report-preview">
          <h3>报告预览</h3>

          <h2 className="report-preview-title">{preview.title}</h2>
          {preview.summary && (
            <p className="report-preview-summary">{preview.summary}</p>
          )}

          {preview.metrics && (
            <div className="report-metrics-cards">
              {preview.metrics.task_completed_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.task_completed_count}</div>
                  <div className="report-metric-label">完成任务</div>
                </div>
              )}
              {preview.metrics.question_attempt_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.question_attempt_count}</div>
                  <div className="report-metric-label">作答次数</div>
                </div>
              )}
              {preview.metrics.correct_rate !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{Math.round(preview.metrics.correct_rate * 100)}%</div>
                  <div className="report-metric-label">正确率</div>
                </div>
              )}
              {preview.metrics.knowledge_point_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.knowledge_point_count}</div>
                  <div className="report-metric-label">知识点</div>
                </div>
              )}
              {preview.metrics.mastered_point_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.mastered_point_count}</div>
                  <div className="report-metric-label">已掌握</div>
                </div>
              )}
              {preview.metrics.weak_point_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.weak_point_count}</div>
                  <div className="report-metric-label">薄弱点</div>
                </div>
              )}
              {preview.metrics.ai_chat_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.ai_chat_count}</div>
                  <div className="report-metric-label">AI 调用</div>
                </div>
              )}
              {preview.metrics.material_count !== undefined && (
                <div className="report-metric-card">
                  <div className="report-metric-value">{preview.metrics.material_count}</div>
                  <div className="report-metric-label">资料数</div>
                </div>
              )}
            </div>
          )}

          <div className="report-content-box">
            <div className="report-content-text">{preview.content}</div>
          </div>

          {(preview.suggestions || []).length > 0 && (
            <div className="report-suggestions">
              <h4>建议</h4>
              <ul>
                {preview.suggestions.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="report-preview-actions">
            <button className="primary-button" onClick={handleSave} disabled={saving}>
              {saving ? "保存中..." : "保存报告"}
            </button>
            <button className="ghost-button" onClick={handleGenerate} disabled={generating}>
              重新生成
            </button>
            <button className="ghost-button" onClick={() => { setPreview(null); setSaveMsg(""); setGenError(""); }}>
              清空
            </button>
          </div>
          {saveMsg && <p className="report-save-msg" style={{ color: saveMsg.includes("失败") ? "#ef4444" : "#059669" }}>{saveMsg}</p>}
        </section>
      )}

      {/* ── History ── */}
      <section className="report-section">
        <div className="report-history-header">
          <h3>历史报告</h3>
          <div className="report-history-controls">
            <select
              className="field compact"
              value={histTypeFilter}
              onChange={(e) => setHistTypeFilter(e.target.value)}
            >
              <option value="">全部类型</option>
              {REPORT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
            <button className="ghost-button compact" onClick={() => fetchHistory(1)}>
              刷新
            </button>
          </div>
        </div>

        {histLoading ? (
          <div className="empty-state">加载中...</div>
        ) : history.length === 0 ? (
          <div className="empty-state">当前还没有历史报告，可以先生成一份学习报告。</div>
        ) : (
          <>
            <div className="report-table-wrap">
              <table className="report-table">
                <thead>
                  <tr>
                    <th>标题</th>
                    <th>类型</th>
                    <th>课程</th>
                    <th>时间范围</th>
                    <th>创建时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((r) => (
                    <tr key={r.id}>
                      <td title={r.title}>{r.title.length > 30 ? r.title.slice(0, 30) + "..." : r.title}</td>
                      <td><span className={`report-type-tag report-type-${r.report_type}`}>{TYPE_LABELS[r.report_type] || r.report_type}</span></td>
                      <td>{r.course_name || getSubjectLabel(r.course_id) || r.course_id || "全部课程"}</td>
                      <td style={{ fontSize: 12 }}>
                        {r.start_date ? new Date(r.start_date).toLocaleDateString("zh-CN") : "-"} ~{" "}
                        {r.end_date ? new Date(r.end_date).toLocaleDateString("zh-CN") : "-"}
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {r.created_at ? new Date(r.created_at).toLocaleString("zh-CN") : "-"}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="ghost-button compact" onClick={() => handleViewDetail(r.id)}>
                          查看
                        </button>
                        <button className="ghost-button compact" style={{ color: "#ef4444" }} onClick={() => handleDelete(r.id)}>
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="report-pagination">
                <button disabled={histPage <= 1} onClick={() => fetchHistory(histPage - 1)}>上一页</button>
                <span className="report-page-info">{histPage} / {totalPages}（共 {histTotal} 条）</span>
                <button disabled={histPage >= totalPages} onClick={() => fetchHistory(histPage + 1)}>下一页</button>
              </div>
            )}
          </>
        )}
      </section>

      {/* ── Detail Modal (Portal) ── */}
      {detailLoading && (
        createPortal(
          <div className="report-modal-overlay">
            <div className="report-modal"><div className="empty-state">加载报告详情...</div></div>
          </div>,
          document.body
        )
      )}
      {detail && !detailLoading && (
        createPortal(
          <div className="report-modal-overlay" onClick={() => setDetail(null)}>
            <div className="report-modal" onClick={(e) => e.stopPropagation()}>
              <h2 className="report-modal-title">{detail.title}</h2>
              <div className="report-modal-meta">
                <span className={`report-type-tag report-type-${detail.report_type}`}>
                  {TYPE_LABELS[detail.report_type] || detail.report_type}
                </span>
                <span>{detail.course_name || getSubjectLabel(detail.course_id) || detail.course_id || "全部课程"}</span>
                {detail.start_date && (
                  <span>{new Date(detail.start_date).toLocaleDateString("zh-CN")} ~ {detail.end_date ? new Date(detail.end_date).toLocaleDateString("zh-CN") : ""}</span>
                )}
              </div>
              {detail.metrics && (
                <div className="report-metrics-cards" style={{ marginTop: 12 }}>
                  {Object.entries(detail.metrics).map(([k, v]) => (
                    <div key={k} className="report-metric-card small">
                      <div className="report-metric-value">{typeof v === "number" && v < 1 ? `${Math.round(v * 100)}%` : v}</div>
                      <div className="report-metric-label">{k}</div>
                    </div>
                  ))}
                </div>
              )}
              <div className="report-content-box" style={{ marginTop: 16 }}>
                <div className="report-content-text">{detail.content}</div>
              </div>
              {(detail.suggestions || []).length > 0 && (
                <div className="report-suggestions">
                  <h4>建议</h4>
                  <ul>
                    {detail.suggestions.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div style={{ marginTop: 16, textAlign: "right" }}>
                <button className="ghost-button" onClick={() => setDetail(null)}>关闭</button>
              </div>
            </div>
          </div>,
          document.body
        )
      )}
    </div>
  );
}
