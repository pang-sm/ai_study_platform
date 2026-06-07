import { useEffect, useMemo, useState } from "react";
import "./ReviewCenter.css";

const API_BASE = "/api";

const EVENT_LABELS = {
  question_incorrect: "答题错误",
  ai_feedback_negative: "AI 负向反馈",
  task_reopened: "任务重开",
};

const STATUS_LABELS = {
  not_started: "未开始",
  learning: "学习中",
  mastering: "掌握中",
  mastered: "已掌握",
  weak: "薄弱",
  review: "待复习",
  reviewing: "复习中",
};

const SORT_OPTIONS = [
  { value: "mastery_asc", label: "掌握度从低到高" },
  { value: "negative_desc", label: "负向事件从高到低" },
  { value: "wrong_desc", label: "错题数从高到低" },
];

function safeNum(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, safeNum(value)));
}

function formatTime(value) {
  if (!value) return "暂无数据";
  const normalized = typeof value === "string" && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(value)
    ? `${value}Z`
    : value;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return "暂无数据";
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

function getCourseText(item, getSubjectLabel) {
  const course = item?.course_id || item?.course_name || item?.course || "";
  return course ? (getSubjectLabel?.(course) || item?.course_name || course) : "未分类课程";
}

function getTitle(item) {
  return item?.title || item?.name || item?.knowledge_point_name || "未命名知识点";
}

function getMastery(item) {
  return clampPercent(item?.mastery_score ?? item?.mastery ?? item?.progress ?? item?.mastery_rate ?? 0);
}

function getSeverityClass(mastery) {
  if (mastery < 40) return "danger";
  if (mastery < 70) return "warning";
  return "good";
}

function getStatus(item) {
  const raw = item?.status || item?.progress_status || "";
  return raw || "review";
}

export default function ReviewCenter({ user, getSubjectLabel, setPage }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creatingId, setCreatingId] = useState(null);
  const [searchText, setSearchText] = useState("");
  const [courseFilter, setCourseFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sortMode, setSortMode] = useState("mastery_asc");

  const fetchReviewData = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE}/review/center?username=${encodeURIComponent(user.username)}`,
      );
      if (res.ok) {
        const json = await res.json();
        setData(json);
      } else {
        setError("复盘数据加载失败，请稍后重试。");
      }
    } catch (e) {
      setError("复盘数据加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReviewData();
  }, [user?.username]);

  const createReviewTask = async (params = {}) => {
    setCreatingId(params.key || "new");
    try {
      const res = await fetch(`${API_BASE}/review/tasks/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: params.course_id || "",
          knowledge_point_id: params.knowledge_point_id || null,
          question_id: params.question_id || null,
          title: params.title || "",
          description: params.description || "",
        }),
      });
      if (res.ok) {
        await fetchReviewData();
      } else {
        const errData = await res.json();
        alert(errData.detail || "创建失败");
      }
    } catch (e) {
      console.error("Failed to create review task:", e);
    } finally {
      setCreatingId(null);
    }
  };

  const normalized = useMemo(() => {
    const source = data || {};
    const wrongQuestions = Array.isArray(source.wrong_questions) ? source.wrong_questions : [];
    const negativeEvents = Array.isArray(source.negative_events) ? source.negative_events : [];
    const reviewTasks = Array.isArray(source.review_tasks) ? source.review_tasks : [];
    const weakPoints = Array.isArray(source.weak_points) ? source.weak_points : [];

    const wrongByKp = new Map();
    wrongQuestions.forEach((item) => {
      if (!item?.knowledge_point_id) return;
      wrongByKp.set(item.knowledge_point_id, (wrongByKp.get(item.knowledge_point_id) || 0) + 1);
    });

    const negativeByKp = new Map();
    const latestByKp = new Map();
    negativeEvents.forEach((item) => {
      if (!item?.knowledge_point_id) return;
      negativeByKp.set(item.knowledge_point_id, (negativeByKp.get(item.knowledge_point_id) || 0) + 1);
      if (!latestByKp.get(item.knowledge_point_id) || String(item.created_at || "") > String(latestByKp.get(item.knowledge_point_id) || "")) {
        latestByKp.set(item.knowledge_point_id, item.created_at);
      }
    });

    const enrichedWeakPoints = weakPoints.map((item, index) => {
      const mastery = getMastery(item);
      const kpId = item.knowledge_point_id || item.id || null;
      return {
        ...item,
        _key: kpId || `${getTitle(item)}-${index}`,
        _title: getTitle(item),
        _course: getCourseText(item, getSubjectLabel),
        _courseId: item.course_id || item.course || "",
        _status: getStatus(item),
        _mastery: mastery,
        _severity: getSeverityClass(mastery),
        _wrongCount: safeNum(item.wrong_count ?? item.mistake_count ?? wrongByKp.get(kpId)),
        _negativeCount: safeNum(item.negative_count ?? item.event_count ?? negativeByKp.get(kpId)),
        _lastStudiedAt: item.last_studied_at || item.updated_at || item.created_at || latestByKp.get(kpId),
        _practiceCount: safeNum(item.practice_count),
        _kpId: kpId,
      };
    });

    const courses = Array.from(new Map(enrichedWeakPoints.map((item) => [item._courseId || item._course, item._course])).entries());
    const ov = source.overview || {};
    return {
      overview: ov,
      wrongQuestions,
      negativeEvents,
      reviewTasks,
      weakPoints: enrichedWeakPoints,
      courses,
    };
  }, [data, getSubjectLabel]);

  const filteredWeakPoints = useMemo(() => {
    const query = searchText.trim().toLowerCase();
    const list = normalized.weakPoints
      .filter((item) => !query || item._title.toLowerCase().includes(query))
      .filter((item) => !courseFilter || item._courseId === courseFilter || item._course === courseFilter)
      .filter((item) => !statusFilter || item._status === statusFilter);

    return [...list].sort((a, b) => {
      if (sortMode === "negative_desc") return b._negativeCount - a._negativeCount;
      if (sortMode === "wrong_desc") return b._wrongCount - a._wrongCount;
      return a._mastery - b._mastery;
    });
  }, [normalized.weakPoints, searchText, courseFilter, statusFilter, sortMode]);

  if (loading) {
    return <div className="empty-state">复盘数据加载中...</div>;
  }

  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="ghost-button compact" onClick={fetchReviewData} style={{ marginTop: 12 }}>
          重试
        </button>
      </div>
    );
  }

  const ov = normalized.overview || {};
  const wrongCount = safeNum(ov.wrong_question_count);
  const weakCount = safeNum(ov.weak_knowledge_count);
  const negativeCount = safeNum(ov.negative_event_count);
  const taskCount = safeNum(ov.review_task_count);

  const overviewCards = [
    { key: "wrong", icon: "✦", label: "错题", value: wrongCount, desc: "需要重新练习的题目数量", state: wrongCount > 0 ? "建议处理" : "状态良好", tone: "red" },
    { key: "weak", icon: "◇", label: "薄弱知识点", value: weakCount, desc: "建议优先复盘的知识点", state: weakCount > 0 ? "建议处理" : "状态良好", tone: "orange" },
    { key: "negative", icon: "!", label: "负向事件", value: negativeCount, desc: "错误、卡顿、失败记录", state: negativeCount > 0 ? "建议处理" : "状态良好", tone: "amber" },
    { key: "task", icon: "✓", label: "复盘任务", value: taskCount, desc: "已创建的复盘任务数量", state: taskCount > 0 ? "持续推进" : "状态良好", tone: "green" },
  ];

  return (
    <div className="review-page">
      <header className="review-hero">
        <div>
          <h1>复盘中心</h1>
          <p>集中处理薄弱知识点、错题和负向事件，创建复盘任务，把问题转化为下一步学习行动。</p>
        </div>
        <button className="review-refresh-button" onClick={fetchReviewData}>
          刷新数据
        </button>
      </header>

      <section className="review-overview-grid" aria-label="复盘概览">
        {overviewCards.map((card) => (
          <article key={card.key} className={`review-overview-card tone-${card.tone}`}>
            <div className="review-overview-top">
              <span className="review-overview-icon">{card.icon}</span>
              <span className="review-overview-state">{card.state}</span>
            </div>
            <strong>{card.value}</strong>
            <div className="review-overview-label">{card.label}</div>
            <p>{card.desc}</p>
          </article>
        ))}
      </section>

      <section className="review-panel">
        <div className="review-panel-header">
          <div>
            <h2>薄弱知识点诊断</h2>
            <p>按掌握度、错题和负向事件综合排序，优先处理最值得复盘的内容。</p>
          </div>
          <span className="review-count-badge">{filteredWeakPoints.length} 个知识点</span>
        </div>

        <div className="review-toolbar">
          <input
            className="review-search"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="搜索知识点"
          />
          <select className="review-select" value={courseFilter} onChange={(e) => setCourseFilter(e.target.value)}>
            <option value="">全部课程</option>
            {normalized.courses.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select className="review-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select className="review-select" value={sortMode} onChange={(e) => setSortMode(e.target.value)}>
            {SORT_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>{item.label}</option>
            ))}
          </select>
        </div>

        {filteredWeakPoints.length > 0 ? (
          <div className="review-weak-list">
            {filteredWeakPoints.map((wp, idx) => (
              <article key={wp._key} className={`review-weak-card severity-${wp._severity}`}>
                <div className="review-weak-main">
                  <div className="review-weak-title-row">
                    <h3>{wp._title}</h3>
                    <span className={`review-status-pill status-${wp._status}`}>
                      {STATUS_LABELS[wp._status] || wp._status || "待复习"}
                    </span>
                  </div>
                  <p>{wp._course}</p>
                  <div className="review-weak-meta">
                    <span>错题 {wp._wrongCount}</span>
                    <span>负向事件 {wp._negativeCount}</span>
                    <span>最近学习 {formatTime(wp._lastStudiedAt)}</span>
                  </div>
                </div>

                <div className="review-diagnosis">
                  <div className="review-mastery-row">
                    <span>掌握度</span>
                    <strong>{wp._mastery}%</strong>
                  </div>
                  <div className="review-progress-track">
                    <span style={{ width: `${wp._mastery}%` }} />
                  </div>
                  <p>{wp._mastery < 40 ? "建议立即复盘并补练" : wp._mastery < 70 ? "建议安排专项巩固" : "保持复习节奏"}</p>
                </div>

                <div className="review-card-actions">
                  <button
                    className="review-primary-action"
                    disabled={creatingId === `wp-${idx}`}
                    onClick={() =>
                      createReviewTask({
                        key: `wp-${idx}`,
                        course_id: wp._courseId,
                        knowledge_point_id: wp._kpId,
                        title: `复盘：${wp._title}`,
                        description: `复习「${wp._title}」，并完成相关练习巩固掌握度。`,
                      })
                    }
                  >
                    {creatingId === `wp-${idx}` ? "创建中..." : "创建复盘任务"}
                  </button>
                  <button className="review-secondary-action" onClick={() => setPage?.("practiceCenter")}>
                    去练习
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="review-empty-card">
            <h3>暂无明显薄弱知识点</h3>
            <p>继续完成练习、AI 问答和学习任务后，系统会自动生成复盘建议。</p>
            <div className="review-empty-actions">
              <button className="review-primary-action" onClick={() => setPage?.("practiceCenter")}>去练习中心</button>
              <button className="review-secondary-action" onClick={() => setPage?.("learningDataCenter")}>去学习数据中心</button>
            </div>
          </div>
        )}
      </section>

      <section className="review-secondary-grid">
        <div className="review-panel review-compact-panel">
          <div className="review-panel-header">
            <h2>错题列表</h2>
            <span className="review-count-badge">{normalized.wrongQuestions.length}</span>
          </div>
          {normalized.wrongQuestions.length > 0 ? (
            <div className="review-mini-list">
              {normalized.wrongQuestions.slice(0, 6).map((wq) => (
                <article key={wq.attempt_id} className="review-mini-item">
                  <div>
                    <strong>{wq.title || "错题"}</strong>
                    <p>{getCourseText(wq, getSubjectLabel)} · {wq.knowledge_point_title || "暂无知识点"}</p>
                  </div>
                  <button
                    className="review-secondary-action"
                    disabled={creatingId === `wq-${wq.attempt_id}`}
                    onClick={() =>
                      createReviewTask({
                        key: `wq-${wq.attempt_id}`,
                        course_id: wq.course_id,
                        knowledge_point_id: wq.knowledge_point_id,
                        question_id: wq.question_id,
                        title: `复盘错题：${wq.title}`,
                        description: `复习「${wq.knowledge_point_title || wq.title}」并重新完成相关练习。`,
                      })
                    }
                  >
                    {creatingId === `wq-${wq.attempt_id}` ? "创建中" : "建任务"}
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <div className="review-soft-empty">暂无错题记录</div>
          )}
        </div>

        <div className="review-panel review-compact-panel">
          <div className="review-panel-header">
            <h2>负向事件</h2>
            <span className="review-count-badge">{normalized.negativeEvents.length}</span>
          </div>
          {normalized.negativeEvents.length > 0 ? (
            <div className="review-mini-list">
              {normalized.negativeEvents.slice(0, 6).map((evt) => (
                <article key={evt.event_id} className="review-mini-item">
                  <div>
                    <strong>{EVENT_LABELS[evt.event_type] || evt.event_type || "负向事件"}</strong>
                    <p>{evt.knowledge_point_title || "暂无知识点"} · {formatTime(evt.created_at)}</p>
                  </div>
                  <span className="review-delta">{evt.delta || 0}</span>
                </article>
              ))}
            </div>
          ) : (
            <div className="review-soft-empty">暂无负向事件</div>
          )}
        </div>

        <div className="review-panel review-compact-panel">
          <div className="review-panel-header">
            <h2>复盘任务</h2>
            <span className="review-count-badge">{normalized.reviewTasks.length}</span>
          </div>
          {normalized.reviewTasks.length > 0 ? (
            <div className="review-mini-list">
              {normalized.reviewTasks.slice(0, 6).map((task) => (
                <article key={task.task_id} className="review-mini-item">
                  <div>
                    <strong>{task.title}</strong>
                    <p>{getCourseText(task, getSubjectLabel)} · {task.knowledge_point_title || "复盘任务"}</p>
                  </div>
                  <span className="review-task-status">{task.status === "todo" ? "待办" : task.status === "doing" ? "进行中" : task.status === "done" ? "已完成" : task.status}</span>
                </article>
              ))}
            </div>
          ) : (
            <div className="review-soft-empty">暂无复盘任务</div>
          )}
        </div>
      </section>
    </div>
  );
}
