import { useEffect, useState } from "react";

const API_BASE = "/api";

const ACTIVITY_LABELS = {
  task_done: "完成任务",
  knowledge_progress: "知识点进度",
  material_uploaded: "上传资料",
  code_session: "编程练习",
  question_attempt: "练习作答",
  challenge_created: "AI 出题",
};

export default function LearningDataCenter({ user, getSubjectLabel }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE}/learning/dashboard?username=${encodeURIComponent(user.username)}`
      );
      if (res.ok) {
        const json = await res.json();
        setData(json);
      } else {
        setError("学习数据加载失败，请稍后重试。");
      }
    } catch (e) {
      setError("学习数据加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [user?.username]);

  if (loading) {
    return (
      <div className="empty-state">学习数据加载中...</div>
    );
  }

  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="ghost-button compact" onClick={fetchDashboard} style={{ marginTop: 12 }}>
          重试
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="empty-state">
        <p>当前学习数据还不多，可以先创建课程、上传资料或完成学习任务。</p>
      </div>
    );
  }

  const ov = data.overview || {};
  const isEmpty =
    ov.course_count === 0 &&
    ov.material_count === 0 &&
    ov.knowledge_point_count === 0 &&
    ov.code_session_count === 0 &&
    ov.question_count === 0;

  if (isEmpty) {
    return (
      <div className="empty-state">
        <p>当前学习数据还不多，可以先创建课程、上传资料或完成学习任务。</p>
        <button className="ghost-button compact" onClick={fetchDashboard} style={{ marginTop: 12 }}>
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
          <h2 style={{ margin: 0 }}>学习数据中心</h2>
          <p style={{ margin: "4px 0 0", color: "#6b7280", fontSize: 14 }}>
            汇总你的课程、资料、任务、练习和知识点掌握情况
          </p>
        </div>
        <button className="ghost-button compact" onClick={fetchDashboard}>
          刷新数据
        </button>
      </div>

      {/* ── Overview Stats ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 12px" }}>总览统计</h3>
        <div className="learning-stats-grid">
          <div className="learning-stat-card">
            <div className="learning-stat-label">课程</div>
            <div className="learning-stat-value">{ov.course_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">资料</div>
            <div className="learning-stat-value">{ov.material_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">知识点</div>
            <div className="learning-stat-value">{ov.knowledge_point_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">平均掌握度</div>
            <div className="learning-stat-value">{ov.average_mastery}%</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">待完成任务</div>
            <div className="learning-stat-value">{ov.todo_task_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">进行中任务</div>
            <div className="learning-stat-value">{ov.doing_task_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">已完成任务</div>
            <div className="learning-stat-value">{ov.done_task_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">编程练习</div>
            <div className="learning-stat-value">{ov.code_session_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">AI 出题</div>
            <div className="learning-stat-value">{ov.challenge_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">练习题</div>
            <div className="learning-stat-value">{ov.question_count}</div>
          </div>
          <div className="learning-stat-card">
            <div className="learning-stat-label">作答次数</div>
            <div className="learning-stat-value">{ov.attempt_count}</div>
          </div>
        </div>
      </section>

      {/* ── Weak Points ── */}
      {data.weak_points && data.weak_points.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>薄弱知识点 Top 5</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {data.weak_points.map((wp, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "8px 12px",
                  background: "#fef2f2",
                  borderRadius: 8,
                  fontSize: 14,
                }}
              >
                <div>
                  <span style={{ fontWeight: 600 }}>{wp.title}</span>
                  <span style={{ color: "#6b7280", marginLeft: 8 }}>
                    {getSubjectLabel ? getSubjectLabel(wp.course_id) : wp.course_name}
                  </span>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 12,
                      background: wp.status === "not_started" ? "#fef3c7" : wp.status === "learning" ? "#dbeafe" : "#ede9fe",
                      color: wp.status === "not_started" ? "#92400e" : wp.status === "learning" ? "#1e40af" : "#6b21a8",
                    }}
                  >
                    {wp.status === "not_started" ? "未开始" : wp.status === "learning" ? "学习中" : wp.status === "mastered" ? "已掌握" : wp.status === "reviewing" ? "复习中" : wp.status}
                  </span>
                  <span style={{ fontWeight: 600, color: wp.mastery_score > 0 ? "#dc2626" : "#9ca3af" }}>
                    {wp.mastery_score}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Recent Activities ── */}
      {data.recent_activities && data.recent_activities.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>最近学习动态</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {data.recent_activities.map((act, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  padding: "6px 0",
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
                      background: "#e0e7ff",
                      color: "#3730a3",
                    }}
                  >
                    {ACTIVITY_LABELS[act.type] || act.type}
                  </span>
                  <span>{act.title}</span>
                </div>
                <div style={{ display: "flex", gap: 8, color: "#6b7280", fontSize: 12 }}>
                  {act.course_id && (
                    <span>{getSubjectLabel ? getSubjectLabel(act.course_id) : act.course_name}</span>
                  )}
                  {act.created_at && (
                    <span>{new Date(act.created_at + "Z").toLocaleString()}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Course Summaries ── */}
      {data.course_summaries && data.course_summaries.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>课程概览</h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 12,
            }}
          >
            {data.course_summaries.map((cs, idx) => (
              <div
                key={idx}
                style={{
                  padding: 16,
                  borderRadius: 12,
                  background: "#f8fafc",
                  border: "1px solid #e2e8f0",
                }}
              >
                <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 8 }}>
                  {getSubjectLabel ? getSubjectLabel(cs.course_id) : cs.course_name}
                </div>
                <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.8 }}>
                  <div>资料：{cs.material_count} | 知识点：{cs.knowledge_point_count}</div>
                  <div>平均掌握度：{cs.average_mastery}%</div>
                  <div>
                    任务：待办 {cs.todo_task_count} / 进行中 {cs.doing_task_count} / 已完成 {cs.done_task_count}
                  </div>
                  <div>编程练习：{cs.code_session_count} | AI 出题：{cs.challenge_count}</div>
                  <div>练习题：{cs.question_count}</div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Recommendations ── */}
      {data.recommendations && data.recommendations.length > 0 && (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>推荐下一步</h3>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, color: "#374151", lineHeight: 1.8 }}>
            {data.recommendations.map((rec, idx) => (
              <li key={idx}>{rec}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
