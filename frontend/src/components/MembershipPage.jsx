import { useCallback, useEffect, useState } from "react";
import "./MembershipPage.css";
import PlanSelection from "./PlanSelection.jsx";
import { notifyFeatureEntitlementsUpdated } from "../hooks/useFeatureEntitlements.js";

function readJson(response) {
  return response.json().catch(() => ({}));
}

export default function MembershipPage({
  user,
  apiBase,
  setPage,
  onPlanUpdate,
  profilePage = "examProfile",
  serviceKey = "exam_11408",
  returnPage = "examHome",
  directionLabel = "11408 考研",
}) {
  const [effectivePlan, setEffectivePlan] = useState(null);
  const [plans, setPlans] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [reminders, setReminders] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [checkoutStarting, setCheckoutStarting] = useState("");
  const [redeemOpen, setRedeemOpen] = useState(false);
  const [redeemCode, setRedeemCode] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState(null);
  const [redeemPreview, setRedeemPreview] = useState(null);
  const [manualChoiceOpen, setManualChoiceOpen] = useState(false);

  const loadMembership = useCallback(async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const [summaryRes, recommendationRes, catalogRes] = await Promise.all([
        fetch(`${apiBase}/membership/summary?username=${encodeURIComponent(user.username)}`, { credentials: "include" }),
        fetch(`${apiBase}/membership/recommendation?username=${encodeURIComponent(user.username)}`, { credentials: "include" }),
        fetch(`${apiBase}/membership/catalog?service_key=${encodeURIComponent(serviceKey)}`, { credentials: "include" }),
      ]);
      const [summary, recommendationData, catalogData] = await Promise.all([
        readJson(summaryRes),
        readJson(recommendationRes),
        readJson(catalogRes),
      ]);
      if (!summaryRes.ok) throw new Error(summary.detail || "无法加载会员状态");
      if (!catalogRes.ok) throw new Error(catalogData.detail || "无法加载当前方向套餐");
      setCatalog(catalogData);
      setEffectivePlan({
        ...(summary.effective_plan || {}),
        plan_code: catalogData.current?.plan || summary.effective_plan?.plan_code || "free",
        plan_expires_at: catalogData.current?.expires_at || summary.effective_plan?.plan_expires_at || null,
      });
      setRecommendation(recommendationRes.ok ? recommendationData : null);
      setPlans(catalogData.plans || []);
    } catch (loadError) {
      setError(loadError.message || "会员信息加载失败");
    } finally {
      setLoading(false);
    }
  }, [apiBase, serviceKey, user?.username]);

  useEffect(() => { loadMembership(); }, [loadMembership]);

  useEffect(() => {
    if (!redeemOpen) setRedeemPreview(null);
  }, [redeemOpen]);

  useEffect(() => {
    if (redeemCode) setRedeemPreview(null);
  }, [redeemCode]);

  useEffect(() => {
    let alive = true;
    fetch(`${apiBase}/membership/reminders`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!alive) return;
        setReminders(Array.isArray(data?.reminders) ? data.reminders.filter((item) => item.service_key === serviceKey) : []);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [apiBase, serviceKey]);

  const handleManualChoice = async (selectedPlan) => {
    try {
      const response = await fetch(`${apiBase}/membership/recommendation/manual?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_plan: selectedPlan }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.detail || "保存偏好失败");
      setManualChoiceOpen(false);
      await loadMembership();
    } catch (choiceError) {
      setError(choiceError.message || "保存偏好失败");
    }
  };

  const handleRedeem = async () => {
    if (redeemPreview) {
      await confirmRedeem();
      return;
    }
    if (!redeemCode.trim()) {
      setRedeemResult({ success: false, message: "请输入兑换码" });
      return;
    }
    setRedeeming(true);
    setRedeemResult(null);
    try {
      const response = await fetch(`${apiBase}/membership/redeem/preview`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: redeemCode.trim(), service_key: serviceKey }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.detail || data.message || "兑换失败");
      setRedeemPreview(data.preview || null);
      setRedeemResult({ success: true, message: "兑换码有效，请确认激活" });
      // The preview step intentionally does not mutate membership state.
    } catch (redeemError) {
      setRedeemResult({ success: false, message: redeemError.message || "兑换失败" });
    } finally {
      setRedeeming(false);
    }
  };

  const confirmRedeem = async () => {
    if (!redeemCode.trim() || !redeemPreview) return;
    setRedeeming(true);
    setRedeemResult(null);
    try {
      const response = await fetch(`${apiBase}/membership/redeem`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: redeemCode.trim(), service_key: serviceKey }),
      });
      const data = await readJson(response);
      if (!response.ok) throw new Error(data.detail || data.message || "兑换失败");
      setRedeemResult({ success: true, message: data.message || "兑换成功" });
      setRedeemCode("");
      setRedeemPreview(null);
      await loadMembership();
      onPlanUpdate?.({ plan: data.redemption?.target_plan || effectivePlan?.plan_code || "free" });
      notifyFeatureEntitlementsUpdated();
    } catch (redeemError) {
      setRedeemResult({ success: false, message: redeemError.message || "兑换失败" });
    } finally {
      setRedeeming(false);
    }
  };

  const startCheckout = async (plan) => {
    setCheckoutStarting(plan.plan_code);
    setError("");
    try {
      const response = await fetch(`${apiBase}/membership/orders`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_key: serviceKey, target_plan: plan.plan_code }),
      });
      const data = await readJson(response);
      if (!response.ok || !data.order?.id) throw new Error(data.detail || "订单创建失败");
      const order = data.order;
      const context = {
        serviceKey,
        service_key: serviceKey,
        sourceDirection: serviceKey,
        source_direction: serviceKey,
        currentPlan: effectivePlan?.plan_code || catalog?.current?.plan || "free",
        current_plan: effectivePlan?.plan_code || catalog?.current?.plan || "free",
        targetPlan: plan.plan_code,
        target_plan: plan.plan_code,
        orderId: order.id,
        order_id: order.id,
        profilePage,
        returnPage,
        return_page: returnPage,
        directionLabel,
      };
      setPage("membershipCheckout", context);
    } catch (checkoutError) {
      setError(checkoutError.message || "订单创建失败");
    } finally {
      setCheckoutStarting("");
    }
  };

  const currentPlanCode = effectivePlan?.plan_code || catalog?.current?.plan || "free";
  const recommendedPlanCode = recommendation?.recommended_plan;

  if (loading) {
    return <div className="membership-shell"><div className="membership-loading">正在加载会员方案…</div></div>;
  }

  if (effectivePlan?.is_developer) {
    return (
      <div className="membership-shell">
        <button type="button" className="membership-back" onClick={() => setPage(profilePage)}>← 返回个人主页</button>
        <div className="membership-heading"><span className="membership-eyebrow">{directionLabel}</span><h1>会员方案</h1><p>开发者账号已拥有当前方向的全部功能。</p></div>
        <section className="membership-panel membership-developer-panel"><div className="membership-status-mark">✓</div><h2>全部功能已开放</h2><p>无需购买会员方案。</p></section>
      </div>
    );
  }

  return (
    <div className="membership-shell membership-shell--standalone">
      <div className="membership-page-card">
      <div className="membership-header-row">
        <button type="button" className="membership-back" onClick={() => setPage(profilePage)}>← 返回个人主页</button>
        <span className="membership-direction">{directionLabel}</span>
      </div>
      <header className="membership-heading">
        <span className="membership-eyebrow">MEMBERSHIP</span>
        <h1>选择适合你的学习方案</h1>
        <p>当前方向的套餐、额度和有效期均来自服务端实时目录。</p>
        {catalog?.payment_notice && <div className="membership-notice">{catalog.payment_notice}</div>}
        {reminders[0] && <div className="membership-reminder">{reminders[0].level === "expired" ? "当前会员已到期，已恢复免费权益。" : `当前会员将在 ${reminders[0].days_left} 天内到期，请及时续期。`}</div>}
      </header>

      {error && <div className="membership-error" role="alert">{error}</div>}

      {recommendation && recommendation.source !== "fallback" && !recommendation.needs_manual_choice && (
        <section className="membership-panel membership-recommendation">
          <div><span className="membership-eyebrow">PERSONALIZED</span><h2>为你推荐</h2><p>{recommendation.reason}</p></div>
          {recommendation.normalized_major && <span className="membership-recommendation-major">{recommendation.normalized_major}</span>}
        </section>
      )}

      {recommendation?.needs_manual_choice && recommendation?.source !== "role" && (
        <section className="membership-panel membership-manual-choice">
          <h2>告诉我们你的学习方向</h2>
          <p>选择后会用于优化会员建议，不会改变已购买的方案。</p>
          {manualChoiceOpen ? (
            <div className="membership-choice-list">
              {[
                ["python_basic", "Python / 数据分析"],
                ["engineering_plus", "工科课程 / 建模"],
                ["cs_pro", "计算机 / 编程 / 算法"],
              ].map(([value, label]) => <button key={value} type="button" onClick={() => handleManualChoice(value)}>{label}<span>→</span></button>)}
            </div>
          ) : <button type="button" className="membership-button membership-button-secondary" onClick={() => setManualChoiceOpen(true)}>选择学习方向</button>}
        </section>
      )}

      <section className="membership-plans-section">
        <div className="membership-section-heading"><div><span className="membership-eyebrow">PLANS</span><h2>套餐选择</h2></div><span className="membership-current-plan">当前方案：{plans.find((plan) => plan.plan_code === currentPlanCode)?.name || currentPlanCode}</span></div>
        <PlanSelection
          plans={plans}
          mode="membership"
          currentPlanCode={currentPlanCode}
          recommendedPlanCode={recommendedPlanCode}
          busyPlan={checkoutStarting}
          onConfirm={startCheckout}
        />
      </section>

      <section className="membership-panel membership-redeem-panel">
        <div><span className="membership-eyebrow">REDEEM</span><h2>兑换码</h2><p>如果你已有兑换码，可以在这里激活会员权益。</p></div>
        <button type="button" className="membership-button membership-button-secondary" onClick={() => { setRedeemOpen(true); setRedeemResult(null); setRedeemCode(""); }}>输入兑换码</button>
      </section>

      {redeemOpen && (
        <div className="membership-modal-backdrop" onClick={() => setRedeemOpen(false)}>
          <div className="membership-modal" onClick={(event) => event.stopPropagation()}>
            <h2>兑换会员</h2><p>输入兑换码激活会员权益。</p>
            <input value={redeemCode} onChange={(event) => { setRedeemCode(event.target.value); setRedeemResult(null); }} onKeyDown={(event) => event.key === "Enter" && handleRedeem()} placeholder="请输入兑换码" autoFocus />
            {redeemPreview && <div className="membership-redeem-preview">
              <div><span>服务方向</span><strong>{redeemPreview.service_key}</strong></div>
              <div><span>目标套餐</span><strong>{redeemPreview.target_plan_name || redeemPreview.target_plan}</strong></div>
              <div><span>会员时长</span><strong>{redeemPreview.membership_duration_days} 天</strong></div>
              <div><span>预计到期</span><strong>{redeemPreview.projected_expires_at?.slice(0, 10)}</strong></div>
            </div>}
            {redeemResult && <div className={`membership-redeem-result ${redeemResult.success ? "is-success" : "is-error"}`}>{redeemResult.message}</div>}
            <div className="membership-modal-actions"><button type="button" className="membership-button membership-button-secondary" onClick={() => setRedeemOpen(false)}>取消</button><button type="button" className="membership-button membership-button-primary" onClick={handleRedeem} disabled={redeeming}>{redeeming ? "兑换中…" : "确认兑换"}</button></div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
