import { useEffect, useState } from "react";

const PACKAGE_META = {
  free: { title: "免费模式", subtitle: "基础体验", price: "0", period: "", icon: "◇", btnLabel: "免费体验" },
  monthly: { title: "月课程包", subtitle: "短期提升", price: "29", period: "/ 月", icon: "◆", btnLabel: "去支付" },
  quarterly: { title: "季度课程包", subtitle: "深度学习", price: "79", period: "/ 季度", icon: "★", btnLabel: "去支付", recommended: true },
  full: { title: "全程课程包", subtitle: "长期陪伴", price: "149", period: "/ 年", icon: "✦", btnLabel: "去支付" },
};

function formatBenefit(benefit) {
  if (!benefit) return "";
  const prefix = benefit.enabled === false ? "未解锁：" : "";
  if (benefit.limit === null || benefit.limit === undefined || benefit.limit === "") {
    return `${prefix}${benefit.label}`;
  }
  return `${prefix}${benefit.label}：${benefit.limit}${benefit.unit ? ` ${benefit.unit}` : ""}`;
}

function normalizePackage(plan) {
  const meta = PACKAGE_META[plan.plan] || PACKAGE_META.free;
  return {
    key: plan.plan,
    title: plan.plan_label || meta.title,
    subtitle: meta.subtitle,
    price: meta.price,
    period: meta.period,
    icon: meta.icon,
    btnLabel: meta.btnLabel,
    recommended: meta.recommended,
    features: (plan.benefits || []).map(formatBenefit).filter(Boolean),
  };
}

export default function CourseLearningPackageStep({
  initialPlan = "quarterly",
  saving = false,
  error = "",
  onBack,
  onComplete,
}) {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan || "quarterly");
  const [packages, setPackages] = useState([]);

  useEffect(() => {
    let alive = true;
    fetch("/api/course-learning/packages")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive || !Array.isArray(data?.plans)) return;
        const next = data.plans.map(normalizePackage);
        if (next.length > 0) setPackages(next);
      })
      .catch(() => setPackages([]));
    return () => { alive = false; };
  }, []);

  const completeWithPlan = (plan = selectedPlan) => {
    if (saving) return;
    setSelectedPlan(plan);
    onComplete?.(plan);
  };

  return (
    <div className="onboarding-v2-page course-package-page">
      <div className="onboarding-v2-card course-package-card">
        <div className="ob-step2-head">
          <p className="ob-subtitle">第 3 步</p>
          <h1 className="ob-title">选择你的学习套餐</h1>
          <p className="ob-desc">根据你的学习方向，为你推荐适合大学课程学习的使用方案</p>
        </div>

        {error && <div className="ob-error">{error}</div>}

        <div className="ob-packages course-package-grid">
          {packages.length === 0 && (
            <div className="ob-error">课程学习套餐加载中，请稍候重试。</div>
          )}
          {packages.map((pkg) => (
            <div
              key={pkg.key}
              className={`ob-package-card${selectedPlan === pkg.key ? " active" : ""}${pkg.recommended ? " recommended" : ""}`}
              onClick={() => setSelectedPlan(pkg.key)}
            >
              {pkg.recommended && <span className="ob-package-badge">推荐</span>}
              <div className="ob-package-icon">{pkg.icon}</div>
              <h3 className="ob-package-title">{pkg.title}</h3>
              <p className="ob-package-subtitle">{pkg.subtitle}</p>
              <div className="ob-package-price">
                <span className="ob-package-currency">¥</span>
                <span className="ob-package-amount">{pkg.price}</span>
                {pkg.period && <span className="ob-package-period">{pkg.period}</span>}
              </div>
              <ul className="ob-package-features">
                {pkg.features.map((feature) => (
                  <li key={feature} className="ob-package-feature">
                    <span className="ob-package-check">✓</span>
                    {feature}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={selectedPlan === pkg.key ? "ob-btn-primary" : "ob-btn-secondary"}
                disabled={saving}
                onClick={(event) => {
                  event.stopPropagation();
                  completeWithPlan(pkg.key);
                }}
              >
                {saving && selectedPlan === pkg.key ? "保存中..." : pkg.btnLabel}
              </button>
            </div>
          ))}
        </div>

        <div className="ob-actions ob-actions--dual">
          <button type="button" className="ob-btn-secondary" onClick={onBack} disabled={saving}>
            上一步
          </button>
          <button type="button" className="ob-btn-primary" onClick={() => completeWithPlan()} disabled={saving}>
            {saving ? "保存中..." : "继续"}
          </button>
        </div>
      </div>
    </div>
  );
}
