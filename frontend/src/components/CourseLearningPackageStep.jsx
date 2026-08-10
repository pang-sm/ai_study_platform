import { useEffect, useState } from "react";
import PlanSelection from "./PlanSelection.jsx";

export default function CourseLearningPackageStep({
  apiBase = "/api",
  initialPlan = "quarterly",
  saving = false,
  error = "",
  onBack,
  onComplete,
}) {
  const [selectedPlan, setSelectedPlan] = useState(initialPlan || "quarterly");
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase}/membership/catalog?service_key=course_learning`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive) return;
        if (!Array.isArray(data?.plans)) throw new Error("套餐目录加载失败");
        setPlans(data.plans);
      })
      .catch(() => alive && setLoadError("套餐目录加载失败，请稍后重试。"))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [apiBase]);

  const completeWithPlan = (plan) => {
    if (saving) return;
    setSelectedPlan(plan.plan_code);
    onComplete?.(plan.plan_code);
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
        {loading && <div className="ob-error">课程学习套餐加载中，请稍候…</div>}
        {!loading && loadError && <div className="ob-error">{loadError}</div>}
        {!loading && !loadError && (
          <PlanSelection
            plans={plans}
            mode="onboarding"
            selectedPlan={selectedPlan}
            saving={saving}
            onSelect={setSelectedPlan}
            onConfirm={completeWithPlan}
          />
        )}
        <div className="ob-actions ob-actions--dual">
          <button type="button" className="ob-btn-secondary" onClick={onBack} disabled={saving}>上一步</button>
          <button
            type="button"
            className="ob-btn-primary"
            onClick={() => {
              const plan = plans.find((item) => item.plan_code === selectedPlan);
              if (plan) completeWithPlan(plan);
            }}
            disabled={saving || loading || !plans.length}
          >
            {saving ? "保存中…" : "继续"}
          </button>
        </div>
      </div>
    </div>
  );
}
