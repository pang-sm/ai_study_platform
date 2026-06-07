import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";

const ACTIVITY_LABELS = {
  task_done: "完成任务",
  knowledge_progress: "知识点学习",
  material_uploaded: "上传资料",
  code_session: "编程练习",
  question_attempt: "练习作答",
  challenge_created: "AI 出题",
  practice: "完成练习",
};

const ACTIVITY_DOTS = {
  task_done: "green",
  material_uploaded: "blue",
  practice: "purple",
  question_attempt: "purple",
  code_session: "cyan",
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

function dayKey(date) {
  return date.toISOString().slice(0, 10);
}

function parseActivityDate(value) {
  if (!value) return null;
  const text = String(value);
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(text)
    ? `${text}Z`
    : text;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function getCourseName(item, getSubjectLabel) {
  const raw = item?.course_id || item?.course_name || item?.subject || "";
  if (!raw) return "未分类课程";
  return getSubjectLabel?.(raw) || item?.course_name || raw;
}

function toRecommendationText(item) {
  if (!item) return "";
  if (typeof item === "string") return item;
  const title = item.title || "";
  const description = item.description || item.summary || "";
  return [title, description].filter(Boolean).join("：");
}

function normalizeDashboardData(raw, getSubjectLabel) {
  const data = raw && typeof raw === "object" ? raw : {};
  const overview = data.overview || {};
  const practice = data.practice_summary || {};
  const task = data.task_summary || {};
  const courses = Array.isArray(data.course_summaries) ? data.course_summaries : [];
  const weakPoints = Array.isArray(data.weak_points) ? data.weak_points.slice(0, 5) : [];
  const activities = Array.isArray(data.recent_activities) ? data.recent_activities.slice(0, 8) : [];

  const weekMinutes = safeNum(overview.week_study_minutes, safeNum(practice.week?.duration_minutes));
  const totalMinutes = Math.max(weekMinutes, courses.reduce((sum, course) => sum + safeNum(course.study_minutes), 0));
  const weekStudyDays = Math.min(7, new Set(activities.map((activity) => {
    const date = parseActivityDate(activity.created_at);
    return date ? dayKey(date) : "";
  }).filter(Boolean)).size);
  const completedTasks = safeNum(task.week_completed, safeNum(overview.done_task_count));
  const practiceAccuracy = safeNum(practice.week?.accuracy, safeNum(overview.week_practice_accuracy));
  const aiQuestionCount = safeNum(overview.attempt_count) + safeNum(overview.challenge_count);

  const subjectMastery = courses
    .map((course) => ({
      name: getCourseName(course, getSubjectLabel),
      value: clampPercent(course.average_mastery),
      meta: `${safeNum(course.knowledge_point_count)} 个知识点`,
    }))
    .filter((course) => course.value > 0 || course.meta !== "0 个知识点")
    .slice(0, 6);

  const trendDays = Array.from({ length: 7 }, (_, index) => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() - (6 - index));
    return {
      key: dayKey(date),
      label: date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }),
      minutes: 0,
    };
  });

  activities.forEach((activity) => {
    const date = parseActivityDate(activity.created_at);
    if (!date) return;
    const item = trendDays.find((day) => day.key === dayKey(date));
    if (item) {
      item.minutes += activity.type === "practice" ? Math.max(15, safeNum(practice.week?.duration_minutes) ? 20 : 15) : 8;
    }
  });
  if (weekMinutes > 0 && trendDays.every((day) => day.minutes === 0)) {
    trendDays[trendDays.length - 1].minutes = weekMinutes;
  }

  const heatmapDays = Array.from({ length: 42 }, (_, index) => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() - (41 - index));
    return { key: dayKey(date), level: 0 };
  });
  activities.forEach((activity) => {
    const date = parseActivityDate(activity.created_at);
    if (!date) return;
    const item = heatmapDays.find((day) => day.key === dayKey(date));
    if (item) item.level = Math.min(4, item.level + (activity.type === "practice" ? 2 : 1));
  });

  const defaultGoals = [
    { label: "学习时长目标", current: weekMinutes, target: 20 * 60, unit: "分钟", formatter: formatDuration },
    { label: "任务完成目标", current: completedTasks, target: 25, unit: "个" },
    { label: "练习正确率目标", current: practiceAccuracy, target: 85, unit: "%", formatter: formatPercent },
    { label: "AI 提问目标", current: aiQuestionCount, target: 40, unit: "次" },
  ];

  const recommendations = (Array.isArray(data.recommendations) ? data.recommendations : [])
    .map(toRecommendationText)
    .filter(Boolean)
    .slice(0, 3);
  if (recommendations.length === 0) {
    if (weakPoints.length > 0) recommendations.push(`建议优先复习 ${weakPoints[0].title || "薄弱知识点"}，再做专项练习巩固。`);
    if (practiceAccuracy > 0 && practiceAccuracy < 70) recommendations.push("本周练习正确率偏低，建议先复盘错题再继续刷题。");
    if (weekStudyDays < 3) recommendations.push("本周学习天数较少，建议安排更稳定的短时学习节奏。");
    if (recommendations.length === 0) recommendations.push("完成更多练习、任务或资料学习后，系统会给出更具体的建议。");
  }

  return {
    kpis: [
      { label: "总学习时长", value: formatDuration(totalMinutes), hint: totalMinutes > 0 ? "来自学习与练习记录" : "暂无学习时长", tone: "blue" },
      { label: "本周学习天数", value: `${weekStudyDays} 天`, hint: "按最近记录日期统计", tone: "cyan" },
      { label: "完成任务数", value: `${completedTasks} 个`, hint: `待完成 ${safeNum(task.pending, overview.todo_task_count)} 个`, tone: "orange" },
      { label: "练习正确率", value: formatPercent(practiceAccuracy), hint: `${safeNum(practice.week?.questions, overview.week_practice_questions)} 道题`, tone: "blue" },
      { label: "AI 提问次数", value: `${aiQuestionCount} 次`, hint: "练习作答与 AI 出题", tone: "purple" },
      { label: "连续学习天数", value: `${weekStudyDays} 天`, hint: weekStudyDays > 0 ? "按现有记录估算" : "暂无连续记录", tone: "red" },
    ],
    trendDays,
    subjectMastery,
    weakPoints,
    heatmapDays,
    activities,
    goals: defaultGoals,
    recommendations,
    hasTrendData: trendDays.some((day) => day.minutes > 0),
  };
}

function TrendChart({ days }) {
  const max = Math.max(...days.map((day) => day.minutes), 1);
  const points = days.map((day, index) => {
    const x = 28 + index * 84;
    const y = 166 - (day.minutes / max) * 118;
    return { ...day, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
  const area = `${path} L ${points[points.length - 1].x} 176 L ${points[0].x} 176 Z`;

  return (
    <div className="ldc-trend-chart">
      <svg viewBox="0 0 560 210" role="img" aria-label="最近 7 天学习时长趋势">
        <defs>
          <linearGradient id="ldcTrendFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2563eb" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#2563eb" stopOpacity="0.03" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((line) => (
          <line key={line} x1="24" x2="536" y1={48 + line * 42} y2={48 + line * 42} className="ldc-chart-grid" />
        ))}
        <path d={area} fill="url(#ldcTrendFill)" />
        <path d={path} className="ldc-chart-line" />
        {points.map((point) => (
          <g key={point.key}>
            <circle cx={point.x} cy={point.y} r="5" className="ldc-chart-dot" />
            <text x={point.x} y={point.y - 12} textAnchor="middle" className="ldc-chart-value">
              {point.minutes > 0 ? `${Math.round(point.minutes / 60 * 10) / 10}h` : "0"}
            </text>
            <text x={point.x} y="202" textAnchor="middle" className="ldc-chart-label">
              {point.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

export default function LearningDataCenter({ user, getSubjectLabel }) {
  const [rawData, setRawData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

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
    [rawData, getSubjectLabel]
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
              当前接口返回异常，已显示空状态兜底：{error}
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
        {dashboard.kpis.map((item) => (
          <article key={item.label} className="ldc-kpi-card">
            <div className={`ldc-kpi-icon ldc-tone-${item.tone}`} />
            <div className="ldc-kpi-body">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.hint}</small>
            </div>
          </article>
        ))}
      </section>

      <section className="ldc-main-grid">
        <article className="ldc-card ldc-card-large">
          <div className="ldc-card-header">
            <div>
              <h2>学习趋势</h2>
              <p>最近 7 天学习时长趋势</p>
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
                <div key={item.name} className="ldc-progress-row">
                  <div className="ldc-progress-title">
                    <span>{item.name}</span>
                    <strong>{formatPercent(item.value)}</strong>
                  </div>
                  <div className="ldc-progress-track">
                    <span style={{ width: `${item.value}%` }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无学科掌握度数据</div>
          )}
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>薄弱知识点 TOP5</h2>
          </div>
          {dashboard.weakPoints.length > 0 ? (
            <div className="ldc-weak-list">
              {dashboard.weakPoints.map((item, index) => {
                const mastery = clampPercent(item.mastery_score);
                return (
                  <div key={`${item.knowledge_point_id || item.title}-${index}`} className="ldc-weak-row">
                    <span className="ldc-rank">{index + 1}</span>
                    <div>
                      <strong>{item.title || "未命名知识点"}</strong>
                      <small>{getCourseName(item, getSubjectLabel)}</small>
                    </div>
                    <div className="ldc-weak-meter">
                      <span style={{ width: `${Math.max(4, mastery)}%` }} />
                    </div>
                    <em>掌握度 {formatPercent(mastery)}</em>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无薄弱知识点，完成更多练习后将自动分析。</div>
          )}
        </article>
      </section>

      <section className="ldc-lower-grid">
        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>学习热力图</h2>
            <p>最近 6 周活跃情况</p>
          </div>
          <div className="ldc-heatmap" aria-label="学习热力图">
            {dashboard.heatmapDays.map((day) => (
              <span key={day.key} className={`ldc-heat-cell level-${day.level}`} title={day.key} />
            ))}
          </div>
          <div className="ldc-heat-legend"><span>少</span><i /><i className="level-1" /><i className="level-2" /><i className="level-3" /><i className="level-4" /><span>多</span></div>
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>最近学习记录</h2>
          </div>
          {dashboard.activities.length > 0 ? (
            <div className="ldc-activity-list">
              {dashboard.activities.map((activity, index) => (
                <div key={`${activity.created_at || index}-${activity.title}`} className="ldc-activity-row">
                  <span className={`ldc-activity-dot ${ACTIVITY_DOTS[activity.type] || "blue"}`} />
                  <div>
                    <strong>{activity.title || ACTIVITY_LABELS[activity.type] || "学习记录"}</strong>
                    <small>{ACTIVITY_LABELS[activity.type] || activity.type || "学习"} · {getCourseName(activity, getSubjectLabel)}</small>
                  </div>
                  <time>{formatRelativeTime(activity.created_at)}</time>
                </div>
              ))}
            </div>
          ) : (
            <div className="ldc-empty-panel">暂无最近学习记录</div>
          )}
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>本周目标达成</h2>
            <p>未设置目标时使用展示兜底</p>
          </div>
          <div className="ldc-goal-list">
            {dashboard.goals.map((goal) => {
              const progress = Math.min(100, Math.round((safeNum(goal.current) / Math.max(1, goal.target)) * 100));
              const currentText = goal.formatter ? goal.formatter(goal.current) : `${Math.round(safeNum(goal.current))} ${goal.unit}`;
              const targetText = goal.formatter ? goal.formatter(goal.target) : `${goal.target} ${goal.unit}`;
              return (
                <div key={goal.label} className="ldc-goal-row">
                  <div className="ldc-progress-title">
                    <span>{goal.label}</span>
                    <strong>{currentText} / {targetText}</strong>
                  </div>
                  <div className="ldc-progress-track">
                    <span style={{ width: `${progress}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </article>

        <article className="ldc-card">
          <div className="ldc-card-header">
            <h2>AI 学习建议</h2>
          </div>
          <div className="ldc-recommend-list">
            {dashboard.recommendations.slice(0, 3).map((item, index) => (
              <div key={`${item}-${index}`} className="ldc-recommend-item">
                <span>{index + 1}</span>
                <p>{item}</p>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
