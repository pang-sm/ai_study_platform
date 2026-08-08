import { useEffect, useState } from "react";
import "./ProgrammingOnboarding.css";

function PlanIcon({ type }) {
  if (type === "code") {
    return <svg viewBox="0 0 24 24"><path d="M8 9 5 12l3 3M16 9l3 3-3 3M14 6l-4 12" /></svg>;
  }
  if (type === "trophy") {
    return <svg viewBox="0 0 24 24"><path d="M8 4h8v4a4 4 0 0 1-8 0V4ZM6 5H4v2a4 4 0 0 0 4 4M18 5h2v2a4 4 0 0 1-4 4M12 12v5M8 21h8M10 17h4" /></svg>;
  }
  if (type === "cap") {
    return <svg viewBox="0 0 24 24"><path d="m3 8 9-5 9 5-9 5-9-5ZM7 11v5c3 2 7 2 10 0v-5" /></svg>;
  }
  return <svg viewBox="0 0 24 24"><path d="M20 7H4v14h16V7ZM12 7v14M4 12h16M8 7a2.5 2.5 0 1 1 4 0M16 7a2.5 2.5 0 1 0-4 0" /></svg>;
}

function formatBenefit(benefit) {
  if (!benefit) return null;
  if (benefit.key === "chat") {
    return { text: `AI问答/纠错：${benefit.limit}${benefit.unit}`, enabled: benefit.enabled };
  }
  if (benefit.key === "question_generate") {
    return { text: `AI出题次数：${benefit.limit}${benefit.unit}`, enabled: benefit.enabled };
  }
  if (benefit.key === "file_library") {
    return { text: "文件库", enabled: benefit.enabled };
  }
  if (benefit.key === "problem_records") {
    return { text: "题目记录", enabled: benefit.enabled };
  }
  return { text: benefit.label, enabled: benefit.enabled };
}

function normalizePackage(plan) {
  const rank = Number(plan.rank || 0);
  const duration = plan.duration_days === 365 ? "/ 年" : plan.duration_days === 90 ? "/ 季度" : plan.duration_days === 30 ? "/ 月" : "";
  const benefits = (plan.benefits || []).map(formatBenefit).filter(Boolean);
  const quotaBenefits = Object.entries(plan.quota || {}).map(([key, value]) => ({
    key,
    label: key === "ai_chat_daily_limit" ? "AI 问答" : key === "ai_question_daily_limit" ? "AI 出题" : key === "problem_records" ? "题目记录" : key === "file_library" ? "文件库" : key,
    limit: typeof value === "number" ? value : null,
    unit: key.endsWith("_limit") ? "次/天" : "",
    enabled: typeof value === "boolean" ? value : true,
  })).map(formatBenefit).filter(Boolean);
  return {
    key: plan.plan_code,
    title: plan.name,
    subtitle: rank === 0 ? "基础体验" : rank === 1 ? "日常练习" : rank === 2 ? "能力提升" : "进阶强化",
    price: (Number(plan.price_cents || 0) / 100).toFixed(2),
    period: duration,
    icon: rank === 0 ? "gift" : rank === 1 ? "code" : rank === 2 ? "trophy" : "cap",
    btnLabel: rank === 0 ? "免费体验" : "前往结算",
    recommended: rank === 2,
    benefits: [...benefits, ...quotaBenefits],
  };
}

export default function ProgrammingPackageStep({
  user,
  apiBase = "/api",
  initialPlan = "quarterly",
  initialDetails,
  onBack,
  onComplete,
}) {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan || "quarterly");
  const [plans, setPlans] = useState([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase}/membership/catalog?service_key=programming`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive || !Array.isArray(data?.plans)) throw new Error("套餐目录加载失败");
        setPlans(data.plans.map(normalizePackage));
      })
      .catch(() => alive && setMessage("套餐目录加载失败，请稍后重试。"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [apiBase]);

  const completeWithPlan = async (plan = selectedPlan) => {
    setSelectedPlan(plan);
    setMessage("");
    setSaving(true);
    try {
      await onComplete?.(plan);
    } catch (error) {
      setMessage(error.message || "套餐保存失败，请稍后再试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="programming-onboarding-page">
      <section className="programming-package-card" aria-label="选择你的编程套餐">
        <div className="programming-onboarding-header programming-package-header">
          <span>第 3 步</span>
          <h1>选择你的编程套餐</h1>
          <p>根据你的学习方向，为你推荐更适合编程能力提升的使用方案</p>
        </div>

        <div className="programming-package-grid">
          {loading && <div className="programming-onboarding-error">套餐目录加载中，请稍后。</div>}
          {plans.map((pkg) => (
            <article
              key={pkg.key}
              className={`programming-plan-card${selectedPlan === pkg.key ? " is-selected" : ""}${pkg.recommended ? " is-recommended" : ""}`}
              onClick={() => { setSelectedPlan(pkg.key); setMessage(""); }}
            >
              {pkg.recommended && <div className="programming-plan-badge">★ 推荐</div>}
              <div className="programming-plan-icon"><PlanIcon type={pkg.icon} /></div>
              <h2>{pkg.title}</h2>
              <span className="programming-plan-subtitle">{pkg.subtitle}</span>
              <div className="programming-plan-price">
                <span>¥</span>
                <strong>{pkg.price}</strong>
                {pkg.period && <em>{pkg.period}</em>}
              </div>
              <ul>
                {pkg.benefits.map((benefit) => (
                  <li key={benefit.text} className={benefit.enabled ? "" : "is-disabled"}>
                    <span>{benefit.enabled ? "✓" : "!"}</span>
                    {benefit.text}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={pkg.recommended ? "programming-btn-primary" : "programming-btn-outline"}
                disabled={saving}
                onClick={(event) => {
                  event.stopPropagation();
                  completeWithPlan(pkg.key);
                }}
              >
                {saving && selectedPlan === pkg.key ? "保存中..." : pkg.btnLabel}
              </button>
            </article>
          ))}
        </div>

        {message && <div className="programming-onboarding-error">{message}</div>}

        <div className="programming-onboarding-actions">
          <button type="button" className="programming-btn-secondary" onClick={onBack} disabled={saving}>上一步</button>
          <button type="button" className="programming-btn-primary" onClick={() => completeWithPlan()} disabled={saving}>
            {saving ? "保存中..." : "继续"}
          </button>
        </div>
      </section>
    </div>
  );
}
