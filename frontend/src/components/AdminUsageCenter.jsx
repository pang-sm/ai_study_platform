import { useEffect, useState } from "react";

const API_BASE = "/api";

const FEATURE_LABELS = {
  chat: "AI 问答",
  code_analyze: "代码分析",
  challenge_generate: "编程题生成",
  learning_diagnosis: "学习诊断",
  knowledge_generate: "知识点生成",
  learning_plan_generate: "学习计划生成",
  material_link_recommend: "资料关联推荐",
  question_generate: "题目生成",
  question_feedback: "题目反馈",
};

const PLAN_NAMES = {
  free: "免费版",
  pro: "专业版",
  admin: "管理员",
};

export default function AdminUsageCenter({ user }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [planForm, setPlanForm] = useState({ username: "", plan: "free" });
  const [planMsg, setPlanMsg] = useState("");

  const fetchSummary = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(
        `${API_BASE}/admin/usage-summary?admin_username=${encodeURIComponent(user.username)}`
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "加载失败");
      }
      const data = await res.json();
      setSummary(data);
    } catch (e) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, [user.username]);

  const handlePlanUpdate = async () => {
    setPlanMsg("");
    const target = planForm.username.trim();
    if (!target) {
      setPlanMsg("请输入目标用户名");
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/admin/users/${encodeURIComponent(target)}/plan`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            admin_username: user.username,
            plan: planForm.plan,
          }),
        }
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "修改失败");
      }
      setPlanMsg(`已为 ${data.username} 设置套餐：${PLAN_NAMES[data.plan] || data.plan}`);
      fetchSummary();
    } catch (e) {
      setPlanMsg(e.message || "修改失败");
    }
  };

  if (loading) {
    return <div className="empty-state">加载中...</div>;
  }

  if (error) {
    return (
      <div className="empty-state">
        <p>{error}</p>
        <button className="primary-button" onClick={fetchSummary}>重试</button>
      </div>
    );
  }

  if (!summary) return null;

  return (
    <div className="admin-usage-center">
      <section className="quota-section">
        <h3>今日总览</h3>
        <div className="admin-overview-cards">
          <div className="admin-overview-card">
            <div className="admin-overview-value">{summary.today_total}</div>
            <div className="admin-overview-label">今日 AI 调用</div>
          </div>
          <div className="admin-overview-card">
            <div className="admin-overview-value">{summary.plan_counts?.free || 0}</div>
            <div className="admin-overview-label">免费用户</div>
          </div>
          <div className="admin-overview-card">
            <div className="admin-overview-value">{summary.plan_counts?.pro || 0}</div>
            <div className="admin-overview-label">专业版用户</div>
          </div>
          <div className="admin-overview-card">
            <div className="admin-overview-value">{summary.plan_counts?.admin || 0}</div>
            <div className="admin-overview-label">管理员</div>
          </div>
        </div>
      </section>

      <section className="quota-section">
        <h3>今日功能用量</h3>
        <div className="quota-grid">
          {Object.entries(summary.feature_stats || {}).map(([feature, count]) => (
            <div key={feature} className="quota-item">
              <div className="quota-item-header">
                <span className="quota-item-label">{FEATURE_LABELS[feature] || feature}</span>
                <span className="quota-item-count">{count}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="quota-section">
        <h3>修改用户套餐</h3>
        <div className="admin-plan-form">
          <input
            className="field"
            placeholder="目标用户名"
            value={planForm.username}
            onChange={(e) => setPlanForm((p) => ({ ...p, username: e.target.value }))}
          />
          <select
            className="field"
            value={planForm.plan}
            onChange={(e) => setPlanForm((p) => ({ ...p, plan: e.target.value }))}
          >
            <option value="free">免费版</option>
            <option value="pro">专业版</option>
            <option value="admin">管理员</option>
          </select>
          <button className="primary-button" onClick={handlePlanUpdate}>确认修改</button>
        </div>
        {planMsg && <p className="admin-plan-msg">{planMsg}</p>}
      </section>

      <section className="quota-section">
        <h3>最近使用记录</h3>
        <div className="admin-log-table-wrapper">
          <table className="admin-log-table">
            <thead>
              <tr>
                <th>用户</th>
                <th>功能</th>
                <th>模型</th>
                <th>估算 Tokens</th>
                <th>状态</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {(summary.recent_logs || []).map((log, i) => (
                <tr key={i}>
                  <td>{log.username}</td>
                  <td>{FEATURE_LABELS[log.feature] || log.feature}</td>
                  <td>{log.model || "-"}</td>
                  <td>{log.estimated_tokens || 0}</td>
                  <td>{log.status === "success" ? "成功" : log.status}</td>
                  <td>{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
                </tr>
              ))}
              {(summary.recent_logs || []).length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>
                    暂无记录
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="quota-refresh">
        <button className="ghost-button" onClick={fetchSummary}>刷新</button>
      </div>
    </div>
  );
}
