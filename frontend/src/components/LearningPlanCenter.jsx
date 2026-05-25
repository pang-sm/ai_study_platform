import { useEffect, useState } from "react";
import { COURSE_OPTIONS, getSubjectLabel } from "../courseOptions.js";

const API_BASE = "/api";

const PLAN_TYPES = [
  { value: "today", label: "今日计划", days: 1, desc: "生成今天的学习任务安排" },
  { value: "three_day", label: "3 天补弱计划", days: 3, desc: "围绕薄弱知识点集中补强" },
  { value: "seven_day", label: "7 天学习计划", days: 7, desc: "一周的完整学习安排" },
  { value: "exam", label: "考前冲刺计划", days: 7, desc: "以复习、练习和总结为主" },
  { value: "coding", label: "编程训练计划", days: 5, desc: "编程练习和代码复盘" },
];

const DAILY_MINUTES_OPTIONS = [30, 60, 90];

const PRIORITY_LABELS = { high: "高", medium: "中", low: "低" };
const PRIORITY_COLORS = {
  high: { bg: "#fef2f2", color: "#dc2626" },
  medium: { bg: "#fffbeb", color: "#d97706" },
  low: { bg: "#f0fdf4", color: "#059669" },
};

const TASK_TYPE_LABELS = {
  review: "复习",
  practice: "练习",
  coding: "编程",
  material: "资料",
  summary: "总结",
  custom: "自定义",
};
const TASK_TYPE_COLORS = {
  review: { bg: "#fef2f2", color: "#dc2626" },
  practice: { bg: "#ede9fe", color: "#6b21a8" },
  coding: { bg: "#dbeafe", color: "#1e40af" },
  material: { bg: "#f0fdf4", color: "#059669" },
  summary: { bg: "#fffbeb", color: "#d97706" },
  custom: { bg: "#e2e8f0", color: "#4b5563" },
};

export default function LearningPlanCenter({ user, getSubjectLabel }) {
  const [planType, setPlanType] = useState("today");
  const [courseId, setCourseId] = useState("");
  const [dailyMinutes, setDailyMinutes] = useState(60);
  const [customMinutes, setCustomMinutes] = useState("");
  const [goal, setGoal] = useState("");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [error, setError] = useState("");

  const selectedPlan = PLAN_TYPES.find((p) => p.value === planType) || PLAN_TYPES[0];

  useEffect(() => {
    // Clear preview when plan type changes
    setPreview(null);
    setImportResult(null);
    setError("");
  }, [planType]);

  const generatePreview = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    setPreview(null);
    setImportResult(null);

    try {
      const minutes = dailyMinutes === 0 ? parseInt(customMinutes, 10) || 60 : dailyMinutes;
      const res = await fetch(`${API_BASE}/learning/plans/generate-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: courseId,
          plan_type: planType,
          days: selectedPlan.days,
          goal: goal.trim(),
          daily_minutes: minutes,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "学习计划生成失败，请稍后重试。");
        return;
      }
      setPreview(data);
    } catch (e) {
      console.error("Failed to generate plan:", e);
      setError("学习计划生成失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  const importTasks = async () => {
    if (!preview?.items?.length || !user?.username) return;
    setImporting(true);
    setError("");
    setImportResult(null);

    try {
      const res = await fetch(`${API_BASE}/learning/plans/import-tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          plan_title: preview.plan_title || "",
          items: preview.items,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "导入失败，请稍后重试。");
        return;
      }
      setImportResult(data);
    } catch (e) {
      console.error("Failed to import tasks:", e);
      setError("导入失败，请稍后重试。");
    } finally {
      setImporting(false);
    }
  };

  const clearPreview = () => {
    setPreview(null);
    setImportResult(null);
    setError("");
  };

  // Group items by day_index
  const groupedItems = preview?.items?.length
    ? preview.items.reduce((acc, item) => {
        const day = item.day_index || 1;
        if (!acc[day]) acc[day] = [];
        acc[day].push(item);
        return acc;
      }, {})
    : {};

  const sortedDays = Object.keys(groupedItems)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="datacenter-shell">
      {/* ── Header ── */}
      <div className="datacenter-header">
        <div>
          <h2 style={{ margin: 0 }}>AI 学习计划</h2>
          <p style={{ margin: "4px 0 0", color: "#6b7280", fontSize: 14 }}>
            根据你的知识点掌握度、错题和学习任务生成个性化计划
          </p>
        </div>
      </div>

      {/* ── Plan Settings ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 16px" }}>计划生成设置</h3>

        {/* Plan type */}
        <div style={{ marginBottom: 16 }}>
          <label className="field-label" style={{ marginBottom: 8, display: "block" }}>
            计划类型
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {PLAN_TYPES.map((pt) => (
              <button
                key={pt.value}
                className={planType === pt.value ? "tiny-button active" : "tiny-button"}
                onClick={() => setPlanType(pt.value)}
                style={{
                  padding: "8px 14px",
                  borderRadius: 8,
                  border: planType === pt.value ? "2px solid #0f766e" : "1px solid #e2e8f0",
                  background: planType === pt.value ? "#f0fdf4" : "#fff",
                  fontWeight: planType === pt.value ? 600 : 400,
                  fontSize: 13,
                  cursor: "pointer",
                  textAlign: "left",
                  lineHeight: 1.4,
                }}
                title={pt.desc}
              >
                <div>{pt.label}</div>
                <div style={{ fontSize: 11, color: "#9ca3af" }}>{pt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Course range */}
        <div style={{ marginBottom: 16 }}>
          <label className="field-label" style={{ marginBottom: 6, display: "block" }}>
            课程范围
          </label>
          <select
            className="field"
            value={courseId}
            onChange={(e) => setCourseId(e.target.value)}
            style={{ maxWidth: 300 }}
          >
            <option value="">全部课程</option>
            {COURSE_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {getSubjectLabel ? getSubjectLabel(c) : c}
              </option>
            ))}
          </select>
        </div>

        {/* Daily minutes */}
        <div style={{ marginBottom: 16 }}>
          <label className="field-label" style={{ marginBottom: 6, display: "block" }}>
            每日学习时间
          </label>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {DAILY_MINUTES_OPTIONS.map((m) => (
              <button
                key={m}
                className="tiny-button"
                onClick={() => { setDailyMinutes(m); setCustomMinutes(""); }}
                style={{
                  padding: "6px 16px",
                  borderRadius: 6,
                  border: dailyMinutes === m && !customMinutes ? "2px solid #0f766e" : "1px solid #e2e8f0",
                  background: dailyMinutes === m && !customMinutes ? "#f0fdf4" : "#fff",
                  fontWeight: dailyMinutes === m && !customMinutes ? 600 : 400,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                {m} 分钟
              </button>
            ))}
            <input
              className="field"
              type="number"
              placeholder="自定义"
              value={customMinutes}
              onChange={(e) => { setCustomMinutes(e.target.value); setDailyMinutes(0); }}
              style={{ width: 80, textAlign: "center" }}
              min={10}
              max={180}
            />
          </div>
        </div>

        {/* Goal */}
        <div style={{ marginBottom: 20 }}>
          <label className="field-label" style={{ marginBottom: 6, display: "block" }}>
            学习目标（可选）
          </label>
          <input
            className="field"
            placeholder="例如：我想复习计算系统基础，准备期末考试"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            style={{ maxWidth: 500 }}
          />
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="onboarding-primary-btn"
            onClick={generatePreview}
            disabled={loading}
          >
            {loading ? "AI 正在生成学习计划..." : "生成计划预览"}
          </button>
        </div>
      </section>

      {/* ── Error ── */}
      {error && (
        <section className="dashboard-card" style={{ borderColor: "#fecaca", background: "#fef2f2" }}>
          <p style={{ color: "#dc2626", margin: 0, fontSize: 14 }}>{error}</p>
        </section>
      )}

      {/* ── Import Result ── */}
      {importResult && (
        <section className="dashboard-card" style={{ borderColor: "#bbf7d0", background: "#f0fdf4" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 20 }}>✓</span>
            <div>
              <p style={{ fontWeight: 600, color: "#059669", margin: 0, fontSize: 15 }}>
                {importResult.message}
              </p>
              <p style={{ color: "#6b7280", margin: "4px 0 0", fontSize: 13 }}>
                可前往
                <a
                  href="#"
                  onClick={(e) => { e.preventDefault(); /* handled by parent */ }}
                  style={{ color: "#0f766e", margin: "0 4px" }}
                >
                  任务中心
                </a>
                查看和管理这些任务。
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Plan Preview ── */}
      {preview && (
        <section className="dashboard-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
            <div>
              <h3 style={{ margin: 0 }}>{preview.plan_title || "学习计划"}</h3>
              {preview.summary && (
                <p style={{ margin: "6px 0 0", color: "#6b7280", fontSize: 13 }}>{preview.summary}</p>
              )}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="ghost-button compact" onClick={clearPreview}>
                清空
              </button>
              <button className="onboarding-primary-btn" onClick={generatePreview} disabled={loading}>
                重新生成
              </button>
              <button
                className="onboarding-primary-btn"
                onClick={importTasks}
                disabled={importing}
                style={{ background: "#059669" }}
              >
                {importing ? "导入中..." : "确认导入任务中心"}
              </button>
            </div>
          </div>

          {sortedDays.map((day) => (
            <div key={day} style={{ marginBottom: 20 }}>
              <h4
                style={{
                  margin: "0 0 10px",
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: "#f1f5f9",
                  fontSize: 14,
                  fontWeight: 600,
                  color: "#374151",
                }}
              >
                第 {day} 天
              </h4>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {groupedItems[day].map((item, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: "10px 14px",
                      borderRadius: 10,
                      background: "#fff",
                      border: "1px solid #e2e8f0",
                      fontSize: 14,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>{item.title}</span>
                      <span style={{ fontSize: 12, color: "#9ca3af" }}>
                        ~{item.estimated_minutes} 分钟
                      </span>
                    </div>
                    {item.description && (
                      <p style={{ margin: "0 0 8px", color: "#4b5563", fontSize: 13, lineHeight: 1.5 }}>
                        {item.description}
                      </p>
                    )}
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                      {item.course_id && (
                        <span style={{ fontSize: 12, color: "#6b7280" }}>
                          {getSubjectLabel ? getSubjectLabel(item.course_id) : item.course_id}
                        </span>
                      )}
                      {item.knowledge_point_title && (
                        <span style={{ fontSize: 12, color: "#6b7280" }}>
                          [{item.knowledge_point_title}]
                        </span>
                      )}
                      {item.priority && (
                        <span
                          style={{
                            padding: "1px 6px",
                            borderRadius: 4,
                            fontSize: 11,
                            background: PRIORITY_COLORS[item.priority]?.bg || "#e2e8f0",
                            color: PRIORITY_COLORS[item.priority]?.color || "#4b5563",
                          }}
                        >
                          {PRIORITY_LABELS[item.priority] || item.priority}
                        </span>
                      )}
                      {item.task_type && (
                        <span
                          style={{
                            padding: "1px 6px",
                            borderRadius: 4,
                            fontSize: 11,
                            background: TASK_TYPE_COLORS[item.task_type]?.bg || "#e2e8f0",
                            color: TASK_TYPE_COLORS[item.task_type]?.color || "#4b5563",
                          }}
                        >
                          {TASK_TYPE_LABELS[item.task_type] || item.task_type}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* ── Empty state ── */}
      {!preview && !loading && !error && !importResult && (
        <div className="empty-state">
          <p>选择计划类型并点击「生成计划预览」，AI 将根据你的学习数据生成个性化计划。</p>
        </div>
      )}
    </div>
  );
}
