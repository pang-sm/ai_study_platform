import { useState } from "react";

const PACKAGE_OPTIONS = [
  { key: "free", label: "免费模式", desc: "基础功能，适合体验课程学习", features: ["课程资料管理", "AI 问答（基础额度）", "知识脉络"] },
  { key: "monthly", label: "月度包", desc: "按月订阅，灵活使用", features: ["全部免费功能", "更高 AI 额度", "学习计划", "练习中心", "学习报告"] },
  { key: "quarterly", label: "季度包", desc: "季度强化，性价比之选", features: ["全部月度功能", "更高额度上限", "错题复盘", "优先支持"] },
  { key: "full", label: "全程包", desc: "一价全包，畅享所有功能", features: ["全部功能无限制", "最高 AI 额度", "资料无限上传", "专属客服"] },
];

export default function CourseLearningRegistration({ user, setPage, API_BASE }) {
  const [selectedPlan, setSelectedPlan] = useState("free");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const username = user?.username || "";
  const displayName = user?.nickname || user?.username || "同学";

  const handleRegister = async () => {
    if (!username) {
      setError("请先登录后再注册课程学习");
      return;
    }
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const res = await fetch(`${API_BASE}/course-learning/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          plan: selectedPlan,
          service_key: "course_learning",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `注册失败 (HTTP ${res.status})`);

      setSuccess("课程学习空间已开通！");
      // Navigate to course learning profile after a short delay
      setTimeout(() => {
        if (setPage) setPage("courseProfile");
      }, 1200);
    } catch (err) {
      setError(err.message || "注册失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ep-page-wrap">
      <div className="ep-shell">
        <div className="ep-header">
          <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("home")}>← 返回主页</button>
          <h1 className="ep-title">📚 开通课程学习空间</h1>
        </div>

        {error && <div className="admin-dashboard-error" style={{ marginBottom: 16 }}>{error}</div>}
        {success && <div className="admin-dashboard-success" style={{ marginBottom: 16 }}>{success}</div>}

        {/* Welcome card */}
        <div className="ep-card" style={{ marginBottom: 20 }}>
          <div className="ep-card-head"><h2>欢迎，{displayName}！</h2></div>
          <div style={{ color: "#4b5563", fontSize: 15, lineHeight: 1.7 }}>
            <p>课程学习空间帮助你管理平日大学课程的学习资料、AI 问答、知识脉络和练习。</p>
            <p>开通后可享受以下功能：</p>
            <ul style={{ paddingLeft: 20, marginTop: 8 }}>
              <li>📁 上传和管理课程资料（课件、笔记、习题等）</li>
              <li>💬 围绕课程资料进行 AI 问答</li>
              <li>⌘ 建立课程知识脉络</li>
              <li>▤ 制定和执行学习计划</li>
              <li>✎ 练习中心和错题整理</li>
              <li>▧ 生成学习报告</li>
            </ul>
          </div>
        </div>

        {/* Plan selection */}
        <div className="ep-card">
          <div className="ep-card-head"><h2>选择套餐</h2></div>
          <div className="ep-plan-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginTop: 12 }}>
            {PACKAGE_OPTIONS.map((pkg) => (
              <button
                key={pkg.key}
                type="button"
                onClick={() => setSelectedPlan(pkg.key)}
                style={{
                  padding: 16,
                  border: selectedPlan === pkg.key ? "2px solid #7c3aed" : "1px solid #e5e7eb",
                  borderRadius: 12,
                  background: selectedPlan === pkg.key ? "#f5f3ff" : "#fff",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.2s",
                }}
              >
                <strong style={{ display: "block", fontSize: 16, marginBottom: 4, color: "#1f2937" }}>{pkg.label}</strong>
                <span style={{ display: "block", fontSize: 13, color: "#6b7280", marginBottom: 8 }}>{pkg.desc}</span>
                <ul style={{ paddingLeft: 16, margin: 0, fontSize: 12, color: "#4b5563" }}>
                  {pkg.features.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </button>
            ))}
          </div>
        </div>

        {/* Action */}
        <div style={{ marginTop: 20, display: "flex", justifyContent: "center" }}>
          <button
            type="button"
            onClick={handleRegister}
            disabled={loading}
            style={{
              padding: "12px 48px",
              fontSize: 16,
              fontWeight: 700,
              borderRadius: 999,
              border: "none",
              background: loading ? "#d1d5db" : "linear-gradient(135deg, #8b5cf6, #6d28d9)",
              color: "#fff",
              cursor: loading ? "not-allowed" : "pointer",
              boxShadow: "0 4px 14px rgba(124,58,237,0.3)",
            }}
          >
            {loading ? "开通中..." : `开通课程学习空间 · ${PACKAGE_OPTIONS.find((p) => p.key === selectedPlan)?.label || "免费模式"}`}
          </button>
        </div>

        <p className="ep-footer" style={{ marginTop: 24 }}>开通即表示同意服务条款。如有疑问，请联系<span className="ep-footer-link">客服支持</span></p>
      </div>
    </div>
  );
}
