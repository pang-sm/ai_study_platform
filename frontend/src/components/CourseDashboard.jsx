import { useMemo, useEffect, useState } from "react";
import { getRouteSource } from "../data/courseKnowledgePlans.js";
import "./CourseDashboard.css";

const GOAL_STORAGE_PREFIX = "ai_study_goal_config_";

const GOAL_OPTIONS = [
  { value: "overview", label: "大概了解", desc: "快速理解课程框架和核心概念" },
  { value: "systematic", label: "系统学习", desc: "正常跟课、掌握主要知识点" },
  { value: "project", label: "项目实践", desc: "偏应用、偏代码案例" },
  { value: "exam", label: "期中 / 期末速成", desc: "短期备考，重点考点优先" },
];

const DIFFICULTY_OPTIONS = [
  { value: "intro", label: "入门" },
  { value: "standard", label: "标准" },
  { value: "advanced", label: "提高" },
  { value: "challenge", label: "挑战" },
];

const DEPTH_OPTIONS = [
  { value: "brief", label: "粗略" },
  { value: "standard", label: "标准" },
  { value: "detailed", label: "详细" },
];

const DAILY_TIME_OPTIONS = [15, 30, 60, 90];

const EXAM_DAYS_OPTIONS = [
  { value: "3", label: "3 天内" },
  { value: "7", label: "1 周内" },
  { value: "14", label: "2 周内" },
  { value: "30", label: "1 个月内" },
  { value: "custom", label: "自定义日期" },
];

function DonutProgress({ pct, size = 72, strokeWidth = 6 }) {
  const r = (size - strokeWidth) / 2;
  const c = Math.PI * r * 2;
  const offset = c - (Math.min(Math.max(pct, 0), 100) / 100) * c;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="co-donut">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={strokeWidth} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#2563eb"
        strokeWidth={strokeWidth} strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
      <text x={size / 2} y={size / 2} textAnchor="middle" dominantBaseline="central"
        fill="#0f172a" fontSize={size * 0.26} fontWeight="700">
        {pct}%
      </text>
    </svg>
  );
}

function loadGoalConfig(course) {
  try {
    const raw = localStorage.getItem(GOAL_STORAGE_PREFIX + course);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

function saveGoalConfig(course, config) {
  try {
    localStorage.setItem(GOAL_STORAGE_PREFIX + course, JSON.stringify(config));
  } catch { /* ignore */ }
}

function getDefaultGoalConfig() {
  return {
    goal: "systematic",
    difficulty: "standard",
    depth: "standard",
    dailyTime: 30,
    examDays: "7",
    examCustomDate: "",
    examPaperUploaded: false,
  };
}

export default function CourseDashboard({
  user,
  course,
  courseOptions,
  dashboard,
  loading,
  setPage,
  onCourseChange,
  getSubjectLabel,
  materials = [],
  goalConfig = null,
  setGoalConfig = () => {},
}) {
  const stats = dashboard?.stats || {};
  const courseLabel = getSubjectLabel(course);
  const routeSource = useMemo(() => getRouteSource(course, courseLabel), [course, courseLabel]);
  const hasPlannedRoute = routeSource !== "materials";

  // Course-scoped materials
  const courseMaterials = useMemo(() => {
    const list = Array.isArray(materials) ? materials : [];
    if (!courseLabel) return list;
    return list.filter((m) => getSubjectLabel(m.subject) === courseLabel);
  }, [materials, courseLabel, getSubjectLabel]);

  // Goal config — lifted from App.jsx, fallback to defaults
  const effectiveGoalConfig = goalConfig || getDefaultGoalConfig();

  const updateGoalConfig = (patch) => {
    setGoalConfig({ ...effectiveGoalConfig, ...patch });
  };

  const overallPct = stats.progress_percent ?? 0;

  if (loading) {
    return (
      <div className="co-loading">
        <div className="co-loading-spinner" />
        <p>课程概览加载中...</p>
      </div>
    );
  }

  return (
    <div className="co-page">
      {/* ── Page Title ── */}
      <div className="co-page-title-area">
        <div className="co-page-title-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
            <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
          </svg>
        </div>
        <div>
          <h1 className="co-page-title">课程概览</h1>
          <p className="co-page-subtitle">配置学习目标，查看学习概况</p>
        </div>
      </div>

      <div className="co-layout">
        <div className="co-main">
          {/* ── Learning goal config card ── */}
          <div className="co-card co-goal-card">
            <h2 className="co-card-title">学习目标配置</h2>
            <p className="co-card-desc">选择学习目标，AI 将据此调整学习路线和推荐内容</p>

            {/* Goal */}
            <div className="co-field-group">
              <label className="co-field-label">学习目标</label>
              <div className="co-option-grid co-option-grid--2">
                {GOAL_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`co-option-card${effectiveGoalConfig.goal === opt.value ? " co-option-card--active" : ""}`}
                    onClick={() => updateGoalConfig({ goal: opt.value })}
                  >
                    <span className="co-option-card-label">{opt.label}</span>
                    <span className="co-option-card-desc">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Difficulty */}
            <div className="co-field-group">
              <label className="co-field-label">学习难度</label>
              <div className="co-chip-row">
                {DIFFICULTY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`co-chip${effectiveGoalConfig.difficulty === opt.value ? " co-chip--active" : ""}`}
                    onClick={() => updateGoalConfig({ difficulty: opt.value })}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Depth */}
            <div className="co-field-group">
              <label className="co-field-label">知识点细度</label>
              <div className="co-chip-row">
                {DEPTH_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={`co-chip${effectiveGoalConfig.depth === opt.value ? " co-chip--active" : ""}`}
                    onClick={() => updateGoalConfig({ depth: opt.value })}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Daily time */}
            <div className="co-field-group">
              <label className="co-field-label">每日学习时间</label>
              <div className="co-chip-row">
                {DAILY_TIME_OPTIONS.map((min) => (
                  <button
                    key={min}
                    type="button"
                    className={`co-chip${effectiveGoalConfig.dailyTime === min ? " co-chip--active" : ""}`}
                    onClick={() => updateGoalConfig({ dailyTime: min })}
                  >
                    {min} 分钟
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ── Exam config card (conditional) ── */}
          {effectiveGoalConfig.goal === "exam" && (
            <div className="co-card co-exam-card">
              <h2 className="co-card-title">考试速成配置</h2>
              <p className="co-card-desc">配置考试信息，AI 将优先安排高频考点</p>

              <div className="co-field-group">
                <label className="co-field-label">距离考试时间</label>
                <div className="co-chip-row">
                  {EXAM_DAYS_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      className={`co-chip${effectiveGoalConfig.examDays === opt.value ? " co-chip--active" : ""}`}
                      onClick={() => updateGoalConfig({ examDays: opt.value })}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {effectiveGoalConfig.examDays === "custom" && (
                  <input
                    type="date"
                    className="co-date-input"
                    value={effectiveGoalConfig.examCustomDate}
                    onChange={(e) => updateGoalConfig({ examCustomDate: e.target.value })}
                  />
                )}
              </div>

              {/* Exam paper upload section */}
              <div className="co-exam-paper-section">
                <div className="co-exam-paper-icon">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="1.5" strokeLinecap="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                </div>
                <div className="co-exam-paper-info">
                  <p className="co-exam-paper-title">上传往年试卷或模拟卷</p>
                  <p className="co-exam-paper-hint">
                    建议上传往年试卷或模拟卷，AI 将分析题型、难度和高频知识点，并调整学习路线优先级。
                  </p>
                </div>
                <div className="co-exam-paper-actions">
                  <button
                    className="co-btn co-btn--primary"
                    type="button"
                    onClick={() => setPage("workspaceMaterials")}
                  >
                    上传试卷分析难度
                  </button>
                  <button
                    className="co-btn co-btn--ghost"
                    type="button"
                    onClick={() => updateGoalConfig({ examPaperUploaded: false })}
                  >
                    暂不上传，使用平台备考路线
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* ── Current learning summary ── */}
          <div className="co-card co-summary-card">
            <h2 className="co-card-title">学习概况</h2>
            <div className="co-summary-grid">
              <div className="co-summary-item">
                <span className="co-summary-val">{overallPct}%</span>
                <span className="co-summary-lbl">总进度</span>
              </div>
              <div className="co-summary-item">
                <span className="co-summary-val">{stats.materials_count ?? courseMaterials.length}</span>
                <span className="co-summary-lbl">已上传资料</span>
              </div>
              <div className="co-summary-item">
                <span className="co-summary-val">{stats.mastered_points ?? 0}</span>
                <span className="co-summary-lbl">已掌握知识点</span>
              </div>
              <div className="co-summary-item">
                <span className="co-summary-val">{stats.pending_review_count ?? 0}</span>
                <span className="co-summary-lbl">待复习</span>
              </div>
              <div className="co-summary-item">
                <span className="co-summary-val">{hasPlannedRoute ? "可用" : "暂无"}</span>
                <span className="co-summary-lbl">平台推荐路线</span>
              </div>
              <div className="co-summary-item">
                <span className="co-summary-val">{courseMaterials.length > 0 ? "已上传" : "暂无"}</span>
                <span className="co-summary-lbl">课程资料</span>
              </div>
            </div>
          </div>

          {/* ── Entry buttons ── */}
          <div className="co-entry-actions">
            <button
              className="co-btn co-btn--primary co-btn--lg"
              type="button"
              onClick={() => setPage("knowledgeLearning")}
            >
              进入知识点学习
            </button>
            <button
              className="co-btn co-btn--primary co-btn--lg"
              type="button"
              onClick={() => setPage("chat")}
            >
              打开 AI 问答
            </button>
            <button
              className="co-btn co-btn--ghost co-btn--lg"
              type="button"
              onClick={() => setPage("workspaceMaterials")}
            >
              上传资料
            </button>
          </div>
        </div>

        {/* ── Right sidebar - course info ── */}
        <aside className="co-sidebar">
          <div className="co-card co-side-card">
            <div className="co-side-card-header">
              <h3 className="co-side-card-title">当前课程</h3>
            </div>
            <div className="co-course-info">
              <p className="co-course-name">{courseLabel || "未选择"}</p>
              <p className="co-course-detail">
                路线来源：{hasPlannedRoute ? "平台预设路线可用" : "需上传资料生成路线"}
              </p>
              <p className="co-course-detail">
                学习目标：{GOAL_OPTIONS.find((g) => g.value === effectiveGoalConfig.goal)?.label || "系统学习"}
              </p>
              <p className="co-course-detail">
                资料数量：{courseMaterials.length} 个
              </p>
            </div>
          </div>

          <div className="co-card co-side-card co-ai-card">
            <div className="co-side-card-header">
              <h3 className="co-side-card-title">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" style={{ marginRight: 6 }}>
                  <path d="M12 2a10 10 0 1 0 10 10h-10v-10z" />
                </svg>
                AI 建议
              </h3>
            </div>
            <p className="co-ai-suggestion">
              {courseMaterials.length === 0
                ? "还没有上传课程资料，建议上传教材、课件或笔记，或直接使用平台推荐路线开始学习。"
                : hasPlannedRoute
                  ? "已上传资料，你可以选择「我的资料路线」或「平台推荐路线」开始学习。"
                  : "已上传资料，AI 将基于你的资料生成个性化学习路线。"}
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
