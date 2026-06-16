import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import AIReportPanel from "./AIReportPanel.jsx";
import { fetchLearningReport } from "../services/learningReport.js";

echarts.use([LineChart, GridComponent, TooltipComponent, CanvasRenderer]);

const DAY_MS = 24 * 60 * 60 * 1000;

function pad(value) {
  return String(value).padStart(2, "0");
}

function formatDate(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function getDefaultRange() {
  const end = new Date();
  const start = new Date(end.getTime() - 29 * DAY_MS);
  return { start: formatDate(start), end: formatDate(end) };
}

function getRangeByType(type, customRange) {
  const today = new Date();
  if (type === "7d") {
    return { start: formatDate(new Date(today.getTime() - 6 * DAY_MS)), end: formatDate(today) };
  }
  if (type === "month") {
    return { start: formatDate(new Date(today.getFullYear(), today.getMonth(), 1)), end: formatDate(today) };
  }
  if (type === "custom") {
    return customRange;
  }
  return getDefaultRange();
}

function safeText(value, fallback = "--") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function normalizeReport(raw) {
  const data = raw && typeof raw === "object" ? raw : {};
  const metrics = data.metrics && typeof data.metrics === "object" ? data.metrics : {};
  const summary = data.summary && typeof data.summary === "object" ? data.summary : {};

  return {
    start: data.start || "",
    end: data.end || "",
    summary: {
      overall_summary: summary.overall_summary || "",
      strengths: Array.isArray(summary.strengths) ? summary.strengths : [],
      weaknesses: Array.isArray(summary.weaknesses) ? summary.weaknesses : [],
      suggestions: Array.isArray(summary.suggestions) ? summary.suggestions : [],
    },
    metrics: {
      study_time: safeText(metrics.study_time),
      knowledge_points: safeText(metrics.knowledge_points),
      accuracy: safeText(metrics.accuracy),
      study_days: safeText(metrics.study_days),
    },
    trend: Array.isArray(data.trend) ? data.trend : [],
    errors: Array.isArray(data.errors) ? data.errors : [],
  };
}

function getItemTitle(item, index) {
  if (typeof item === "string") return item;
  return item?.knowledge_point || item?.knowledgePoint || item?.name || item?.title || `知识点 ${index + 1}`;
}

function getItemMeta(item) {
  if (!item || typeof item === "string") return "";
  const parts = [];
  if (item.count !== undefined) parts.push(`${item.count} 次错误`);
  if (item.error_count !== undefined) parts.push(`${item.error_count} 次错误`);
  if (item.accuracy !== undefined) parts.push(`正确率 ${item.accuracy}`);
  if (item.mastery !== undefined) parts.push(`掌握度 ${item.mastery}`);
  return parts.join(" · ");
}

function buildReviewList(report) {
  const fromErrors = report.errors.slice(0, 4).map((item, index) => ({
    title: getItemTitle(item, index),
    meta: getItemMeta(item) || "建议优先复盘错题与对应知识点",
    action: "去复习",
  }));

  const fromWeakness = report.summary.weaknesses.slice(0, 4).map((item, index) => ({
    title: getItemTitle(item, index),
    meta: "薄弱环节，需要专项练习",
    action: index === 0 ? "重点复习" : "去练习",
  }));

  return (fromErrors.length > 0 ? fromErrors : fromWeakness).slice(0, 4);
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
  const points = trend.map((item, index) => {
    const rawValue = Number(item.study_time ?? item.study_minutes ?? item.value ?? item.count ?? 0);
    return {
      label: item.date || item.day || item.label || `D${index + 1}`,
      value: Number.isFinite(rawValue) ? rawValue : 0,
    };
  });
  const safePoints = points.length > 0 ? points : Array.from({ length: 7 }, (_, index) => ({ label: `D${index + 1}`, value: 0 }));

  useEffect(() => {
    if (!chartRef.current) return undefined;
    const chart = echarts.init(chartRef.current);

    chart.setOption({
      grid: { left: 42, right: 24, top: 28, bottom: 34 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(17, 24, 74, 0.92)",
        borderWidth: 0,
        textStyle: { color: "#fff" },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: safePoints.map((item) => String(item.label).slice(5) || item.label),
        axisLine: { lineStyle: { color: "rgba(124, 92, 255, 0.18)" } },
        axisTick: { show: false },
        axisLabel: { color: "#7c86a8", fontSize: 12 },
      },
      yAxis: {
        type: "value",
        splitNumber: 3,
        axisLabel: { color: "#7c86a8", fontSize: 12 },
        splitLine: { lineStyle: { color: "rgba(124, 92, 255, 0.12)" } },
      },
      series: [
        {
          name: "学习投入",
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 10,
          data: safePoints.map((item) => item.value),
          lineStyle: {
            width: 4,
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
              { offset: 0, color: "#7c5cff" },
              { offset: 1, color: "#36c5f0" },
            ]),
          },
          itemStyle: {
            color: "#ffffff",
            borderColor: "#7c5cff",
            borderWidth: 3,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(124, 92, 255, 0.18)" },
              { offset: 1, color: "rgba(124, 92, 255, 0.02)" },
            ]),
          },
        },
      ],
    });

    const resize = () => chart.resize();
    window.addEventListener("resize", resize);

    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [safePoints]);

  return (
    <section className="report-card report-trend-card">
      <div className="report-section-head">
        <div>
          <h3>学习趋势图</h3>
          <p>所选时间范围内的学习投入变化</p>
        </div>
      </div>
      <div ref={chartRef} className="report-trend-chart" role="img" aria-label="学习趋势折线图" />
    </section>
  );
}

function KnowledgeListCard({ title, type, items, emptyText }) {
  return (
    <section className="report-card report-list-card">
      <div className="report-section-head report-section-head--compact">
        <h3>{title}</h3>
      </div>
      {items.length === 0 ? (
        <div className="report-empty-mini">{emptyText}</div>
      ) : (
        <div className="report-knowledge-list">
          {items.map((item, index) => (
            <div key={`${getItemTitle(item, index)}-${index}`} className="report-knowledge-row">
              <span className={`report-knowledge-rank report-knowledge-rank--${type}`}>{index + 1}</span>
              <div className="report-knowledge-body">
                <strong>{getItemTitle(item, index)}</strong>
                <span>{getItemMeta(item) || (type === "error" ? "高频出错，建议回看解析" : item.meta || "建议纳入下一轮复习计划")}</span>
              </div>
              {item.action && <button type="button" className="report-row-action">{item.action}</button>}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function LearningReportCenter({ user }) {
  const defaultRange = useMemo(() => getDefaultRange(), []);
  const [rangeType, setRangeType] = useState("30d");
  const [customRange, setCustomRange] = useState(defaultRange);
  const [report, setReport] = useState(() => normalizeReport({ metrics: {}, summary: {}, trend: [], errors: [] }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const activeRange = useMemo(() => getRangeByType(rangeType, customRange), [rangeType, customRange]);

  useEffect(() => {
    if (!activeRange.start || !activeRange.end) return;

    let ignore = false;
    setLoading(true);
    setError("");

    fetchLearningReport({
      start: activeRange.start,
      end: activeRange.end,
      username: user?.username,
    })
      .then((data) => {
        if (!ignore) setReport(normalizeReport(data));
      })
      .catch((err) => {
        if (!ignore) {
          setError(err.message || "学习报告加载失败，请稍后重试。");
          setReport(normalizeReport({ metrics: {}, summary: {}, trend: [], errors: [] }));
        }
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, [activeRange.start, activeRange.end, user?.username]);

  const metricCards = [
    { icon: "⏱", label: "学习时长", value: report.metrics.study_time, tone: "purple" },
    { icon: "▣", label: "完成知识点", value: report.metrics.knowledge_points, tone: "blue" },
    { icon: "✓", label: "练习正确率", value: report.metrics.accuracy, tone: "green" },
    { icon: "▤", label: "学习天数", value: report.metrics.study_days, tone: "orange" },
  ];

  const reviewItems = buildReviewList(report);

  return (
    <main className="report-center-v2 learning-report-dashboard">
      <section className="report-filter-bar">
        <div>
          <h1 className="report-hero-title">学习报告</h1>
          <p className="report-hero-subtitle">AI自动分析学习状态，按时间维度沉淀结构化洞察。</p>
        </div>

        <div className="report-filter-controls">
          <div className="report-range-tabs" role="tablist" aria-label="学习报告时间范围">
            {[
              { key: "7d", label: "近7天" },
              { key: "30d", label: "近30天" },
              { key: "month", label: "本月" },
              { key: "custom", label: "自定义" },
            ].map((item) => (
              <button
                key={item.key}
                type="button"
                className={rangeType === item.key ? "active" : ""}
                onClick={() => setRangeType(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>

          {rangeType === "custom" && (
            <div className="report-date-range">
              <input
                type="date"
                value={customRange.start}
                onChange={(event) => setCustomRange((prev) => ({ ...prev, start: event.target.value }))}
              />
              <span>至</span>
              <input
                type="date"
                value={customRange.end}
                onChange={(event) => setCustomRange((prev) => ({ ...prev, end: event.target.value }))}
              />
            </div>
          )}
        </div>
      </section>

      <div className="report-range-hint">
        当前分析范围：{activeRange.start} 至 {activeRange.end}
        {loading && <span> · 正在更新...</span>}
      </div>

      {error && <div className="report-error">{error}</div>}

      <section className="report-stat-cards">
        {metricCards.map((item) => (
          <MetricCard key={item.label} {...item} />
        ))}
      </section>

      <AIReportPanel summary={report.summary} loading={loading} />

      <TrendChart trend={report.trend} />

      <section className="report-bottom-grid">
        <KnowledgeListCard
          title="错误知识点列表"
          type="error"
          items={report.errors.slice(0, 6)}
          emptyText="当前范围暂无错误知识点记录。"
        />
        <KnowledgeListCard
          title="重点复习列表"
          type="review"
          items={reviewItems}
          emptyText="当前范围暂无重点复习建议。"
        />
      </section>
    </main>
  );
}
