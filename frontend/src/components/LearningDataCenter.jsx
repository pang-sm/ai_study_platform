import { useEffect, useState } from "react";

const API_BASE = "/api";

const ACTIVITY_LABELS = {
  task_done: "任务",
  knowledge_progress: "知识点",
  material_uploaded: "资料",
  code_session: "编程",
  question_attempt: "作答",
  challenge_created: "出题",
  practice: "练习",
};

function safeNum(v, fallback = 0) { return typeof v === "number" && !isNaN(v) ? v : fallback; }
function fmtPct(v) { const n = safeNum(v, -1); return n >= 0 ? `${Math.round(n)}%` : "--"; }
function fmtDur(s) { const m = Math.round(safeNum(s) / 60); return m > 0 ? `${m} 分钟` : "0 分钟"; }
function fmtTime(v) { try { return v ? new Date((typeof v === "string" && !v.endsWith("Z") ? v + "Z" : v)).toLocaleString("zh-CN") : ""; } catch { return v || ""; } }

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
  const ps = data.practice_summary || {};
  const ts = data.task_summary || {};
  const hasPractice = safeNum(ov.today_practice_questions) > 0 || safeNum(ps.week?.questions) > 0;
  const hasOldData = ov.course_count > 0 || ov.material_count > 0 || ov.knowledge_point_count > 0;
  const isEmpty = !hasOldData && !hasPractice && safeNum(ov.todo_task_count) === 0;

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

      {/* ── Practice Summary ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 12px" }}>练习表现</h3>
        {!hasPractice ? (
          <p style={{ color: "#6b7280", fontSize: 14 }}>还没有练习数据。完成一次练习后，这里会展示正确率、练习题数和学习时长。</p>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 12 }}>
            <div className="learning-stat-card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: "#1e293b" }}>今日练习</div>
              <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.8 }}>
                <div>练习次数：{safeNum(ps.today?.sessions)} 次</div>
                <div>完成题数：{safeNum(ps.today?.questions)} 题 / 正确 {safeNum(ps.today?.correct)} 题</div>
                <div>正确率：<strong>{fmtPct(ps.today?.accuracy)}</strong></div>
                <div>用时：{fmtDur(safeNum(ps.today?.duration_minutes) * 60)}</div>
              </div>
            </div>
            <div className="learning-stat-card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8, color: "#1e293b" }}>本周练习</div>
              <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.8 }}>
                <div>练习次数：{safeNum(ps.week?.sessions)} 次</div>
                <div>完成题数：{safeNum(ps.week?.questions)} 题 / 正确 {safeNum(ps.week?.correct)} 题</div>
                <div>正确率：<strong>{fmtPct(ps.week?.accuracy)}</strong></div>
                <div>用时：{fmtDur(safeNum(ps.week?.duration_minutes) * 60)}</div>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* ── Task Summary ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 12px" }}>任务贡献</h3>
        <div className="learning-stats-grid">
          <div className="learning-stat-card"><div className="learning-stat-label">今日完成任务</div><div className="learning-stat-value">{safeNum(ts.today_completed)}</div></div>
          <div className="learning-stat-card"><div className="learning-stat-label">本周完成任务</div><div className="learning-stat-value">{safeNum(ts.week_completed)}</div></div>
          <div className="learning-stat-card"><div className="learning-stat-label">待完成任务</div><div className="learning-stat-value">{safeNum(ts.pending)}</div></div>
          <div className="learning-stat-card"><div className="learning-stat-label" style={{ color: safeNum(ts.overdue) > 0 ? "#dc2626" : undefined }}>逾期任务</div><div className="learning-stat-value" style={{ color: safeNum(ts.overdue) > 0 ? "#dc2626" : undefined }}>{safeNum(ts.overdue)}</div></div>
        </div>
        {safeNum(ts.overdue) > 0 && <p style={{ marginTop: 8, color: "#dc2626", fontSize: 13 }}>有 {safeNum(ts.overdue)} 个任务已逾期，建议优先处理。</p>}
      </section>

      {/* ── Weak Points ── */}
      {data.weak_points && data.weak_points.length > 0 ? (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>薄弱知识点</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {(data.weak_points || []).map((wp, idx) => (
              <div key={idx} style={{ padding: 12, borderRadius: 10, background: "#fef2f2", border: "1px solid #fecaca" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontWeight: 600, fontSize: 15 }}>{wp.title || "未知知识点"}</span>
                  <span style={{ fontSize: 13, color: "#6b7280" }}>{getSubjectLabel ? getSubjectLabel(wp.course_id) : wp.course_name || ""}</span>
                </div>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, color: "#4b5563" }}>
                  <span>掌握度：<strong style={{ color: wp.mastery_score > 30 ? "#ea580c" : "#dc2626" }}>{safeNum(wp.mastery_score)}%</strong></span>
                  {wp.recent_accuracy != null && <span>最近正确率：<strong>{fmtPct(wp.recent_accuracy)}</strong></span>}
                  {wp.practice_count > 0 && <span>练习次数：{wp.practice_count}</span>}
                  {wp.reason && <span style={{ color: "#991b1b" }}>{wp.reason}</span>}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <section className="dashboard-card">
          <h3 style={{ margin: "0 0 12px" }}>薄弱知识点</h3>
          <p style={{ color: "#6b7280", fontSize: 14 }}>暂无明显薄弱知识点。完成更多练习后，这里会根据掌握度自动分析。</p>
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
                  {safeNum(cs.practice_questions) > 0 && <div style={{ color: "#059669" }}>本周练习：{cs.practice_questions} 题 · 正确率 {fmtPct(cs.practice_accuracy)} · {safeNum(cs.study_minutes)} 分钟</div>}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Recommendations ── */}
      <section className="dashboard-card">
        <h3 style={{ margin: "0 0 12px" }}>推荐下一步</h3>
        {data.recommendations && data.recommendations.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14, color: "#374151", lineHeight: 1.8 }}>
            {data.recommendations.map((rec, idx) => (
              <li key={idx}>{typeof rec === "string" ? rec : (rec.title ? <><strong>{rec.title}</strong> — {rec.description}</> : JSON.stringify(rec))}</li>
            ))}
          </ul>
        ) : (
          <p style={{ color: "#6b7280", fontSize: 14 }}>暂无新的学习建议。完成练习或任务后，这里会自动生成建议。</p>
        )}
      </section>
    </div>
  );
}
