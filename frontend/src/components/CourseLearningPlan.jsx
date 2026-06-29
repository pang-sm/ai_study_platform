import { useEffect, useState } from "react";

const PACKAGES = [
  { key: "free", name: "免费模式", price: "0", period: "", desc: "基础体验", icon: "◇" },
  { key: "monthly", name: "月课程包", price: "29", period: "/ 月", desc: "短期提升", icon: "◆" },
  { key: "quarterly", name: "季度课程包", price: "79", period: "/ 季度", desc: "深度学习", icon: "★", recommended: true },
  { key: "full", name: "全程课程包", price: "149", period: "/ 年", desc: "长期陪伴", icon: "✦" },
];

const TIER_ORDER = ["free", "monthly", "quarterly", "full"];

function formatUploadLimit(mb) {
  return Number(mb) >= 1024 ? `${Number(mb) / 1024}GB` : `${mb}MB`;
}

/** Derive features from either API benefits or fallback permissions */
function buildFeatures(pkg) {
  if (pkg.benefits && pkg.benefits.length > 0) {
    return pkg.benefits.map((b) => {
      const suffix = b.limit != null ? ` ${b.limit}${b.unit ? ` ${b.unit}` : ""}` : "";
      return { label: `${b.label}${suffix}`, ok: b.enabled !== false };
    });
  }
  const perms = pkg.permissions || {};
  return [
    { label: `AI 问答 ${perms.ai_chat_daily_limit ?? 50} 次 / 每天`, ok: true },
    { label: `AI 出题 ${perms.ai_question_daily_limit ?? 5} 次 / 每天`, ok: true },
    { label: `资料上传限制 ${formatUploadLimit(perms.material_upload_limit_mb ?? 100)}`, ok: true },
    { label: "学习计划", ok: Boolean(perms.learning_plan) },
    { label: "练习中心", ok: Boolean(perms.practice_center) },
    { label: "学习报告", ok: Boolean(perms.learning_report) },
  ];
}

export default function CourseLearningPlan({ user, setPage, API_BASE }) {
  const [apiPackages, setApiPackages] = useState([]);
  const [currentPkg, setCurrentPkg] = useState("free");
  const [loading, setLoading] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // Fetch available packages from API
  useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/course-learning/packages`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive) return;
        if (data?.plans && Array.isArray(data.plans)) {
          const merged = PACKAGES.map((pkg) => {
            const apiPlan = data.plans.find((p) => p.plan === pkg.key);
            return { ...pkg, permissions: apiPlan?.permissions || {}, benefits: apiPlan?.benefits || [] };
          });
          setApiPackages(merged);
        } else {
          setApiPackages(PACKAGES);
        }
      })
      .catch(() => { if (alive) setApiPackages(PACKAGES); });
    return () => { alive = false; };
  }, [API_BASE]);

  // Fetch current entitlements
  useEffect(() => {
    if (!user?.username) return;
    let alive = true;
    fetch(`${API_BASE}/course-learning/entitlements?username=${encodeURIComponent(user.username)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (alive && data?.plan) setCurrentPkg(data.plan);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [API_BASE, user?.username]);

  const currentIdx = TIER_ORDER.indexOf(currentPkg);
  const displayPackages = apiPackages.length > 0 ? apiPackages : PACKAGES;

  const handleUpgrade = async (pkgKey) => {
    const targetIdx = TIER_ORDER.indexOf(pkgKey);
    if (targetIdx <= currentIdx) {
      setErr("当前已是该套餐或更高等级课程，无需升级");
      return;
    }
    setLoading(pkgKey);
    setErr("");
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/course-learning/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${encodeURIComponent(user?.username || "")}`,
        },
        body: JSON.stringify({ plan: pkgKey, onboarding_completed: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "套餐升级失败，请稍后重试");
      setCurrentPkg(pkgKey);
      setMsg("课程学习套餐已更新");
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
          <button
            type="button"
            className="ep-outline-btn"
            onClick={() => setPage && setPage("courseProfile")}
          >
            ← 返回个人中心
          </button>
          <h1 className="ep-title">课程学习套餐详情</h1>
        </div>

        {msg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{msg}</div>}
        {err && <div className="admin-dashboard-error" style={{ marginBottom: 12 }}>{err}</div>}

        <div className="ep-card">
          <div className="ob-packages">
            {displayPackages.map((pkg) => {
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
                  {isCurrent && (
                    <span className="ob-package-badge" style={{ background: "linear-gradient(135deg, #059669, #10b981)" }}>
                      当前套餐
                    </span>
                  )}
                  <div className="ob-package-icon">{pkg.icon}</div>
                  <h3 className="ob-package-title">{pkg.name}</h3>
                  <p className="ob-package-subtitle">{pkg.desc}</p>
                  <div className="ob-package-price">
                    <span className="ob-package-currency">¥</span>
                    <span className="ob-package-amount">{pkg.price}</span>
                    {pkg.period && <span className="ob-package-period">{pkg.period}</span>}
                  </div>
                  <ul className="ob-package-features">
                    {buildFeatures(pkg).map((f, i) => (
                      <li key={i} className={f.ok ? "ob-package-feature" : "ob-package-feature ob-package-feature--unavail"}>
                        <span className="ob-package-check">{f.ok ? "✓" : "✕"}</span>{" "}
                        {f.label}
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    className={isCurrent ? "ob-btn-secondary" : canUpgrade ? "ob-btn-primary" : "ob-btn-secondary"}
                    disabled={isLower || loading === pkg.key}
                    onClick={() => canUpgrade && handleUpgrade(pkg.key)}
                    style={{ opacity: isLower ? 0.4 : 1 }}
                  >
                    {loading === pkg.key
                      ? "升级中..."
                      : isCurrent
                      ? "当前套餐"
                      : isLower
                      ? "不可用"
                      : "立即升级"}
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
