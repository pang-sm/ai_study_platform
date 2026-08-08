import { useEffect, useState } from "react";

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
  const [currentRank, setCurrentRank] = useState(0);
  const [packages, setPackages] = useState([]);
  const [err, setErr] = useState("");

  const fetchPackages = async () => {
    try {
      const res = await fetch(`${API_BASE}/membership/catalog?service_key=exam_11408`, { credentials: "include" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !Array.isArray(data.plans)) throw new Error(data.detail || "套餐目录加载失败");
      setPackages(data.plans.map((pkg) => ({
        ...pkg,
        key: pkg.plan_code,
        name: pkg.name,
        price: (Number(pkg.price_cents || 0) / 100).toString(),
        period: pkg.duration_days === 365 ? "/ 年" : pkg.duration_days === 90 ? "/ 季度" : pkg.duration_days === 30 ? "/ 月" : "",
        desc: pkg.rank === 0 ? "基础体验" : pkg.rank === 1 ? "短期冲刺" : pkg.rank === 2 ? "强化备考" : "长期备考",
        icon: pkg.rank === 0 ? "🎓" : pkg.rank === 1 ? "🚀" : pkg.rank === 2 ? "⭐" : "🏆",
        recommended: pkg.rank === 2,
      })));
      const current = data.current?.plan || "free";
      setCurrentPkg(current);
      setCurrentRank(Number(data.plans.find((pkg) => pkg.plan_code === current)?.rank || 0));
    } catch (error) { setErr(error.message || "套餐目录加载失败，请稍后重试"); }
  };
  useEffect(() => { fetchPackages(); }, [API_BASE]);

  const handleUpgrade = (pkgKey) => {
    const target = packages.find((pkg) => pkg.key === pkgKey);
    if (!target || Number(target.rank) <= currentRank) {
      setErr("当前已是该套餐或更高等级，无需升级");
      return;
    }
    setErr("");
    setPage?.("membershipCheckout", { serviceKey: "exam_11408", planCode: pkgKey, profilePage: "examProfile" });
  };

  return (
    <div className="ep-page-wrap">
      <div className="ep-shell">
        <div className="ep-header">
          <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("examProfile")}>← 返回个人中心</button>
          <h1 className="ep-title">套餐详情</h1>
        </div>

        {err && <div className="admin-dashboard-error" style={{ marginBottom: 12 }}>{err}</div>}

        <div className="ep-card">
          <div className="ob-packages">
            {packages.map((pkg) => {
              const isCurrent = pkg.key === currentPkg;
              const canUpgrade = Number(pkg.rank) > currentRank;
              const isLower = Number(pkg.rank) < currentRank;

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
                    {featuresFromPermissions(pkg.quota || {}).map((f, i) => (
                      <li key={i} className={f.ok ? "ob-package-feature" : "ob-package-feature ob-package-feature--unavail"}>
                        <span className="ob-package-check">{f.ok ? "✓" : "✕"}</span> {f.label}
                      </li>
                    ))}
                  </ul>
                  <button
                    type="button"
                    className={isCurrent ? "ob-btn-secondary" : canUpgrade ? "ob-btn-primary" : "ob-btn-secondary"}
                    disabled={isLower}
                    onClick={() => canUpgrade ? handleUpgrade(pkg.key) : (isLower ? setErr("当前已是该套餐或更高等级") : null)}
                    style={{ opacity: isLower ? 0.4 : 1 }}
                  >
                    {isCurrent ? "当前套餐" : isLower ? "不可用" : "查看并开通"}
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
