import { useEffect, useState } from "react";

function formatBenefit(benefit) {
  if (!benefit) return "";
  const prefix = benefit.enabled === false ? "未解锁：" : "";
  if (benefit.limit === null || benefit.limit === undefined || benefit.limit === "") {
    return `${prefix}${benefit.label}`;
  }
  return `${prefix}${benefit.label}：${benefit.limit}${benefit.unit ? ` ${benefit.unit}` : ""}`;
}

function normalizePackage(plan) {
  const rank = Number(plan.rank || 0);
  const duration = plan.duration_days === 365 ? "/ 年" : plan.duration_days === 90 ? "/ 季度" : plan.duration_days === 30 ? "/ 月" : "";
  return {
    key: plan.plan_code,
    title: plan.name,
    subtitle: rank === 0 ? "基础体验" : rank === 1 ? "短期提升" : rank === 2 ? "深度学习" : "长期陪伴",
    price: (Number(plan.price_cents || 0) / 100).toFixed(2),
    period: duration,
    icon: rank === 0 ? "◇" : rank === 1 ? "◆" : rank === 2 ? "★" : "✦",
    btnLabel: rank === 0 ? "免费体验" : "前往结算",
    recommended: rank === 2,
    features: Object.entries(plan.quota || {}).map(([key, value]) => ({
      label: key === "ai_chat_daily_limit" ? "AI 问答" : key === "ai_question_daily_limit" ? "AI 出题" : key === "material_upload_limit_mb" ? "资料上传" : key === "learning_plan" ? "学习计划" : key === "mistake_review" ? "练习复盘" : key === "learning_report" ? "学习报告" : key,
      limit: typeof value === "number" ? value : null,
      unit: key.endsWith("_limit") ? "次/天" : "",
      enabled: typeof value === "boolean" ? value : true,
    })).map(formatBenefit).filter(Boolean),
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
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let alive = true;
    fetch("/api/membership/catalog?service_key=course_learning", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive) return;
        if (!Array.isArray(data?.plans)) throw new Error("套餐目录加载失败");
        const next = data.plans.map(normalizePackage);
        setPackages(next);
      })
      .catch(() => {
        if (alive) setLoadError("套餐目录加载失败，请稍后重试。");
      })
      .finally(() => alive && setLoading(false));
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
          {loading && <div className="ob-error">课程学习套餐加载中，请稍候。</div>}
          {!loading && loadError && (
            <div className="ob-error">{loadError}</div>
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
