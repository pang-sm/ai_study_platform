import { useState } from "react";

const COURSE_PACKAGES = [
  {
    key: "free",
    title: "免费模式",
    subtitle: "基础体验",
    price: "0",
    period: "",
    icon: "◇",
    btnLabel: "免费体验",
    features: [
      "适合新用户体验",
      "AI 问答次数：20 次 / 每天",
      "AI 出题次数：5 次 / 每天",
      "资料上传限制：50MB",
      "学习计划",
      "错题复盘",
      "学习报告",
    ],
  },
  {
    key: "monthly",
    title: "月课程包",
    subtitle: "短期提升",
    price: "29",
    period: "/ 月",
    icon: "◆",
    btnLabel: "去支付",
    features: [
      "适合短期课程冲刺",
      "AI 问答次数：200 次 / 每天",
      "AI 出题次数：50 次 / 每天",
      "资料上传限制：200MB",
      "学习计划",
      "错题复盘",
      "学习报告",
      "课程资料支持",
    ],
  },
  {
    key: "quarterly",
    title: "季度课程包",
    subtitle: "深度学习",
    price: "79",
    period: "/ 季度",
    icon: "★",
    btnLabel: "去支付",
    recommended: true,
    features: [
      "适合阶段性系统学习",
      "AI 问答次数：500 次 / 每天",
      "AI 出题次数：100 次 / 每天",
      "资料上传限制：500MB",
      "学习计划",
      "错题复盘",
      "学习报告",
      "课程资料支持",
    ],
  },
  {
    key: "full",
    title: "全程课程包",
    subtitle: "长期陪伴",
    price: "149",
    period: "/ 年",
    icon: "✦",
    btnLabel: "去支付",
    features: [
      "适合长期课程陪伴",
      "AI 问答次数：不限次数",
      "AI 出题次数：不限次数",
      "资料上传限制：1GB",
      "学习计划",
      "错题复盘",
      "学习报告",
      "课程资料支持",
    ],
  },
];

export default function CourseLearningPackageStep({
  initialPlan = "quarterly",
  saving = false,
  error = "",
  onBack,
  onComplete,
}) {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan || "quarterly");

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
          {COURSE_PACKAGES.map((pkg) => (
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
