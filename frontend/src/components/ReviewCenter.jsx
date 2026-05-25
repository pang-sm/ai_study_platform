import { useEffect, useState } from "react";

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

export default function ReviewCenter({ user, getSubjectLabel }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [creatingId, setCreatingId] = useState(null);

  const fetchReviewData = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE}/review/center?username=${encodeURIComponent(user.username)}`
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

  if (!data) {
    return (
      <div className="empty-state">
        <p>当前没有明显需要复盘的内容，继续完成练习和任务后这里会自动更新。</p>
      </div>
    );
  }

  const ov = data.overview || {};
  const isEmpty =
    ov.wrong_question_count === 0 &&
    ov.weak_knowledge_count === 0 &&
    ov.negative_event_count === 0 &&
    ov.review_task_count === 0;

  if (isEmpty) {
    return (
      <div className="empty-state">
        <p>当前没有明显需要复盘的内容，继续完成练习和任务后这里会自动更新。</p>
        <button className="ghost-button compact" onClick={fetchReviewData} style={{ marginTop: 12 }}>
          刷新
        </button>
      </div>
    );
  }

  return (
    <div className="datacenter-shell">
      {/* ── Header ── */}
      <div className="datacenter-header">
        <div>
          <h2 style={{ margin: 0 }}>复盘中心</h2>
          <p style={{ margin: "4px 0 0", color: "#6b7280", fontSize: 14 }}>
            集中查看错题、薄弱知识点和需要复习的内容
          </p>
        </div>
        <button className="ghost-button compact" onClick={fetchReviewData}>
          刷新数据
        </button>
      </div>

      {/* ── Overview Stats ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 12px" }}>复盘概览</h3>
        <div className="learning-stats-grid">
          <div className="learning-stat-card">
            <div className="learning-stat-label">错题</div>
            <div className="learning-stat-value">{ov.wrong_question_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">薄弱知识点</div>
            <div className="learning-stat-value">{ov.weak_knowledge_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">负向事件</div>
            <div className="learning-stat-value">{ov.negative_event_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">复盘任务</div>
            <div className="learning-stat-value">{ov.review_task_count}</div>
          </div>
        </div>
      </section>

      {/* ── Wrong Questions ── */}
      {data.wrong_questions && data.wrong_questions.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>错题列表</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {data.wrong_questions.map((wq) => (
              <div
                key={wq.attempt_id}
                style={{
                  padding: 12,
                  borderRadius: 10,
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  fontSize: 14,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                  <div>
                    <span style={{ fontWeight: 600 }}>{wq.title}</span>
                    {wq.knowledge_point_title && (
                      <span style={{ color: "#6b7280", marginLeft: 8, fontSize: 13 }}>
                        [{wq.knowledge_point_title}]
                      </span>
                    )}
                  </div>
                  <span style={{ color: "#dc2626", fontWeight: 600, fontSize: 13 }}>
                    {wq.question_type === "choice" ? "选择题" : "简答题"}
                  </span>
                </div>
                <div style={{ fontSize: 13, color: "#4b5563", marginBottom: 4 }}>
                  你的答案：<span style={{ color: "#dc2626" }}>{wq.user_answer || "未作答"}</span>
                  {"　"}正确答案：<span style={{ color: "#059669" }}>{wq.correct_answer || "—"}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: "#9ca3af" }}>
                    {getSubjectLabel ? getSubjectLabel(wq.course_id) : wq.course_name}
                    {" · "}
                    {wq.created_at ? new Date(wq.created_at + "Z").toLocaleString() : ""}
                  </span>
                  <button
                    className="tiny-button"
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
                    style={{ color: "#0f766e" }}
                  >
                    {creatingId === `wq-${wq.attempt_id}` ? "创建中..." : "创建复盘任务"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Weak Points ── */}
      {data.weak_points && data.weak_points.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>薄弱知识点</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {data.weak_points.map((wp, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  background: "#fffbeb",
                  border: "1px solid #fde68a",
                  borderRadius: 10,
                  fontSize: 14,
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{wp.title}</span>
                  <span style={{ color: "#6b7280", marginLeft: 8, fontSize: 13 }}>
                    {getSubjectLabel ? getSubjectLabel(wp.course_id) : wp.course_name}
                  </span>
                  <span
                    style={{
                      marginLeft: 8,
                      padding: "1px 6px",
                      borderRadius: 4,
                      fontSize: 12,
                      background: "#fef3c7",
                      color: "#92400e",
                    }}
                  >
                    {STATUS_LABELS[wp.status] || wp.status}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <span style={{ fontWeight: 600, color: wp.mastery_score > 0 ? "#dc2626" : "#9ca3af" }}>
                    {wp.mastery_score}%
                  </span>
                  <button
                    className="tiny-button"
                    disabled={creatingId === `wp-${idx}`}
                    onClick={() =>
                      createReviewTask({
                        key: `wp-${idx}`,
                        course_id: wp.course_id,
                        knowledge_point_id: wp.knowledge_point_id,
                      })
                    }
                    style={{ color: "#0f766e" }}
                  >
                    {creatingId === `wp-${idx}` ? "创建中..." : "创建复盘任务"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Negative Events ── */}
      {data.negative_events && data.negative_events.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>负向掌握事件</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {data.negative_events.map((evt) => (
              <div
                key={evt.event_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 0",
                  borderBottom: "1px solid #f1f5f9",
                  fontSize: 14,
                }}
              >
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span
                    style={{
                      padding: "1px 6px",
                      borderRadius: 4,
                      fontSize: 12,
                      background: "#fce4ec",
                      color: "#c62828",
                    }}
                  >
                    {EVENT_LABELS[evt.event_type] || evt.event_type}
                  </span>
                  <span style={{ fontWeight: 600, color: "#dc2626" }}>{evt.delta}</span>
                  {evt.knowledge_point_title && (
                    <span style={{ color: "#4b5563" }}>{evt.knowledge_point_title}</span>
                  )}
                  {evt.reason && (
                    <span style={{ color: "#9ca3af", fontSize: 13 }}>— {evt.reason}</span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8, color: "#6b7280", fontSize: 12 }}>
                  {evt.course_id && (
                    <span>{getSubjectLabel ? getSubjectLabel(evt.course_id) : evt.course_id}</span>
                  )}
                  {evt.created_at && (
                    <span>{new Date(evt.created_at + "Z").toLocaleString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Review Tasks ── */}
      {data.review_tasks && data.review_tasks.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>复盘任务</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.review_tasks.map((t) => (
              <div
                key={t.task_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "10px 14px",
                  borderRadius: 10,
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  fontSize: 14,
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{t.title}</span>
                  {t.knowledge_point_title && (
                    <span style={{ color: "#6b7280", marginLeft: 8, fontSize: 13 }}>
                      [{t.knowledge_point_title}]
                    </span>
                  )}
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13 }}>
                  <span
                    style={{
                      padding: "1px 6px",
                      borderRadius: 4,
                      fontSize: 12,
                      background: t.status === "todo" ? "#fef3c7" : t.status === "doing" ? "#dbeafe" : "#e2e8f0",
                      color: t.status === "todo" ? "#92400e" : t.status === "doing" ? "#1e40af" : "#4b5563",
                    }}
                  >
                    {t.status === "todo" ? "待办" : t.status === "doing" ? "进行中" : t.status === "done" ? "已完成" : t.status}
                  </span>
                  {t.course_id && (
                    <span style={{ color: "#6b7280" }}>
                      {getSubjectLabel ? getSubjectLabel(t.course_id) : t.course_id}
                    </span>
                  )}
                  {t.due_date && (
                    <span style={{ color: "#9ca3af" }}>
                      {new Date(t.due_date + "Z").toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
