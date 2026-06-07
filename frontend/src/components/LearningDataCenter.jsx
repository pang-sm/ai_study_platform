import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";

const ACTIVITY_LABELS = {
  task_done: "完成任务",
  task_created: "创建任务",
  learning_record: "学习记录",
  knowledge_progress: "知识点学习",
  material_uploaded: "上传资料",
  code_session: "编程练习",
  code_attempt: "编程提交",
  question_attempt: "练习作答",
  practice: "完成练习",
  chat: "AI 问答",
  report: "学习报告",
};

const ACTIVITY_DOTS = {
  task_done: "green",
  task_created: "orange",
  material_uploaded: "blue",
  practice: "purple",
  question_attempt: "purple",
  chat: "cyan",
  code_session: "cyan",
  code_attempt: "cyan",
  knowledge_progress: "green",
  report: "blue",
};

function safeNum(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, safeNum(value)));
}

function formatPercent(value) {
  return `${Math.round(clampPercent(value))}%`;
}

function formatDuration(minutes) {
  const total = Math.max(0, Math.round(safeNum(minutes)));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours <= 0) return `${mins} 分钟`;
  if (mins === 0) return `${hours} 小时`;
  return `${hours} 小时 ${mins} 分钟`;
}

function formatRelativeTime(value) {
  if (!value) return "";
  const text = String(value);
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(text)
    ? `${text}Z`
    : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text;
  const diff = Date.now() - date.getTime();
  const minute = 60 * 1000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < hour) return `${Math.max(1, Math.round(diff / minute))} 分钟前`;
  if (diff < day) return `${Math.round(diff / hour)} 小时前`;
  if (diff < day * 7) return `${Math.round(diff / day)} 天前`;
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function getCourseName(item, getSubjectLabel) {
  const raw = item?.course_id || item?.course_name || item?.subject || "";
  if (!raw) return "未分类课程";
  return getSubjectLabel?.(raw) || item?.course_name || raw;
}

function normalizeDashboardData(raw, getSubjectLabel) {
  const data = raw && typeof raw === "object" ? raw : {};
  const overview = data.overview || {};
  const trend = Array.isArray(data.trend) ? data.trend : [];
  const courses = Array.isArray(data.course_summaries) ? data.course_summaries : [];
  const weakPoints = Array.isArray(data.weak_points)
    ? data.weak_points.filter((item) => (item.knowledge_point_name || item.title || "").trim()).slice(0, 5)
    : [];
  const heatmap = Array.isArray(data.heatmap) ? data.heatmap : [];
  const activities = Array.isArray(data.recent_activities) ? data.recent_activities.slice(0, 10) : [];
  const goals = data.goals && typeof data.goals === "object" ? data.goals : {};
  const recommendations = Array.isArray(data.recommendations) ? data.recommendations : [];

  const hasPractice = safeNum(overview.practice_total) > 0;
  const kpis = [
    {
      label: "总学习时长",
      value: formatDuration(overview.total_study_minutes),
      hint: safeNum(overview.total_study_minutes) > 0 ? "来自真实学习时长记录" : "暂无学习时长记录",
      tone: "blue",
      target_page: "",
    },
    {
      label: "本周学习天数",
      value: `${safeNum(overview.active_days_this_week)} 天`,
      hint: "按真实活动日期去重",
      tone: "cyan",
      target_page: "",
    },
    {
      label: "完成任务数",
      value: `${safeNum(overview.completed_tasks)} 个`,
      hint: `待完成 ${safeNum(overview.pending_tasks)} 个`,
      tone: "orange",
      target_page: "taskCenter",
    },
    {
      label: "练习正确率",
      value: formatPercent(overview.practice_accuracy),
      hint: hasPractice ? `${safeNum(overview.practice_correct)} / ${safeNum(overview.practice_total)} 题正确` : "暂无练习记录",
      tone: "blue",
      target_page: "practiceCenter",
    },
    {
      label: "AI 提问次数",
      value: `${safeNum(overview.ai_question_count)} 次`,
      hint: "来自用户 AI 问答消息",
      tone: "purple",
      target_page: "chat",
    },
    {
      label: "连续学习天数",
      value: `${safeNum(overview.streak_days)} 天`,
      hint: `最佳连续 ${safeNum(overview.best_streak_days)} 天`,
      tone: "red",
      target_page: "",
    },
  ];

  const subjectMastery = courses
    .filter((course) => safeNum(course.knowledge_point_count) > 0 || safeNum(course.practice_count) > 0 || safeNum(course.material_count) > 0)
    .map((course) => ({
      ...course,
      name: getCourseName(course, getSubjectLabel),
      value: clampPercent(course.average_mastery),
      meta: `${safeNum(course.knowledge_point_count)} 个知识点 · ${safeNum(course.practice_count)} 次练习`,
    }))
    .slice(0, 6);

  return {
    kpis,
    trendDays: trend,
    subjectMastery,
    weakPoints,
    heatmapDays: heatmap,
    activities,
    goals,
    recommendations,
    hasTrendData: trend.some((day) => safeNum(day.study_minutes) > 0 || safeNum(day.completed_tasks) > 0 || safeNum(day.practice_count) > 0 || safeNum(day.ai_question_count) > 0),
    hasHeatmapData: heatmap.some((day) => safeNum(day.activity_count) > 0),
  };
}

function TrendChart({ days }) {
  const max = Math.max(...days.map((day) => safeNum(day.study_minutes)), 1);
  const points = days.map((day, index) => {
    const x = 28 + index * 84;
    const y = 166 - (safeNum(day.study_minutes) / max) * 118;
    return { ...day, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const area = points.length ? `${path} L ${points[points.length - 1].x} 176 L ${points[0].x} 176 Z` : "";

  return (
    <div className="ldc-trend-chart">
      <svg viewBox="0 0 560 210" role="img" aria-label="最近 7 天真实学习趋势">
        <defs>
          <linearGradient id="ldcTrendFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0.03" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((line) => (
          <line key={line} x1="24" x2="536" y1={48 + line * 42} y2={48 + line * 42} className="ldc-chart-grid" />
        ))}
        {area && <path d={area} fill="url(#ldcTrendFill)" />}
        {path && <path d={path} className="ldc-chart-line" />}
        {points.map((point) => (
          <g key={point.date}>
            <circle cx={point.x} cy={point.y} r="5" className="ldc-chart-dot" />
            <text x={point.x} y={point.y - 12} textAnchor="middle" className="ldc-chart-value">
              {safeNum(point.study_minutes)}
            </text>
            <text x={point.x} y="202" textAnchor="middle" className="ldc-chart-label">
              {String(point.date || "").slice(5)}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

function GoalRow({ label, current, target, formatter = (v) => String(v), onClick }) {
  const progress = Math.min(100, Math.round((safeNum(current) / Math.max(1, safeNum(target, 1))) * 100));
  return (
    <button type="button" className="ldc-goal-row ldc-clickable-row" onClick={onClick}>
      <div className="ldc-progress-title">
        <span>{label}</span>
        <strong>{formatter(current)} / {formatter(target)}</strong>
      </div>
      <div className="ldc-progress-track">
        <span style={{ width: `${progress}%` }} />
      </div>
    </button>
  );
}

export default function LearningDataCenter({ user, getSubjectLabel, onNavigate }) {
  const [rawData, setRawData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const navigate = (targetPage, targetParams = {}) => {
    if (!targetPage || !onNavigate) return;
    onNavigate(targetPage, { ...targetParams, from: "learningDataCenter" });
  };

  const fetchDashboard = async () => {
    if (!user?.username) {
      setLoading(false);
      setRawData({});
      return;
    }
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ username: user.username });
      const res = await fetch(`${API_BASE}/learning/dashboard?${params.toString()}`);
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(json.detail || `HTTP ${res.status}`);
      }
      setRawData(json || {});
    } catch (err) {
      setError(err.message || "学习数据加载失败，请稍后重试。");
      setRawData({});
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [user?.username]);

  const dashboard = useMemo(
    () => normalizeDashboardData(rawData, getSubjectLabel),
    [rawData, getSubjectLabel],
  );

  if (loading) {
    return <div className="empty-state">学习数据加载中...</div>;
  }

  return (
    <div className="ldc-page">
      <header className="ldc-header">
        <div>
          <h1>学习数据中心</h1>
          <p>查看你的学习表现、进度趋势与薄弱点分析</p>
          {error && (
            <div className="ldc-error-banner">
              当前接口返回异常，已显示真实空状态：{error}
            </div>
          )}
        </div>
        <div className="ldc-header-actions">
          <select className="ldc-select" value="7d" disabled aria-label="时间范围">
            <option value="7d">近7天</option>
          </select>
          <button className="ldc-refresh-button" onClick={fetchDashboard} disabled={loading}>
            刷新数据
          </button>
        </div>
      </header>

      <section className="ldc-kpi-grid" aria-label="学习统计">
        {dashboard.kpis.map((item) => {
          const content = (
            <>
              <div className={`ldc-kpi-icon ldc-tone-${item.tone}`} />
              <div className="ldc-kpi-body">
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.hint}</small>
              </div>
            </>
          );
          return item.target_page ? (
            <button key={item.label} type="button" className="ldc-kpi-card ldc-clickable-card" onClick={() => navigate(item.target_page)}>
              {content}
            </button>
          ) : (
            <article key={item.label} className="ldc-kpi-card">
              {content}
            </article>
          );
        })}
      </section>

      <section className="ldc-main-grid">
        <article className="ldc-card ldc-card-large">
          <div className="ldc-card-header">
            <div>
              <h2>学习趋势</h2>
              <p>最近 7 天真实学习时长、任务、练习和 AI 提问</p>
            </div>
          </div>
          {dashboard.hasTrendData ? (
            <TrendChart days={dashboard.trendDays} />
          ) : (
            <div className="ldc-empty-panel">暂无学习趋势数据</div>
          )}
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>学科掌握度</h2>
          </div>
          {dashboard.subjectMastery.length > 0 ? (
            <div className="ldc-progress-list">
              {dashboard.subjectMastery.map((item) => (
                <button
                  key={item.course_id || item.name}
                  type="button"
                  className="ldc-progress-row ldc-clickable-row"
                  onClick={() => navigate("dashboard", { courseId: item.course_id })}
                >
                  <div className="ldc-progress-title">
                    <span>{item.name}</span>
                    <strong>{formatPercent(item.value)}</strong>
                  </div>
                  <div className="ldc-progress-track">
                    <span style={{ width: `${item.value}%` }} />
                  </div>
                  <small>{item.meta}</small>
                </button>
              ))}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无学科掌握度数据，完成练习或知识点学习后将自动生成。</div>
          )}
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>薄弱知识点</h2>
          </div>
          {dashboard.weakPoints.length > 0 ? (
            <div className="ldc-weak-list">
              {dashboard.weakPoints.map((item, index) => {
                const title = item.knowledge_point_name || item.title;
                const mastery = clampPercent(item.mastery ?? item.mastery_score);
                return (
                  <button
                    key={`${item.knowledge_point_id || title}-${index}`}
                    type="button"
                    className="ldc-weak-row ldc-clickable-row"
                    onClick={() => navigate("knowledgeLearning", { courseId: item.course_id, knowledgePointId: item.knowledge_point_id })}
                  >
                    <span className="ldc-rank">{index + 1}</span>
                    <div>
                      <strong>{title}</strong>
                      <small>{getCourseName(item, getSubjectLabel)} · {item.reason || item.source || "真实学习数据"}</small>
                    </div>
                    <div className="ldc-weak-meter">
                      <span style={{ width: `${Math.max(4, mastery)}%` }} />
                    </div>
                    <em>掌握度 {formatPercent(mastery)}</em>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无薄弱知识点，完成更多练习或知识点学习后将自动分析。</div>
          )}
        </article>
      </section>

      <section className="ldc-lower-grid">
        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>学习热力图</h2>
            <p>最近 6 周真实活跃情况</p>
          </div>
          <div className="ldc-heatmap" aria-label="学习热力图">
            {dashboard.heatmapDays.map((day) => (
              <span key={day.date} className={`ldc-heat-cell level-${safeNum(day.level)}`} title={`${day.date}：${safeNum(day.activity_count)} 次活动`} />
            ))}
          </div>
          {!dashboard.hasHeatmapData && <div className="ldc-heat-empty">暂无学习活动</div>}
          <div className="ldc-heat-legend"><span>少</span><i /><i className="level-1" /><i className="level-2" /><i className="level-3" /><i className="level-4" /><span>多</span></div>
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>最近学习记录</h2>
          </div>
          {dashboard.activities.length > 0 ? (
            <div className="ldc-activity-list">
              {dashboard.activities.map((activity, index) => (
                <button
                  key={`${activity.created_at || index}-${activity.title}`}
                  type="button"
                  className="ldc-activity-row ldc-clickable-row"
                  onClick={() => navigate(activity.target_page, activity.target_params)}
                >
                  <span className={`ldc-activity-dot ${ACTIVITY_DOTS[activity.type] || "blue"}`} />
                  <div>
                    <strong>{activity.title}</strong>
                    <small>{ACTIVITY_LABELS[activity.type] || activity.type || "学习"} · {getCourseName(activity, getSubjectLabel)}{activity.subtitle ? ` · ${activity.subtitle}` : ""}</small>
                  </div>
                  <time>{formatRelativeTime(activity.created_at)}</time>
                </button>
              ))}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无最近学习记录</div>
          )}
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <div>
              <h2>本周目标达成</h2>
              <p>{dashboard.goals.configured ? "来自学习目标设置" : "未设置目标，使用展示参考线"}</p>
            </div>
            <button type="button" className="ldc-link-button" onClick={() => navigate("profileEdit")}>去学习设置</button>
          </div>
          <div className="ldc-goal-list">
            <GoalRow label="学习时长参考线" current={dashboard.goals.current_study_minutes} target={dashboard.goals.study_minutes_goal || dashboard.goals.reference_study_minutes_goal || 300} formatter={formatDuration} onClick={() => navigate("profileEdit")} />
            <GoalRow label="任务完成参考线" current={dashboard.goals.current_completed_tasks} target={dashboard.goals.task_goal || dashboard.goals.reference_task_goal || 5} formatter={(v) => `${safeNum(v)} 个`} onClick={() => navigate("taskCenter")} />
            <GoalRow label="练习正确率参考线" current={dashboard.goals.current_practice_accuracy} target={dashboard.goals.practice_accuracy_goal || dashboard.goals.reference_practice_accuracy_goal || 80} formatter={formatPercent} onClick={() => navigate("practiceCenter")} />
            <GoalRow label="AI 提问参考线" current={dashboard.goals.current_ai_questions} target={dashboard.goals.ai_question_goal || dashboard.goals.reference_ai_question_goal || 10} formatter={(v) => `${safeNum(v)} 次`} onClick={() => navigate("chat")} />
          </div>
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>AI 学习建议</h2>
          </div>
          {dashboard.recommendations.length > 0 ? (
            <div className="ldc-recommend-list">
              {dashboard.recommendations.slice(0, 4).map((item, index) => (
                <div key={item.id || `${item.title}-${index}`} className="ldc-recommend-item">
                  <span>{index + 1}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.reason}</p>
                    <button type="button" className="ldc-link-button" onClick={() => navigate(item.target_page, item.target_params)}>
                      {item.action_text || "去处理"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无学习建议，完成更多学习行为后将自动生成。</div>
          )}
        </article>
      </section>
    </div>
  );
}
