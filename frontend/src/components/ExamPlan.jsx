import { useEffect, useState } from "react";

const PACKAGES = [
  { key: "free", name: "免费模式", price: "0", period: "", desc: "基础体验", icon: "🎓", permissions: { ai_chat_daily_limit: 50, ai_question_daily_limit: 5, material_upload_limit_mb: 100, learning_plan: false, mistake_review: false, learning_report: false } },
  { key: "monthly_sprint", name: "月度冲刺包", price: "29", period: "/ 月", desc: "短期提升", icon: "🚀", permissions: { ai_chat_daily_limit: 300, ai_question_daily_limit: 30, material_upload_limit_mb: 500, learning_plan: true, mistake_review: true, learning_report: true } },
  { key: "quarterly_boost", name: "季度强化包", price: "79", period: "/ 季度", desc: "学习更稳", icon: "⭐", recommended: true, permissions: { ai_chat_daily_limit: 500, ai_question_daily_limit: 50, material_upload_limit_mb: 1024, learning_plan: true, mistake_review: true, learning_report: true } },
  { key: "full_exam", name: "全程考包", price: "149", period: "/ 年", desc: "长期备考", icon: "🏆", permissions: { ai_chat_daily_limit: 1000, ai_question_daily_limit: 100, material_upload_limit_mb: 2048, learning_plan: true, mistake_review: true, learning_report: true } },
];

const TIER_ORDER = ["free", "monthly_sprint", "quarterly_boost", "full_exam"];

function formatUploadLimit(mb) {
  return Number(mb) >= 1024 ? `${Number(mb) / 1024}GB` : `${mb}MB`;
}

function featuresFromPermissions(permissions) {
  return [
    { label: `AI 问答 ${permissions.ai_chat_daily_limit} 次 / 每天`, ok: true },
    { label: `AI 出题 ${permissions.ai_question_daily_limit} 次 / 每天`, ok: true },
    { label: `资料上传限制 ${formatUploadLimit(permissions.material_upload_limit_mb)}`, ok: true },
    { label: "学习计划", ok: Boolean(permissions.learning_plan) },
    { label: "错题复盘", ok: Boolean(permissions.mistake_review) },
    { label: "学习报告", ok: Boolean(permissions.learning_report) },
  ];
}

export default function ExamPlan({ user, setPage, API_BASE }) {
  const [currentPkg, setCurrentPkg] = useState("free");
  const [currentTrack, setCurrentTrack] = useState(null);
  const [loading, setLoading] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // Fetch real package from tracks API — not from stale prop
  const fetchPackage = async () => {
    try {
      const res = await fetch(`${API_BASE}/me/tracks?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      const tracks = data.tracks || [];
      const examTrack = tracks.find((t) => t.track_type === "exam_408");
      if (examTrack) {
        setCurrentTrack(examTrack);
        if (examTrack.package_type) setCurrentPkg(examTrack.package_type);
      }
    } catch { /* keep default */ }
  };
  useEffect(() => { fetchPackage(); }, []);

  const currentIdx = TIER_ORDER.indexOf(currentPkg);

  const handleUpgrade = async (pkgKey) => {
    const targetIdx = TIER_ORDER.indexOf(pkgKey);
    if (targetIdx <= currentIdx) {
      setErr("当前已是该套餐或更高等级，无需升级");
      return;
    }
    setLoading(pkgKey);
    setErr(""); setMsg("");
    try {
      const res = await fetch(`${API_BASE}/me/tracks/exam_408/package`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, package_type: pkgKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "升级失败");
      const nextTrack = data.track || null;
      setCurrentTrack(nextTrack);
      setCurrentPkg(nextTrack?.package_type || pkgKey);
      setMsg(data.message || "套餐已更新");
      setTimeout(() => setMsg(""), 3000);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading("");
    }
  };

  return (
    <div className="ep-page-wrap">
      <div className="ep-shell">
        <div className="ep-header">
          <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("examProfile")}>← 返回个人中心</button>
          <h1 className="ep-title">套餐详情</h1>
        </div>

        {msg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{msg}</div>}
        {err && <div className="admin-dashboard-error" style={{ marginBottom: 12 }}>{err}</div>}

        <div className="ep-card">
          <div className="ob-packages">
            {PACKAGES.map((pkg) => {
              const pkgIdx = TIER_ORDER.indexOf(pkg.key);
              const isCurrent = pkg.key === currentPkg;
              const canUpgrade = pkgIdx > currentIdx;
              const isLower = pkgIdx < currentIdx;

              return (
                <div
                  key={pkg.key}
                  className={`ob-package-card${isCurrent ? " active" : ""}${pkg.recommended && !isCurrent ? " recommended" : ""}`}
                >
                  {pkg.recommended && !isCurrent && <span className="ob-package-badge">推荐</span>}
                  {isCurrent && <span className="ob-package-badge" style={{ background: "linear-gradient(135deg, #059669, #10b981)" }}>当前套餐</span>}
                  <div className="ob-package-icon">{pkg.icon}</div>
                  <h3 className="ob-package-title">{pkg.name}</h3>
                  <p className="ob-package-subtitle">{pkg.desc}</p>
                  <div className="ob-package-price">
                    <span className="ob-package-currency">￥</span>
                    <span className="ob-package-amount">{pkg.price}</span>
                    {pkg.period && <span className="ob-package-period">{pkg.period}</span>}
                  </div>
                  <ul className="ob-package-features">
                    {featuresFromPermissions(pkg.key === currentPkg && currentTrack?.permissions ? currentTrack.permissions : pkg.permissions).map((f, i) => (
                      <li key={i} className={f.ok ? "ob-package-feature" : "ob-package-feature ob-package-feature--unavail"}>
                        <span className="ob-package-check">{f.ok ? "✓" : "✕"}</span> {f.label}
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    className={isCurrent ? "ob-btn-secondary" : canUpgrade ? "ob-btn-primary" : "ob-btn-secondary"}
                    disabled={isLower || loading === pkg.key}
                    onClick={() => canUpgrade ? handleUpgrade(pkg.key) : (isLower ? setErr("当前已是该套餐或更高等级") : null)}
                    style={{ opacity: isLower ? 0.4 : 1 }}
                  >
                    {loading === pkg.key ? "升级中..." : isCurrent ? "当前套餐" : isLower ? "不可用" : "立即升级"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
