import { useEffect, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import AIReportPanel from "./AIReportPanel.jsx";
import { generateAIReport } from "../services/learningReport.js";

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

function pad(v) { return String(v).padStart(2, "0"); }

function formatDate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function formatStudyTime(minutes) {
  if (minutes === null || minutes === undefined) return "--";
  const m = Number(minutes);
  if (!Number.isFinite(m) || m <= 0) return "0 分钟";
  const h = Math.floor(m / 60);
  const min = m % 60;
  if (h > 0 && min > 0) return `${h} 小时 ${min} 分钟`;
  if (h > 0) return `${h} 小时`;
  return `${min} 分钟`;
}

function formatAccuracy(value) {
  if (value === null || value === undefined) return "--";
  const n = Number(value);
  if (!Number.isFinite(n)) return "--";
  return `${n}%`;
}

function formatStudyDays(count) {
  if (count === null || count === undefined) return "--";
  const n = Number(count);
  if (!Number.isFinite(n) || n <= 0) return "0 天";
  return `${n} 天`;
}

const EMPTY_REPORT = {
  range: { start_date: "", end_date: "", label: "" },
  metrics: { study_minutes: 0, completed_knowledge_count: 0, practice_accuracy: null, study_days: 0 },
  ai_report: { summary: "", strengths: [], weaknesses: [], suggestions: [] },
  trend: [],
  errors: [],
};

function normalizeReport(raw) {
  const data = raw && typeof raw === "object" ? raw : {};
  const m = data.metrics && typeof data.metrics === "object" ? data.metrics : {};
  const ai = data.ai_report && typeof data.ai_report === "object" ? data.ai_report : {};
  return {
    range: data.range || { start_date: "", end_date: "", label: "" },
    metrics: {
      study_minutes: Number.isFinite(Number(m.study_minutes)) ? Number(m.study_minutes) : 0,
      completed_knowledge_count: Number.isFinite(Number(m.completed_knowledge_count)) ? Number(m.completed_knowledge_count) : 0,
      practice_accuracy: Number.isFinite(Number(m.practice_accuracy)) ? Number(m.practice_accuracy) : null,
      study_days: Number.isFinite(Number(m.study_days)) ? Number(m.study_days) : 0,
    },
    summary: {
      overall_summary: ai.summary || "",
      strengths: Array.isArray(ai.strengths) ? ai.strengths : [],
      weaknesses: Array.isArray(ai.weaknesses) ? ai.weaknesses : [],
      suggestions: Array.isArray(ai.suggestions) ? ai.suggestions : [],
    },
    trend: Array.isArray(data.trend) ? data.trend : [],
    errors: Array.isArray(data.errors) ? data.errors : [],
  };
}

function MetricCard({ icon, label, value, tone }) {
  return (
    <section className="report-metric-card-v3">
      <div className={`report-metric-icon report-metric-icon--${tone}`}>{icon}</div>
      <div>
        <div className="report-metric-label-v3">{label}</div>
        <div className="report-metric-value-v3">{value}</div>
      </div>
    </section>
  );
}

function TrendChart({ trend }) {
  const chartRef = useRef(null);
  const points = trend.map((item) => ({
    label: item.date || item.day || item.label || "",
    value: Number(item.study_minutes ?? item.value ?? item.count ?? 0),
  }));
  const hasData = points.some((p) => p.value > 0);
  const safePoints = points.length > 0 ? points : [];

  useEffect(() => {
    if (!chartRef.current || !hasData) return undefined;
    const chart = echarts.init(chartRef.current);
    chart.setOption({
      grid: { left: 42, right: 24, top: 28, bottom: 34 },
      tooltip: { trigger: "axis", backgroundColor: "rgba(17,24,74,0.92)", borderWidth: 0, textStyle: { color: "#fff" } },
      xAxis: {
        type: "category", boundaryGap: false,
        data: safePoints.map((p) => String(p.label).slice(5) || p.label),
        axisLine: { lineStyle: { color: "rgba(124,92,255,0.18)" } },
        axisTick: { show: false }, axisLabel: { color: "#7c86a8", fontSize: 12 },
      },
      yAxis: {
        type: "value", splitNumber: 3,
        axisLabel: { color: "#7c86a8", fontSize: 12 },
        splitLine: { lineStyle: { color: "rgba(124,92,255,0.12)" } },
      },
      series: [{
        name: "学习投入", type: "line", smooth: true, symbol: "circle", symbolSize: 10,
        data: safePoints.map((p) => p.value),
        lineStyle: { width: 4, color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [{ offset: 0, color: "#7c5cff" }, { offset: 1, color: "#36c5f0" }]) },
        itemStyle: { color: "#ffffff", borderColor: "#7c5cff", borderWidth: 3 },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: "rgba(124,92,255,0.18)" }, { offset: 1, color: "rgba(124,92,255,0.02)" }]) },
      }],
    });
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => { window.removeEventListener("resize", resize); chart.dispose(); };
  }, [safePoints]);

  return (
    <section className="report-card report-trend-card">
      <div className="report-section-head">
        <div><h3>学习趋势图</h3><p>所选时间范围内的学习投入变化</p></div>
      </div>
      {!hasData ? (
        <div className="report-empty-mini" style={{padding:"40px 20px",textAlign:"center",color:"#6b7280"}}>
          当前时间范围内暂无学习趋势数据
        </div>
      ) : (
        <div ref={chartRef} className="report-trend-chart" role="img" aria-label="学习趋势折线图" />
      )}
    </section>
  );
}

function KnowledgeListCard({ title, type, items, emptyText }) {
  return (
    <section className="report-card report-list-card">
      <div className="report-section-head report-section-head--compact"><h3>{title}</h3></div>
      {items.length === 0 ? (
        <div className="report-empty-mini">{emptyText}</div>
      ) : (
        <div className="report-knowledge-list">
          {items.map((item, index) => (
            <div key={`${item}-${index}`} className="report-knowledge-row">
              <span className={`report-knowledge-rank report-knowledge-rank--${type}`}>{index + 1}</span>
              <div className="report-knowledge-body">
                <strong>{typeof item === "string" ? item : item.knowledge_point || item.title || `知识点 ${index + 1}`}</strong>
                <span>{typeof item === "object" ? (item.meta || "") : ""}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* ── Generate Report Modal ── */
function GenerateReportModal({ onClose, onGenerate, generating }) {
  const [rangeType, setRangeType] = useState("7d");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [error, setError] = useState("");

  const RANGES = [
    { key: "7d", label: "近7天" },
    { key: "15d", label: "近15天" },
    { key: "30d", label: "近30天" },
    { key: "month", label: "本月" },
    { key: "custom", label: "自定义" },
  ];

  const handleGenerate = () => {
    setError("");
    if (rangeType === "custom") {
      if (!customStart || !customEnd) { setError("请选择开始和结束日期"); return; }
      if (customStart > customEnd) { setError("开始日期不能晚于结束日期"); return; }
      if (customEnd > formatDate(new Date())) { setError("结束日期不能超过今天"); return; }
    }
    onGenerate({
      rangeType,
      startDate: rangeType === "custom" ? customStart : null,
      endDate: rangeType === "custom" ? customEnd : null,
    });
  };

  return (
    <div className="rpt-modal-overlay" onClick={generating ? undefined : onClose}>
      <div className="rpt-modal" onClick={(e) => e.stopPropagation()}>
        <div className="rpt-modal-header">
          <h2>✨ 生成 AI 学习报告</h2>
          {!generating && <button type="button" className="rpt-modal-close" onClick={onClose}>✕</button>}
        </div>
        <div className="rpt-modal-body">
          <p className="rpt-modal-desc">请选择分析时间范围，AI 会结合学习时长、知识点完成情况、练习正确率等数据生成报告。</p>

          {error && <div className="rpt-modal-error">{error}</div>}

          <div className="rpt-range-pills">
            {RANGES.map((r) => (
              <button
                key={r.key}
                type="button"
                className={`rpt-range-pill${rangeType === r.key ? " active" : ""}`}
                onClick={() => setRangeType(r.key)}
                disabled={generating}
              >
                {r.label}
              </button>
            ))}
          </div>

          {rangeType === "custom" && (
            <div className="rpt-custom-dates">
              <div className="esp-form-group">
                <label>开始日期</label>
                <input type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} disabled={generating} />
              </div>
              <span className="rpt-date-sep">至</span>
              <div className="esp-form-group">
                <label>结束日期</label>
                <input type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} disabled={generating} />
              </div>
            </div>
          )}

          {generating && (
            <div className="rpt-generating-hint">
              <div className="esp-loading-spinner" />
              <p>AI 正在分析你的学习数据...</p>
            </div>
          )}
        </div>
        <div className="rpt-modal-footer">
          <button type="button" className="esp-modal-cancel" onClick={onClose} disabled={generating}>取消</button>
          <button type="button" className="rpt-modal-generate" onClick={handleGenerate} disabled={generating}>
            {generating ? "AI 正在分析..." : "生成AI报告"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main Component ── */
export default function LearningReportCenter({
  user,
  mode = "exam_11408",        // "exam_11408" | "course_learning"
  courseName = "",             // used in course_learning mode
}) {
  const isCourseMode = mode === "course_learning";
  const contextName = isCourseMode ? (courseName || "课程学习") : "11408";
  const [report, setReport] = useState(() => normalizeReport(EMPTY_REPORT));
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState("");
  const [hasReport, setHasReport] = useState(false);

  const handleGenerate = async ({ rangeType, startDate, endDate }) => {
    setGenerating(true);
    setError("");
    try {
      const data = await generateAIReport({
        rangeType, startDate, endDate,
        username: user?.username,
        mode: isCourseMode ? "course_learning" : "exam_11408",
        courseName: isCourseMode ? courseName : undefined,
      });
      setReport(normalizeReport(data));
      setHasReport(true);
      setShowModal(false);
    } catch (e) {
      setError(e.message || "AI报告生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const m = report.metrics;
  const metricCards = [
    { icon: "⏱", label: "学习时长", value: formatStudyTime(m.study_minutes), tone: "purple" },
    { icon: "▣", label: "完成知识点", value: String(m.completed_knowledge_count ?? 0), tone: "blue" },
    { icon: "✓", label: "练习正确率", value: formatAccuracy(m.practice_accuracy), tone: "green" },
    { icon: "▤", label: "学习天数", value: formatStudyDays(m.study_days), tone: "orange" },
  ];

  return (
    <main className="report-center-v2 learning-report-dashboard">
      {/* Header bar */}
      <section className="report-filter-bar">
        <div>
          <h1 className="report-hero-title">学习报告</h1>
          <p className="report-hero-subtitle">AI 将根据你的学习记录生成阶段性分析报告</p>
        </div>
        <div className="report-filter-controls">
          <button type="button" className="rpt-ai-btn" onClick={() => { setError(""); setShowModal(true); }}>
            ✨ AI报告
          </button>
        </div>
      </section>

      {/* Range hint */}
      {hasReport && report.range.label && (
        <div className="report-range-hint">
          当前分析范围：{report.range.start_date} 至 {report.range.end_date} · {report.range.label}
        </div>
      )}

      {error && <div className="report-error">{error}</div>}

      {/* Loading overlay during generation */}
      {generating && (
        <div className="rpt-generating-banner">
          <div className="esp-loading-spinner" style={{width:24,height:24,borderWidth:2}} />
          <span>AI 正在分析你的学习数据并生成报告...</span>
        </div>
      )}

      {/* Metric cards */}
      <section className="report-stat-cards">
        {metricCards.map((item) => (
          <MetricCard key={item.label} {...item} />
        ))}
      </section>

      {/* AI Analysis */}
      <AIReportPanel summary={report.summary} loading={generating} />

      {/* Trend */}
      <TrendChart trend={report.trend} />

      {/* Bottom lists */}
      <section className="report-bottom-grid">
        <KnowledgeListCard title="薄弱知识点" type="error" items={report.errors.slice(0, 6)}
          emptyText="当前范围暂无薄弱知识点记录。" />
        <KnowledgeListCard title="AI 建议" type="review"
          items={report.summary.suggestions.map((s, i) => ({ title: s, meta: `建议 ${i + 1}` }))}
          emptyText="生成AI报告后将显示个性化建议。" />
      </section>

      {/* Modal */}
      {showModal && (
        <GenerateReportModal
          onClose={() => setShowModal(false)}
          onGenerate={handleGenerate}
          generating={generating}
        />
      )}
    </main>
  );
}
