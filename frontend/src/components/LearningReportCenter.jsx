import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { COURSE_OPTIONS, getSubjectLabel, normalizeSubject } from "../courseOptions.js";
import { guardFeature } from "../featureFlags.js";

const API_BASE = "/api";

const REPORT_TYPES = [
  { value: "today", label: "今日总结", icon: "📅" },
  { value: "weekly", label: "本周报告", icon: "📊" },
  { value: "monthly", label: "本月报告", icon: "📈" },
  { value: "course", label: "课程报告", icon: "📚" },
  { value: "exam", label: "考前复盘", icon: "📝" },
  { value: "growth", label: "成长档案", icon: "🌱" },
];

const REPORT_TYPE_DESCS = {
  today: "总结今天的学习内容和待复习点",
  weekly: "分析本周学习投入和薄弱模块",
  monthly: "查看阶段性成长趋势",
  course: "聚焦单门课程的学习情况",
  exam: "整理重点、错题和冲刺建议",
  growth: "长期记录能力变化和学习成果",
};

const TYPE_LABELS = Object.fromEntries(REPORT_TYPES.map((t) => [t.value, t.label]));

const REPORT_SECTION_ICONS = {
  "学习情况": "📘", "已完成内容": "✅", "基础统计分析": "📊",
  "主要薄弱点": "⚠️", "资料使用": "📚", "AI 使用": "🤖",
  "下一步建议": "🚀", "重点知识点": "🎯", "总结": "📝",
  "学习概览": "📋", "薄弱点分析": "🔍",
};

/** Parse report markdown content into structured sections */
function parseReportMarkdown(content) {
  if (!content) return { title: "", sections: [] };
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const sections = [];
  let title = "";
  let summary = "";
  let currentSection = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("# ") && !title) {
      title = line.slice(2).trim();
      continue;
    }
    if (line.startsWith("> ") && !summary) {
      summary = line.slice(2).trim();
      continue;
    }
    if (line.startsWith("## ")) {
      if (currentSection && currentSection.body.trim()) {
        sections.push(currentSection);
      }
      currentSection = { title: line.slice(3).trim(), body: "" };
      continue;
    }
    if (currentSection) {
      currentSection.body += line + "\n";
    }
  }
  if (currentSection && currentSection.body.trim()) {
    sections.push(currentSection);
  }
  return { title, summary, sections };
}

/** Render a section body (bullet/ordered lists + paragraphs) */
function renderSectionBody(body) {
  const lines = body.trim().split("\n");
  const elements = [];
  let bulletGroup = [];
  let orderedGroup = [];
  let paraGroup = [];
  let inCode = false;
  let codeLines = [];

  const flush = (group, type) => {
    if (group.length === 0) return;
    const text = group.join("\n").trim();
    if (!text) return;
    if (type === "bullet") {
      const items = text.split(/\n(?=[*-]\s)/).filter(Boolean).map((item) =>
        item.replace(/^[*-]\s*/, "").trim()
      );
      elements.push(
        <ul key={elements.length} className="report-section-list">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      );
    } else if (type === "ordered") {
      const items = text.split(/\n(?=\d+\.\s)/).filter(Boolean).map((item) => {
        const m = item.match(/^\d+\.\s\*\*(.+?)\*\*[：:]?\s*(.*)/);
        if (m) return { title: m[1], desc: m[2] };
        return { title: item.replace(/^\d+\.\s*/, "").trim(), desc: "" };
      });
      elements.push(
        <ol key={elements.length} className="report-action-list-v2">
          {items.map((item, i) => (
            <li key={i} className="report-action-item-v2">
              <span className="report-action-num">{i + 1}</span>
              <div className="report-action-body">
                <strong>{item.title}</strong>
                {item.desc && <p>{item.desc}</p>}
              </div>
            </li>
          ))}
        </ol>
      );
    } else {
      elements.push(
        <p key={elements.length} className="report-section-para">
          {text}
        </p>
      );
    }
  };

  for (const line of lines) {
    if (line.startsWith("```")) {
      if (inCode) { flush(codeLines, "para"); codeLines = []; }
      inCode = !inCode;
      continue;
    }
    if (inCode) { codeLines.push(line); continue; }
    const trimmed = line.trim();
    if (!trimmed) {
      flush(bulletGroup, "bullet");
      flush(orderedGroup, "ordered");
      flush(paraGroup, "para");
      bulletGroup = [];
      orderedGroup = [];
      paraGroup = [];
      continue;
    }
    if (/^[*-]\s/.test(trimmed)) {
      flush(orderedGroup, "ordered");
      flush(paraGroup, "para");
      orderedGroup = [];
      paraGroup = [];
      bulletGroup.push(trimmed);
    } else if (/^\d+\.\s/.test(trimmed)) {
      flush(bulletGroup, "bullet");
      flush(paraGroup, "para");
      bulletGroup = [];
      paraGroup = [];
      orderedGroup.push(trimmed);
    } else {
      flush(bulletGroup, "bullet");
      flush(orderedGroup, "ordered");
      bulletGroup = [];
      orderedGroup = [];
      paraGroup.push(trimmed);
    }
  }
  flush(bulletGroup, "bullet");
  flush(orderedGroup, "ordered");
  flush(paraGroup, "para");
  return elements;
}

/** Safely extract statistics from report (preview.statistics or metrics.statistics or metrics) */
function extractStatistics(report) {
  if (!report) return null;
  // Direct statistics field (from preview or detail endpoint)
  if (report.statistics && typeof report.statistics === "object") return report.statistics;
  // Embedded in metrics (for backward compatibility)
  const m = report.metrics;
  if (m && typeof m === "object" && m.statistics && typeof m.statistics === "object") return m.statistics;
  // Fallback: extract from flat metrics (old reports without statistics)
  if (m && typeof m === "object") {
    const hasAny = m.practice_sessions != null || m.practice_questions != null;
    if (hasAny) {
      return {
        practice_sessions: m.practice_sessions ?? 0,
        practice_questions: m.practice_questions ?? 0,
        practice_accuracy: m.practice_accuracy ?? null,
        study_minutes: m.practice_duration_minutes ?? 0,
        completed_tasks: m.task_completed_count ?? 0,
        weak_points: [],
      };
    }
  }
  return null;
}

function safeNum(v, fallback = 0) {
  if (typeof v === "number" && !isNaN(v)) return v;
  return fallback;
}

function formatAccuracy(v) {
  if (v == null || (typeof v === "number" && isNaN(v))) return "--";
  return `${Math.round(v)}%`;
}

function StatisticsBasisCard({ statistics }) {
  if (!statistics) {
    return (
      <div className="report-statistics-basis-card">
        <h4 className="report-statistics-basis-title">报告数据依据</h4>
        <p className="report-statistics-basis-empty">
          暂无足够练习数据。本报告会基于已有任务、资料和学习记录生成，但正确率与练习表现暂无法分析。
        </p>
      </div>
    );
  }

  const hasAnyPractice = safeNum(statistics.practice_sessions) > 0
    || safeNum(statistics.practice_questions) > 0
    || safeNum(statistics.study_minutes) > 0;

  const weakPoints = Array.isArray(statistics.weak_points) ? statistics.weak_points.filter(Boolean) : [];

  return (
    <div className="report-statistics-basis-card">
      <h4 className="report-statistics-basis-title">报告数据依据</h4>
      {!hasAnyPractice && safeNum(statistics.completed_tasks) === 0 ? (
        <p className="report-statistics-basis-empty">
          暂无足够练习数据。本报告会基于已有任务、资料和学习记录生成，但正确率与练习表现暂无法分析。
        </p>
      ) : (
        <div className="report-statistics-basis-grid">
          <div className="report-statistics-basis-item">
            <div className="report-statistics-basis-value">{safeNum(statistics.practice_sessions)} 次</div>
            <div className="report-statistics-basis-label">练习次数</div>
          </div>
          <div className="report-statistics-basis-item">
            <div className="report-statistics-basis-value">{safeNum(statistics.practice_questions)} 题</div>
            <div className="report-statistics-basis-label">练习题数</div>
          </div>
          <div className="report-statistics-basis-item">
            <div className="report-statistics-basis-value">{formatAccuracy(statistics.practice_accuracy)}</div>
            <div className="report-statistics-basis-label">平均正确率</div>
          </div>
          <div className="report-statistics-basis-item">
            <div className="report-statistics-basis-value">{safeNum(statistics.study_minutes)} 分钟</div>
            <div className="report-statistics-basis-label">学习时长</div>
          </div>
          <div className="report-statistics-basis-item">
            <div className="report-statistics-basis-value">{safeNum(statistics.completed_tasks)} 个</div>
            <div className="report-statistics-basis-label">完成任务</div>
          </div>
          <div className="report-statistics-basis-item report-statistics-basis-item--wide">
            <div className="report-statistics-basis-value report-statistics-basis-value--small">
              {weakPoints.length > 0 ? weakPoints.join("、") : "暂无明显薄弱知识点"}
            </div>
            <div className="report-statistics-basis-label">薄弱知识点</div>
          </div>
        </div>
      )}
    </div>
  );
}

function ReportPreview({ report, onSave, onRetry, onClear, saving, saveMsg, showActions }) {
  const parsed = parseReportMarkdown(report.content);
  const metrics = report.metrics || {};
  const metricEntries = [
    { key: "task_completed_count", label: "完成任务" },
    { key: "question_attempt_count", label: "作答次数" },
    { key: "correct_rate", label: "正确率", fmt: (v) => `${Math.round((v ?? 0) * 100)}%` },
    { key: "knowledge_point_count", label: "知识点" },
    { key: "mastered_point_count", label: "已掌握" },
    { key: "weak_point_count", label: "薄弱点" },
    { key: "ai_chat_count", label: "AI 调用" },
    { key: "material_count", label: "资料数" },
  ].filter((e) => metrics[e.key] !== undefined);

  return (
    <div className="report-preview-card-v2">
      <div className="report-preview-header-v2">
        <span className="report-preview-label-v2">报告预览</span>
      </div>
      {parsed.title && <h2 className="report-preview-title-v2">{parsed.title}</h2>}
      {parsed.summary && <p className="report-preview-summary-v2">{parsed.summary}</p>}
      {metricEntries.length > 0 && (
        <div className="report-preview-metrics-v2">
          {metricEntries.map((e) => (
            <div key={e.key} className="report-preview-metric-v2">
              <strong>{e.fmt ? e.fmt(metrics[e.key]) : metrics[e.key]}</strong>
              <span>{e.label}</span>
            </div>
          ))}
        </div>
      )}
      {parsed.sections.length > 0 && (
        <div className="report-body-v2">
          {parsed.sections.map((sec, i) => (
            <div key={i} className="report-section-v2">
              <div className="report-section-title-v2">
                <span className="report-section-icon">
                  {REPORT_SECTION_ICONS[sec.title] || "📝"}
                </span>
                {sec.title}
              </div>
              <div className="report-section-content-v2">
                {renderSectionBody(sec.body)}
              </div>
            </div>
          ))}
        </div>
      )}
      {showActions && (
        <div className="report-preview-actions" style={{ marginTop: 20 }}>
          <p style={{ color: "#059669", fontSize: "0.82rem", margin: 0, display: "flex", alignItems: "center", gap: 6 }}>
            ✓ 报告已自动保存到历史记录
          </p>
          <button className="ghost-button" onClick={onRetry}>重新生成</button>
          <button className="ghost-button" onClick={onClear}>清空</button>
        </div>
      )}
    </div>
  );
}

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

  // Export / share state
  const [shareInfo, setShareInfo] = useState(null);
  const [shareLoading, setShareLoading] = useState(false);
  const [shareMsg, setShareMsg] = useState("");
  const [exportLoading, setExportLoading] = useState("");

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
      // Report is now auto-saved by backend — refresh history immediately
      await fetchHistory(1);
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
      const data = await res.json().catch(() => ({}));
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
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "加载失败");
      setDetail(data);
      fetchShareStatus(reportId);
    } catch (e) {
      alert(e.message || "加载报告详情失败");
    } finally {
      setDetailLoading(false);
    }
  };

  // ── Export ──

  const handleCopyReport = async () => {
    if (!detail) return;
    const lines = [detail.title, "", detail.summary || "", "", detail.content];
    if ((detail.suggestions || []).length > 0) {
      lines.push("", "建议：");
      detail.suggestions.forEach((s, i) => lines.push(`${i + 1}. ${s}`));
    }
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      setSaveMsg("报告已复制到剪贴板。");
    } catch {
      setSaveMsg("复制失败，请手动选择文本。");
    }
  };

  const handleExport = async (format) => {
    if (!detail || !detail.id) return;
    setExportLoading(format);
    try {
      const res = await fetch(
        `${API_BASE}/learning/reports/${detail.id}/export/${format}?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "导出失败");
      const blob = new Blob([data.content], { type: format === "markdown" ? "text/markdown" : "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = data.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message || "导出失败");
    } finally {
      setExportLoading("");
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleCreateShare = async () => {
    if (!detail || !detail.id) return;
    if (!guardFeature("feature_report_share_enabled", "报告分享功能暂时关闭")) return;
    setShareLoading(true);
    setShareMsg("");
    try {
      const res = await fetch(`${API_BASE}/learning/reports/${detail.id}/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, report_id: detail.id }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "创建分享失败");
      setShareInfo(data);
    } catch (e) {
      setShareMsg(e.message || "创建分享失败");
    } finally {
      setShareLoading(false);
    }
  };

  const handleRevokeShare = async () => {
    if (!detail || !detail.id) return;
    if (!window.confirm("确定撤销该报告的分享链接？撤销后分享链接将立即失效。")) return;
    setShareLoading(true);
    setShareMsg("");
    try {
      const res = await fetch(
        `${API_BASE}/learning/reports/${detail.id}/share?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "撤销失败");
      setShareInfo(null);
      setShareMsg("分享已撤销。");
    } catch (e) {
      setShareMsg(e.message || "撤销失败");
    } finally {
      setShareLoading(false);
    }
  };

  const fetchShareStatus = async (reportId) => {
    try {
      const res = await fetch(
        `${API_BASE}/learning/reports/${reportId}/share?username=${encodeURIComponent(user.username)}`
      );
      const data = await res.json();
      if (res.ok && data.is_shared) {
        setShareInfo(data);
      } else {
        setShareInfo(null);
      }
    } catch {
      setShareInfo(null);
    }
  };

  const copyShareUrl = async (token) => {
    const url = `${window.location.origin}/shared/reports/${token}`;
    try {
      await navigator.clipboard.writeText(url);
      setShareMsg("分享链接已复制到剪贴板。");
    } catch {
      setShareMsg("复制失败，请手动复制上方链接。");
    }
  };

  // ── Helpers ──

  const totalPages = Math.max(1, Math.ceil(histTotal / pageSize));

  const courseOptions = useMemo(
    () => [
      { value: "", label: "选择课程..." },
      ...COURSE_OPTIONS.map((c) => ({ value: c, label: c })),
    ],
    []
  );

  const statCards = useMemo(() => {
    const totalReports = histTotal;
    const today = new Date();
    const weekAgo = new Date(today.getTime() - 7 * 86400000);
    const weekReports = history.filter((r) => r.created_at && new Date(r.created_at) >= weekAgo).length;
    const lastReport = history.length > 0 ? history[0] : null;
    return [
      { icon: "📋", label: "已生成报告", value: String(totalReports) },
      { icon: "📆", label: "本周生成", value: String(weekReports) },
      { icon: "⏱️", label: "累计学习记录", value: totalReports > 0 ? "可用" : "暂无" },
      { icon: "🕐", label: "最近生成", value: lastReport?.created_at ? new Date(lastReport.created_at).toLocaleDateString("zh-CN") : "暂无" },
    ];
  }, [histTotal, history]);

  return (
    <div className="report-center-v2">
      {/* ── Hero Header ── */}
      <div className="report-hero">
        <div className="report-hero-text">
          <h1 className="report-hero-title">学习报告</h1>
          <p className="report-hero-subtitle">AI 自动整理你的学习记录，生成阶段总结、薄弱点分析和成长档案。</p>
        </div>
      </div>

      {/* ── Stat Cards ── */}
      <div className="report-stat-cards">
        {statCards.map((sc) => (
          <div key={sc.label} className="report-stat-card">
            <div className="report-stat-icon">{sc.icon}</div>
            <div className="report-stat-body">
              <div className="report-stat-value">{sc.value}</div>
              <div className="report-stat-label">{sc.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Generate Card ── */}
      <div className="report-card report-generate-card">
        <div className="report-card-header">
          <h3>生成新报告</h3>
          <p>选择报告类型、课程和时间范围，AI 会自动整理你的学习表现。</p>
        </div>

        <div className="report-type-grid">
          {REPORT_TYPES.map((t) => (
            <button
              key={t.value}
              className={`report-type-card-v2 ${reportType === t.value ? "active" : ""}`}
              onClick={() => setReportType(t.value)}
            >
              <span className="report-type-card-icon">{t.icon}</span>
              <div className="report-type-card-body">
                <span className="report-type-card-title">{t.label}</span>
                <span className="report-type-card-desc">{REPORT_TYPE_DESCS[t.value]}</span>
              </div>
              {reportType === t.value && <span className="report-type-card-check">✓</span>}
            </button>
          ))}
        </div>

        <div className="report-form-grid">
          <div className="report-form-col report-form-col--full">
            <label className="field-label">课程范围</label>
            <select className="field" value={courseScope} onChange={(e) => setCourseScope(e.target.value)}>
              <option value="all">全部课程</option>
              <option value="specific">指定课程</option>
            </select>
          </div>
          {courseScope === "specific" && (
            <div className="report-form-col">
              <label className="field-label">选择课程</label>
              <select className="field" value={selectedCourse} onChange={(e) => setSelectedCourse(e.target.value)}>
                {courseOptions.map((c) => (<option key={c.value} value={c.value}>{c.label}</option>))}
              </select>
            </div>
          )}
          <div className="report-form-col">
            <label className="field-label">开始日期（可选）</label>
            <input type="datetime-local" className="field" value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
          </div>
          <div className="report-form-col">
            <label className="field-label">结束日期（可选）</label>
            <input type="datetime-local" className="field" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} />
          </div>
          <div className="report-form-col report-form-col--full">
            <label className="field-label">学习目标（可选）</label>
            <input className="field" placeholder="可填写本次报告关注的问题，例如：期末复习、数据库薄弱点、算法错题整理" value={goal} onChange={(e) => setGoal(e.target.value)} />
          </div>
        </div>

        <div className="report-generate-footer">
          <span className="report-generate-hint">AI 将根据学习记录、练习情况和资料库生成报告</span>
          <button className="report-btn-generate" onClick={handleGenerate} disabled={generating}>
            {generating ? "⏳ AI 正在生成..." : "✨ 生成报告预览"}
          </button>
        </div>

        {genError && <div className="report-error">{genError}</div>}
      </div>

      {/* ── Statistics Basis ── */}
      {preview && (
        <StatisticsBasisCard statistics={extractStatistics(preview)} />
      )}

      {/* ── Preview ── */}
      {preview && (
        <ReportPreview
          report={preview}
          onSave={handleSave}
          onRetry={handleGenerate}
          onClear={() => { setPreview(null); setSaveMsg(""); setGenError(""); }}
          saving={saving}
          saveMsg={saveMsg}
          showActions={true}
        />
      )}

      {/* ── History ── */}
      <div className="report-card report-history-card">
        <div className="report-history-header">
          <div>
            <h3>历史报告</h3>
            <p className="report-card-subtitle">查看已经生成过的学习报告</p>
          </div>
          <div className="report-history-controls">
            <select className="field compact" value={histTypeFilter} onChange={(e) => setHistTypeFilter(e.target.value)}>
              <option value="">全部类型</option>
              {REPORT_TYPES.map((t) => (<option key={t.value} value={t.value}>{t.label}</option>))}
            </select>
            <button className="report-btn-refresh" onClick={() => fetchHistory(1)}>↻ 刷新</button>
          </div>
        </div>

        {histLoading ? (
          <div className="empty-state">加载中...</div>
        ) : history.length === 0 ? (
          <div className="empty-state">当前还没有历史报告，可以先生成一份学习报告。</div>
        ) : (
          <>
            <div className="report-table-wrap">
              <table className="report-table-v2">
                <thead><tr><th>标题</th><th>类型</th><th>课程</th><th>时间范围</th><th>创建时间</th><th>操作</th></tr></thead>
                <tbody>
                  {history.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <div className="report-table-title">{r.title.length > 30 ? r.title.slice(0, 30) + "..." : r.title}</div>
                        <div className="report-table-subtitle">包含学习概览、薄弱点分析、复习建议</div>
                      </td>
                      <td><span className={`report-type-tag report-type-${r.report_type}`}>{TYPE_LABELS[r.report_type] || r.report_type}</span></td>
                      <td>{r.course_name || getSubjectLabel(r.course_id) || r.course_id || "全部课程"}</td>
                      <td style={{ fontSize: 12 }}>{r.start_date ? new Date(r.start_date).toLocaleDateString("zh-CN") : "-"} ~ {r.end_date ? new Date(r.end_date).toLocaleDateString("zh-CN") : "-"}</td>
                      <td style={{ fontSize: 12 }}>{r.created_at ? new Date(r.created_at).toLocaleString("zh-CN") : "-"}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="report-btn-view" onClick={() => handleViewDetail(r.id)}>查看</button>
                        <button className="report-btn-delete" onClick={() => handleDelete(r.id)}>删除</button>
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
      </div>

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
          <div className="report-modal-overlay-v2">
            <div className="report-modal-shell-v2">
              <button
                type="button"
                className="report-modal-close-v2"
                onClick={() => { setDetail(null); setShareInfo(null); setShareMsg(""); }}
                aria-label="关闭报告预览"
              >
                ×
              </button>
              <div className="report-modal-scroll-v2">
                <h2 className="report-modal-title">{detail.title}</h2>
                <StatisticsBasisCard statistics={extractStatistics(detail)} />
                <ReportPreview report={detail} showActions={false} />

                {/* ── Share Info ── */}
                {shareInfo && shareInfo.is_shared && (
                  <div className="report-share-info">
                    <div className="report-share-info-title">分享链接（已激活）</div>
                    <div className="report-share-url-row">
                      <input className="field" readOnly value={`${window.location.origin}/shared/reports/${shareInfo.share_token}`} onClick={(e) => e.target.select()} />
                      <button className="ghost-button compact" onClick={() => copyShareUrl(shareInfo.share_token)}>复制</button>
                    </div>
                    <div className="report-share-meta">
                      <span>浏览量：{shareInfo.view_count || 0}</span>
                      {shareInfo.created_at && <span>创建于：{new Date(shareInfo.created_at).toLocaleString("zh-CN")}</span>}
                    </div>
                  </div>
                )}
                {shareMsg && (
                  <p className="report-save-msg" style={{ color: shareMsg.includes("失败") ? "#ef4444" : "#059669", marginTop: 8 }}>{shareMsg}</p>
                )}

                {/* ── Actions ── */}
                <div className="report-detail-actions">
                  <button className="ghost-button compact" onClick={handleCopyReport}>复制报告</button>
                  <button className="ghost-button compact" onClick={() => handleExport("markdown")} disabled={exportLoading === "markdown"}>
                    {exportLoading === "markdown" ? "导出中..." : "导出 Markdown"}
                  </button>
                  <button className="ghost-button compact" onClick={() => handleExport("text")} disabled={exportLoading === "text"}>
                    {exportLoading === "text" ? "导出中..." : "导出 TXT"}
                  </button>
                  <button className="ghost-button compact" onClick={handlePrint}>打印 / 保存 PDF</button>
                  {shareInfo && shareInfo.is_shared ? (
                    <button className="ghost-button compact" style={{ color: "#ef4444" }} onClick={handleRevokeShare} disabled={shareLoading}>
                      {shareLoading ? "撤销中..." : "撤销分享"}
                    </button>
                  ) : (
                    <button className="ghost-button compact" onClick={handleCreateShare} disabled={shareLoading}>
                      {shareLoading ? "创建中..." : "创建分享链接"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>,
          document.body
        )
      )}
    </div>
  );
}
