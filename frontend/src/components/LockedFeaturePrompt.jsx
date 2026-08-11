import "./LockedFeaturePrompt.css";

const FEATURE_LABELS = {
  learning_plan: "学习计划",
  practice_review: "练习复盘",
  learning_report: "学习报告",
};

const PLAN_LABELS = {
  free: "免费模式",
  monthly: "月度学习包",
  monthly_sprint: "月度冲刺包",
  quarterly: "季度学习包",
  quarterly_sprint: "季度冲刺包",
  full: "全程学习包",
  full_sprint: "全程冲刺包",
};

export function featureLabel(feature) {
  return FEATURE_LABELS[feature] || "高级功能";
}

function planLabel(plan) {
  return PLAN_LABELS[plan] || plan || "免费模式";
}

export function LockedFeatureView({ entitlement, onViewMembership }) {
  return (
    <section className="locked-feature-view" role="status">
      <span className="locked-feature-view__icon" aria-hidden="true">🔒</span>
      <h2>{featureLabel(entitlement?.feature)}</h2>
      <p>当前套餐为{planLabel(entitlement?.current_plan)}，升级至{planLabel(entitlement?.required_plan)}及以上即可使用。</p>
      <button type="button" onClick={onViewMembership}>查看套餐</button>
    </section>
  );
}

export default function LockedFeaturePrompt({ entitlement, onClose, onViewMembership }) {
  if (!entitlement) return null;
  return (
    <div className="locked-feature-prompt" role="presentation" onMouseDown={onClose}>
      <section className="locked-feature-prompt__dialog" role="dialog" aria-modal="true" aria-labelledby="locked-feature-title" onMouseDown={(event) => event.stopPropagation()}>
        <button className="locked-feature-prompt__close" type="button" onClick={onClose} aria-label="关闭">×</button>
        <span className="locked-feature-prompt__icon" aria-hidden="true">🔒</span>
        <h2 id="locked-feature-title">{featureLabel(entitlement.feature)}</h2>
        <p>该功能需要升级后使用。</p>
        <dl>
          <div><dt>当前套餐</dt><dd>{planLabel(entitlement.current_plan)}</dd></div>
          <div><dt>最低所需</dt><dd>{planLabel(entitlement.required_plan)}及以上</dd></div>
        </dl>
        <button className="locked-feature-prompt__primary" type="button" onClick={onViewMembership}>查看套餐</button>
      </section>
    </div>
  );
}
