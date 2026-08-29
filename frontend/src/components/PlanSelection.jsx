import "./PlanSelection.css";

const QUOTA_LABELS = {
  ai_chat_daily_limit: "AI 问答",
  ai_question_daily_limit: "AI 出题",
  material_upload_limit_mb: "资料上传",
  learning_plan: "学习计划",
  learning_report: "学习报告",
  problem_records: "题目记录",
  file_library: "文件库",
};

function formatPeriod(days) {
  if (days === 365) return "/ 年";
  if (days === 90) return "/ 季度";
  if (days === 30) return "/ 月";
  return "";
}

function formatQuota(key, value) {
  if (typeof value === "boolean") return value ? "已包含" : "未包含";
  if (key === "material_upload_limit_mb") {
    const amount = Number(value || 0);
    return amount >= 1024 ? `${amount / 1024} GB` : `${amount} MB`;
  }
  return `${value ?? 0} 次/天`;
}

function getFeatures(plan) {
  return Object.entries(plan.quota || {})
    .filter(([key]) => QUOTA_LABELS[key])
    .map(([key, value]) => ({
      key,
      label: QUOTA_LABELS[key],
      value: formatQuota(key, value),
      enabled: typeof value === "boolean" ? value : true,
    }));
}

export default function PlanSelection({
  plans = [],
  mode = "onboarding",
  selectedPlan,
  currentPlanCode = "",
  recommendedPlanCode = "",
  busyPlan = "",
  saving = false,
  onSelect,
  onConfirm,
}) {
  const currentRank = Number(plans.find((plan) => plan.plan_code === currentPlanCode)?.rank || 0);

  return (
    <div className={`plan-selection plan-selection--${mode}`}>
      <div className="plan-selection-grid">
        {plans.map((plan) => {
          const isCurrent = mode === "membership" && plan.plan_code === currentPlanCode;
          const isLower = mode === "membership" && !isCurrent && Number(plan.rank || 0) <= currentRank;
          const isRecommended = plan.plan_code === recommendedPlanCode;
          const disabled = Boolean(saving || busyPlan || isCurrent || isLower);
          const actionLabel = mode === "membership"
            ? (isCurrent ? "当前方案" : isLower ? "不可降级" : "前往结算")
            : (Number(plan.price_cents || 0) > 0 ? "前往结算" : "免费体验");

          return (
            <article
              key={plan.plan_code}
              className={`plan-selection-card${plan.plan_code === selectedPlan ? " is-selected" : ""}${isCurrent ? " is-current" : ""}${isRecommended ? " is-recommended" : ""}`}
              onClick={() => onSelect?.(plan.plan_code)}
            >
              {isRecommended && <span className="plan-selection-badge">推荐</span>}
              {isCurrent && <span className="plan-selection-badge plan-selection-badge-current">当前方案</span>}
              <div className="plan-selection-name">{plan.name}</div>
              <div className="plan-selection-price">
                {Number(plan.price_cents || 0) > 0 ? <><strong>¥{Number(plan.price_yuan || 0).toFixed(0)}</strong><span>{formatPeriod(plan.duration_days)}</span></> : <strong className="plan-selection-free">免费</strong>}
              </div>
              <ul className="plan-selection-features">
                {getFeatures(plan).map((feature) => (
                  <li key={feature.key} className={feature.enabled ? "" : "is-disabled"}>
                    <span aria-hidden="true">{feature.enabled ? "✓" : "—"}</span>
                    <span>{feature.label}：{feature.value}</span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={`plan-selection-button ${disabled ? "is-muted" : "is-primary"}`}
                disabled={disabled}
                onClick={(event) => {
                  event.stopPropagation();
                  onConfirm?.(plan);
                }}
              >
                {busyPlan === plan.plan_code ? "正在创建订单…" : actionLabel}
              </button>
            </article>
          );
        })}
      </div>
    </div>
  );
}
