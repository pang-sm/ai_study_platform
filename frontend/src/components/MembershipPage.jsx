import { useState, useEffect, useCallback } from "react";
import "./MembershipPage.css";

export default function MembershipPage({ user, apiBase, setPage, onPlanUpdate }) {
  const [effectivePlan, setEffectivePlan] = useState(null);
  const [plans, setPlans] = useState([]);
  const [recommendation, setRecommendation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [redeemOpen, setRedeemOpen] = useState(false);
  const [redeemCode, setRedeemCode] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState(null);
  const [toast, setToast] = useState("");
  const [manualChoiceOpen, setManualChoiceOpen] = useState(false);

  const showToast = useCallback((msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  }, []);

  // Load membership data
  useEffect(() => {
    if (!user?.username) return;
    setLoading(true);

    Promise.all([
      fetch(`${apiBase}/membership/summary?username=${encodeURIComponent(user.username)}`).then((r) => r.json()),
      fetch(`${apiBase}/membership/recommendation?username=${encodeURIComponent(user.username)}`).then((r) => r.json().catch(() => null)),
      fetch(`${apiBase}/membership/plans?username=${encodeURIComponent(user.username)}`).then((r) => r.json()),
    ])
      .then(([summary, rec, plansData]) => {
        setEffectivePlan(summary.effective_plan);
        setRecommendation(rec);
        setPlans(plansData.plans || []);
      })
      .catch(() => {
        showToast("加载会员信息失败");
      })
      .finally(() => setLoading(false));
  }, [user?.username, apiBase, showToast]);

  // Handle manual recommendation choice
  const handleManualChoice = async (selectedPlan) => {
    try {
      const res = await fetch(`${apiBase}/membership/recommendation/manual?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_plan: selectedPlan }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        // Re-fetch recommendation
        const recRes = await fetch(`${apiBase}/membership/recommendation?username=${encodeURIComponent(user.username)}`);
        const rec = await recRes.json();
        setRecommendation(rec);
        setManualChoiceOpen(false);
        showToast("已记录你的学习方向偏好");
        // Re-fetch plans to update recommended state
        const plansRes = await fetch(`${apiBase}/membership/plans?username=${encodeURIComponent(user.username)}`);
        const plansData = await plansRes.json();
        setPlans(plansData.plans || []);
      }
    } catch {
      showToast("操作失败，请稍后重试");
    }
  };

  // Handle redeem
  const handleRedeem = async () => {
    if (!redeemCode.trim()) {
      setRedeemResult({ success: false, message: "请输入兑换码" });
      return;
    }
    setRedeeming(true);
    setRedeemResult(null);
    try {
      const res = await fetch(`${apiBase}/membership/redeem?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: redeemCode.trim() }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setRedeemResult({ success: true, message: data.message });
        setRedeemCode("");
        // Refresh membership status
        const summaryRes = await fetch(`${apiBase}/membership/summary?username=${encodeURIComponent(user.username)}`);
        const summary = await summaryRes.json();
        setEffectivePlan(summary.effective_plan);
        // Notify parent
        if (onPlanUpdate) {
          onPlanUpdate({ plan: summary.current_plan });
        }
      } else {
        setRedeemResult({ success: false, message: data.detail || data.message || "兑换失败" });
      }
    } catch {
      setRedeemResult({ success: false, message: "网络错误，请稍后重试" });
    } finally {
      setRedeeming(false);
    }
  };

  const isDev = effectivePlan?.is_developer;
  const isMember = effectivePlan?.plan_code !== "free";

  // Determine recommended plan from recommendation
  const recommendedPlanCode = recommendation?.recommended_plan;

  // Merge recommendation into plans data
  const plansWithRecommendation = plans.map((p) => ({
    ...p,
    is_recommended: p.plan_code === recommendedPlanCode,
  }));

  if (loading) {
    return (
      <div className="mp-shell">
        <div className="mp-loading">加载中...</div>
      </div>
    );
  }

  // ── Developer view ──
  if (isDev) {
    return (
      <div className="mp-shell">
        {toast && <div className="mp-toast">{toast}</div>}
        <div className="mp-header">
          <button className="mp-back-btn" onClick={() => setPage("profile")}>← 返回个人主页</button>
          <h1 className="mp-title">会员中心</h1>
        </div>
        <div className="mp-card mp-dev-card">
          <div className="mp-dev-icon">🛠️</div>
          <div className="mp-dev-title">开发者账号</div>
          <div className="mp-dev-desc">已开放所有功能，无需开通会员</div>
          <div className="mp-dev-perks">
            <span>无限 AI 问答</span>
            <span>无限文件上传</span>
            <span>全语言编程支持</span>
            <span>所有高级功能</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mp-shell">
      {/* Toast */}
      {toast && <div className="mp-toast">{toast}</div>}

      {/* Header */}
      <div className="mp-header">
        <button className="mp-back-btn" onClick={() => setPage("profile")}>← 返回个人主页</button>
        <div>
          <h1 className="mp-title">会员中心</h1>
          <p className="mp-subtitle">根据你的专业，为你推荐最适合的学习套餐</p>
        </div>
      </div>

      {/* ── Recommendation Banner ── */}
      {recommendation && recommendation.source !== "fallback" && !recommendation.needs_manual_choice && (
        <div className="mp-card mp-recommend-card">
          <div className="mp-rec-header">
            <span className="mp-rec-icon">🎯</span>
            <div>
              <div className="mp-rec-title">系统推荐</div>
              {recommendation.normalized_major && (
                <div className="mp-rec-major">
                  你的专业：<strong>{recommendation.normalized_major}</strong>
                </div>
              )}
            </div>
          </div>
          <div className="mp-rec-body">
            <div className="mp-rec-reason">{recommendation.reason}</div>
            {recommendation.suggested_courses?.length > 0 && (
              <div className="mp-rec-courses">
                <span className="mp-rec-courses-label">推荐课程：</span>
                {recommendation.suggested_courses.map((c, i) => (
                  <span key={i} className="mp-rec-course-tag">{c}</span>
                ))}
              </div>
            )}
            <div className="mp-rec-source">
              推荐来源：
              {recommendation.source === "rule" && "规则匹配"}
              {recommendation.source === "keyword" && "关键词匹配"}
              {recommendation.source === "ai" && "AI 判断"}
              {recommendation.source === "cache" && "缓存结果"}
              {recommendation.source === "manual" && "手动选择"}
              {recommendation.source === "role" && "系统身份"}
            </div>
          </div>
        </div>
      )}

      {/* ── Low confidence / manual choice needed ── */}
      {recommendation?.needs_manual_choice && recommendation?.source !== "role" && (
        <div className="mp-card mp-unknown-card">
          <div className="mp-unknown-title">我们还不太确定你的专业方向</div>
          <div className="mp-unknown-desc">你可以选择更接近自己的学习需求，我们会为你推荐更合适的套餐：</div>
          {manualChoiceOpen ? (
            <div className="mp-manual-btns">
              <button className="mp-btn mp-btn-manual" onClick={() => handleManualChoice("python_basic")}>
                <span className="mp-manual-icon">📊</span>
                <div>
                  <strong>我主要学 Python / 数据分析</strong>
                  <div className="mp-manual-hint">经管、文学、法学、教育等方向</div>
                </div>
              </button>
              <button className="mp-btn mp-btn-manual" onClick={() => handleManualChoice("engineering_plus")}>
                <span className="mp-manual-icon">🔧</span>
                <div>
                  <strong>我主要学工科课程 / 建模 / 自动化</strong>
                  <div className="mp-manual-hint">机械、电气、土木、材料等方向</div>
                </div>
              </button>
              <button className="mp-btn mp-btn-manual" onClick={() => handleManualChoice("cs_pro")}>
                <span className="mp-manual-icon">💻</span>
                <div>
                  <strong>我主要学计算机 / 编程 / 算法</strong>
                  <div className="mp-manual-hint">软件、CS、AI、网络安全等方向</div>
                </div>
              </button>
            </div>
          ) : (
            <button className="mp-btn mp-btn-primary" onClick={() => setManualChoiceOpen(true)} style={{ marginTop: 12 }}>
              选择我的学习方向
            </button>
          )}
        </div>
      )}

      {/* ── Plan Cards ── */}
      <div className="mp-section-title">套餐选择</div>
      <div className="mp-plans-grid">
        {plansWithRecommendation.map((plan) => (
          <div
            key={plan.plan_code}
            className={`mp-plan-card${plan.is_recommended ? " mp-plan-recommended" : ""}${plan.plan_code === effectivePlan?.plan_code ? " mp-plan-current" : ""}`}
          >
            {plan.is_recommended && <div className="mp-plan-badge">推荐</div>}
            {plan.plan_code === effectivePlan?.plan_code && !plan.is_recommended && (
              <div className="mp-plan-badge mp-plan-badge-current">当前套餐</div>
            )}
            <div className="mp-plan-name">{plan.name}</div>
            <div className="mp-plan-price">
              {plan.price_yuan > 0 ? (
                <>
                  <span className="mp-plan-amount">{plan.price_yuan}</span>
                  <span className="mp-plan-unit"> 元/月</span>
                </>
              ) : (
                <span className="mp-plan-free">免费</span>
              )}
            </div>
            <div className="mp-plan-desc">{plan.perks || plan.description}</div>
            <div className="mp-plan-limits">
              <div className="mp-plan-limit-item">
                <span className="mp-limit-label">AI 问答</span>
                <span className="mp-limit-value">{plan.daily_ai_limit >= 999999 ? "无限" : `${plan.daily_ai_limit}次/天`}</span>
              </div>
              <div className="mp-plan-limit-item">
                <span className="mp-limit-label">文件上传</span>
                <span className="mp-limit-value">{plan.daily_upload_limit >= 999999 ? "无限" : `${plan.daily_upload_limit}次/天`}</span>
              </div>
              <div className="mp-plan-limit-item">
                <span className="mp-limit-label">编程练习</span>
                <span className="mp-limit-value">{plan.daily_code_limit >= 999999 ? "无限" : `${plan.daily_code_limit}次/天`}</span>
              </div>
              {plan.allowed_languages?.length > 0 && (
                <div className="mp-plan-limit-item">
                  <span className="mp-limit-label">编程语言</span>
                  <span className="mp-limit-value">{plan.allowed_languages.map((l) => l.toUpperCase()).join(" / ")}</span>
                </div>
              )}
            </div>
            <div className="mp-plan-action">
              {plan.plan_code === effectivePlan?.plan_code ? (
                <button className="mp-btn mp-btn-outline" disabled>当前套餐</button>
              ) : plan.price_yuan > 0 ? (
                <button
                  className={`mp-btn ${plan.is_recommended ? "mp-btn-primary" : "mp-btn-outline"}`}
                  onClick={() => showToast("微信支付功能正在开发中，当前仅支持兑换码激活测试权益")}
                >
                  开通套餐
                </button>
              ) : (
                <button className="mp-btn mp-btn-outline" disabled>使用免费版</button>
              )}
            </div>
            {plan.requires_ads && (
              <div className="mp-plan-ads-note">部分功能需观看广告解锁</div>
            )}
          </div>
        ))}
      </div>

      {/* ── Redeem Section ── */}
      <div className="mp-card mp-redeem-card">
        <div className="mp-redeem-left">
          <span className="mp-redeem-icon">🎁</span>
          <div>
            <div className="mp-redeem-title">有兑换码？</div>
            <div className="mp-redeem-desc">输入兑换码激活会员权益</div>
          </div>
        </div>
        <button className="mp-btn mp-btn-outline" onClick={() => { setRedeemOpen(true); setRedeemResult(null); setRedeemCode(""); }}>
          输入兑换码
        </button>
      </div>

      {/* ── Redeem Modal ── */}
      {redeemOpen && (
        <div className="mp-modal-overlay" onClick={() => setRedeemOpen(false)}>
          <div className="mp-modal" onClick={(e) => e.stopPropagation()}>
            <div className="mp-modal-title">兑换会员</div>
            <div className="mp-modal-desc">输入兑换码激活会员权益</div>
            <input
              className="mp-modal-input"
              placeholder="请输入兑换码"
              value={redeemCode}
              onChange={(e) => { setRedeemCode(e.target.value); setRedeemResult(null); }}
              onKeyDown={(e) => e.key === "Enter" && handleRedeem()}
              autoFocus
            />
            {redeemResult && (
              <div className={`mp-redeem-result ${redeemResult.success ? "mp-redeem-ok" : "mp-redeem-fail"}`}>
                {redeemResult.message}
              </div>
            )}
            <div className="mp-modal-actions">
              <button className="mp-btn mp-btn-cancel" onClick={() => setRedeemOpen(false)}>取消</button>
              <button className="mp-btn mp-btn-primary" onClick={handleRedeem} disabled={redeeming}>
                {redeeming ? "兑换中..." : "确认兑换"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
