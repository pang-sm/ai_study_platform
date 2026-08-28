import { useEffect, useState } from "react";
import PlanSelection from "./PlanSelection.jsx";
import "./ProgrammingOnboarding.css";

export default function ProgrammingPackageStep({
  apiBase = "/api",
  initialPlan = "quarterly",
  onBack,
  onCancel,
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
        if (!alive) return;
        if (!Array.isArray(data?.plans)) throw new Error("套餐目录加载失败");
        setPlans(data.plans);
      })
      .catch(() => alive && setMessage("套餐目录加载失败，请稍后重试。"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [apiBase]);

  const completeWithPlan = async (plan) => {
    setSelectedPlan(plan.plan_code);
    setMessage("");
    setSaving(true);
    try {
      await onComplete?.(plan.plan_code);
    } catch (error) {
      setMessage(error.message || "套餐保存失败，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="programming-onboarding-page">
      <section className="programming-package-card" aria-label="选择你的编程套餐">
        <div className="programming-onboarding-header programming-package-header">
          <span>第 3 步</span>
          <h1>选择你的学习套餐</h1>
          <p>根据你的学习方向，为你推荐适合编程能力提升的使用方案</p>
        </div>
        {loading && <div className="programming-onboarding-error">套餐目录加载中，请稍候…</div>}
        {message && <div className="programming-onboarding-error">{message}</div>}
        {!loading && !message && (
          <PlanSelection
            plans={plans}
            mode="onboarding"
            selectedPlan={selectedPlan}
            recommendedPlanCode="quarterly"
            saving={saving}
            onSelect={setSelectedPlan}
            onConfirm={completeWithPlan}
          />
        )}
        <div className="programming-onboarding-actions">
          {onCancel && <button type="button" className="programming-btn-secondary" onClick={onCancel} disabled={saving}>取消并返回</button>}
          <button type="button" className="programming-btn-secondary" onClick={onBack} disabled={saving}>上一步</button>
          <button
            type="button"
            className="programming-btn-primary"
            onClick={() => {
              const plan = plans.find((item) => item.plan_code === selectedPlan);
              if (plan) completeWithPlan(plan);
            }}
            disabled={saving || loading || !plans.length}
          >
            {saving ? "保存中…" : "继续"}
          </button>
        </div>
      </section>
    </div>
  );
}
