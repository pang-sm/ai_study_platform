import { useEffect, useMemo, useState } from "react";
import "./ProgrammingOnboarding.css";

const PACKAGE_META = {
  free: { title: "免费模式", subtitle: "基础体验", price: "0", period: "", icon: "gift", btnLabel: "免费体验" },
  monthly: { title: "编程练习月卡", subtitle: "日常练习", price: "9", period: "/ 月", icon: "code", btnLabel: "去支付" },
  quarterly: { title: "编程进阶训练包", subtitle: "能力提升", price: "19", period: "/ 季度", icon: "trophy", btnLabel: "去支付", recommended: true },
  full: { title: "实验与算法强化包", subtitle: "进阶强化", price: "59", period: "/ 年", icon: "cap", btnLabel: "去支付" },
};

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
  const meta = PACKAGE_META[plan.plan] || PACKAGE_META.free;
  const benefits = (plan.benefits || []).map(formatBenefit).filter(Boolean);
  const experience = plan.plan === "free" ? "体验情况：基础编程体验" : plan.plan === "full" ? "体验情况：长期完整编程体验" : "体验情况：进阶编程体验";
  return {
    key: plan.plan,
    title: plan.plan_label || meta.title,
    subtitle: meta.subtitle,
    price: meta.price,
    period: meta.period,
    icon: meta.icon,
    btnLabel: meta.btnLabel,
    recommended: meta.recommended,
    benefits: [{ text: experience, enabled: true }, ...benefits],
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
  const [paymentAvailable, setPaymentAvailable] = useState(false);
  const [savedDetails, setSavedDetails] = useState(initialDetails || null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    setSavedDetails(initialDetails || null);
  }, [initialDetails]);

  useEffect(() => {
    if (initialDetails || !user?.username) return;
    let alive = true;
    fetch(`${apiBase}/programming/onboarding`, {
      headers: { Authorization: `Bearer ${encodeURIComponent(user.username)}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive || !data) return;
        setSavedDetails(data);
        if (data.onboarding_completed && data.plan) setSelectedPlan(data.plan);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [apiBase, initialDetails, user?.username]);

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase}/programming/packages`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive || !Array.isArray(data?.plans)) return;
        setPlans(data.plans.map(normalizePackage));
        setPaymentAvailable(Boolean(data.payment_available));
      })
      .catch(() => {
        if (alive) setPlans([]);
      });
    return () => { alive = false; };
  }, [apiBase]);

  const visiblePlans = useMemo(() => (
    plans.length ? plans : Object.entries(PACKAGE_META).map(([key, meta]) => ({
      key,
      title: meta.title,
      subtitle: meta.subtitle,
      price: meta.price,
      period: meta.period,
      icon: meta.icon,
      btnLabel: meta.btnLabel,
      recommended: meta.recommended,
      benefits: [],
    }))
  ), [plans]);

  const completeWithPlan = async (plan = selectedPlan) => {
    setSelectedPlan(plan);
    setMessage("");
    if (plan !== "free" && !paymentAvailable) {
      setMessage("当前项目尚未接入支付系统，付费套餐暂不能直接开通。请先选择免费体验。");
      return;
    }
    if (!user?.username) {
      setMessage("登录状态已失效，请重新登录后再试");
      return;
    }
    const details = savedDetails || initialDetails || {};
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/programming/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${encodeURIComponent(user.username)}`,
        },
        body: JSON.stringify({
          main_language: details.main_language || "Python",
          level: details.level || "零基础",
          problems: Array.isArray(details.problems) ? details.problems : [],
          plan,
          onboarding_completed: true,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "套餐保存失败");
      onComplete?.(data);
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
          {visiblePlans.map((pkg) => (
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
