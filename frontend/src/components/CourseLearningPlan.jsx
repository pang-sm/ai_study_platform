import { useEffect, useState } from "react";

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
  const perms = pkg.quota || pkg.permissions || {};
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
  const [currentRank, setCurrentRank] = useState(0);
  const [err, setErr] = useState("");

  useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/membership/catalog?service_key=course_learning`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive) return;
        if (!Array.isArray(data?.plans)) throw new Error("套餐目录加载失败");
        setApiPackages(data.plans.map((pkg) => ({
          ...pkg,
          key: pkg.plan_code,
          price: (Number(pkg.price_cents || 0) / 100).toString(),
          desc: pkg.rank === 0 ? "基础体验" : pkg.rank === 1 ? "短期提升" : pkg.rank === 2 ? "深度学习" : "长期陪伴",
          period: pkg.duration_days === 365 ? "/ 年" : pkg.duration_days === 90 ? "/ 季度" : pkg.duration_days === 30 ? "/ 月" : "",
          icon: pkg.rank === 0 ? "◇" : pkg.rank === 1 ? "◆" : pkg.rank === 2 ? "★" : "✦",
          recommended: pkg.rank === 2,
        })));
        setCurrentPkg(data.current?.plan || "free");
        setCurrentRank(Number(data.plans.find((pkg) => pkg.plan_code === data.current?.plan)?.rank || 0));
      })
      .catch(() => { if (alive) setErr("套餐目录加载失败，请稍后重试。"); });
    return () => { alive = false; };
  }, [API_BASE]);

  const displayPackages = apiPackages;

  const handleUpgrade = (pkgKey) => {
    const target = displayPackages.find((pkg) => pkg.key === pkgKey);
    if (!target || Number(target.rank) <= currentRank) {
      setErr("当前已是该套餐或更高等级课程，无需升级");
      return;
    }
    setErr("");
    setPage?.("membershipCheckout", { serviceKey: "course_learning", planCode: pkgKey, profilePage: "courseProfile" });
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

        {err && <div className="admin-dashboard-error" style={{ marginBottom: 12 }}>{err}</div>}

        <div className="ep-card">
          <div className="ob-packages">
            {displayPackages.map((pkg) => {
              const isCurrent = pkg.key === currentPkg;
              const canUpgrade = Number(pkg.rank) > currentRank;
              const isLower = Number(pkg.rank) < currentRank;

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
                    disabled={isLower}
                    onClick={() => canUpgrade && handleUpgrade(pkg.key)}
                    style={{ opacity: isLower ? 0.4 : 1 }}
                  >
                    {isCurrent
                      ? "当前套餐"
                      : isLower
                      ? "不可降级"
                      : "查看并开通"}
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
