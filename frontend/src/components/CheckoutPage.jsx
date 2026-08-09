import { useEffect, useMemo, useState } from "react";
import "./CheckoutPage.css";

function money(cents) {
  return (Number(cents || 0) / 100).toFixed(2);
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", { hour12: false });
}

function statusLabel(status) {
  return { pending: "待支付", paid: "已支付", cancelled: "已取消", expired: "已过期" }[status] || status || "未知";
}

function directionName(serviceKey, directionLabel) {
  return directionLabel || ({ course_learning: "课程学习", programming: "编程学习", exam_11408: "11408 考研" }[serviceKey] || serviceKey);
}

export default function CheckoutPage({
  apiBase,
  serviceKey,
  planCode,
  orderId,
  currentPlan = "free",
  directionLabel,
  onBack,
  onComplete,
  onReturnHome,
}) {
  const [catalog, setCatalog] = useState(null);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const plan = useMemo(
    () => catalog?.plans?.find((item) => item.plan_code === (order?.target_plan || planCode)) || null,
    [catalog, order?.target_plan, planCode],
  );

  const currentPlanDetails = useMemo(
    () => catalog?.plans?.find((item) => item.plan_code === currentPlan) || null,
    [catalog, currentPlan],
  );

  useEffect(() => {
    let alive = true;
    const loadCheckout = async () => {
      setLoading(true);
      setError("");
      try {
        const catalogResponse = await fetch(`${apiBase}/membership/catalog?service_key=${encodeURIComponent(serviceKey)}`, { credentials: "include" });
        const catalogData = await catalogResponse.json().catch(() => ({}));
        if (!catalogResponse.ok) throw new Error(catalogData.detail || "套餐信息加载失败");

        let orderData;
        if (orderId) {
          const orderResponse = await fetch(`${apiBase}/membership/orders/${encodeURIComponent(orderId)}`, { credentials: "include" });
          orderData = await orderResponse.json().catch(() => ({}));
          if (!orderResponse.ok) throw new Error(orderData.detail || "订单不存在或已失效");
        } else {
          const ordersResponse = await fetch(`${apiBase}/membership/orders?service_key=${encodeURIComponent(serviceKey)}`, { credentials: "include" });
          const ordersData = await ordersResponse.json().catch(() => ({}));
          if (!ordersResponse.ok) throw new Error(ordersData.detail || "订单信息加载失败");
          const existing = (ordersData.orders || []).find((item) => item.target_plan === planCode && ["pending", "paid"].includes(item.status));
          orderData = existing ? { order: existing } : {};
        }

        const nextOrder = orderData.order;
        if (!nextOrder) throw new Error("订单上下文已失效，请返回会员中心重新选择套餐。");
        if (nextOrder.service_key !== serviceKey || (planCode && nextOrder.target_plan !== planCode)) {
          throw new Error("订单与当前学习方向不匹配，请返回会员中心重新选择套餐。");
        }
        if (!alive) return;
        setCatalog(catalogData);
        setOrder(nextOrder);
      } catch (loadError) {
        if (alive) setError(loadError.message || "结算信息加载失败");
      } finally {
        if (alive) setLoading(false);
      }
    };
    loadCheckout();
    return () => { alive = false; };
  }, [apiBase, orderId, planCode, serviceKey]);

  const payOrder = async () => {
    if (!order?.id || order.status !== "pending") return;
    setWorking(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/membership/orders/${order.id}/pay`, { method: "POST", credentials: "include" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "支付失败");
      setOrder(data.order);
    } catch (payError) {
      setError(payError.message || "支付失败");
    } finally {
      setWorking(false);
    }
  };

  const cancelOrder = async () => {
    if (!order?.id || order.status !== "pending") return;
    setWorking(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/membership/orders/${order.id}/cancel`, { method: "POST", credentials: "include" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "订单取消失败");
      setOrder(data.order);
    } catch (cancelError) {
      setError(cancelError.message || "订单取消失败");
    } finally {
      setWorking(false);
    }
  };

  if (loading) return <div className="checkout-shell"><div className="checkout-loading">正在加载订单…</div></div>;

  if (error && !order) {
    return <div className="checkout-shell"><div className="checkout-error-state"><button type="button" className="checkout-back" onClick={onBack}>← 返回会员中心</button><h1>无法打开订单</h1><p>{error}</p><button type="button" className="checkout-button checkout-button-primary" onClick={onBack}>返回会员中心</button></div></div>;
  }

  const displayDirection = directionName(serviceKey, directionLabel);
  const amount = order?.amount ?? plan?.price_cents ?? 0;
  const paid = order?.status === "paid";

  return (
    <div className="checkout-shell checkout-shell--standalone">
      <div className="checkout-page-card">
      <div className="checkout-topbar"><button type="button" className="checkout-back" onClick={onBack}>← 返回会员中心</button><span>{displayDirection}</span></div>
      <header className="checkout-heading"><span className="checkout-eyebrow">CHECKOUT</span><h1>{paid ? "支付成功" : "确认订单"}</h1><p>{paid ? "你的会员权益已经生效。" : `升级你的 ${plan?.name || order?.target_plan || "学习套餐"}`}</p></header>

      {error && <div className="checkout-error" role="alert">{error}</div>}

      {paid ? (
        <section className="checkout-success-panel">
          <div className="checkout-success-mark">✓</div>
          <span className="checkout-eyebrow">PAYMENT COMPLETE</span>
          <h2>模拟支付成功</h2>
          <p>本次仅更新会员权益，不会产生真实扣款。</p>
          <dl className="checkout-success-details">
            <div><dt>套餐</dt><dd>{plan?.name || order.target_plan}</dd></div>
            <div><dt>服务方向</dt><dd>{displayDirection}</dd></div>
            <div><dt>生效时间</dt><dd>{formatDate(order.membership_started_at)}</dd></div>
            <div><dt>到期时间</dt><dd>{formatDate(order.membership_expires_at)}</dd></div>
            <div><dt>订单号</dt><dd>#{order.id}</dd></div>
          </dl>
          <div className="checkout-success-actions"><button type="button" className="checkout-button checkout-button-secondary" onClick={onComplete}>查看我的会员</button><button type="button" className="checkout-button checkout-button-primary" onClick={onReturnHome}>返回学习</button></div>
        </section>
      ) : (
        <div className="checkout-grid">
          <main className="checkout-main-column">
            <section className="checkout-panel"><span className="checkout-eyebrow">PLAN DETAILS</span><h2>套餐信息</h2><div className="checkout-detail-list"><div><span>当前套餐</span><strong>{currentPlanDetails?.name || currentPlan}</strong></div><div><span>升级至</span><strong>{plan?.name || order?.target_plan}</strong></div><div><span>服务方向</span><strong>{displayDirection}</strong></div><div><span>套餐周期</span><strong>{plan?.duration_days ? `${plan.duration_days} 天` : "-"}</strong></div><div><span>预计到期</span><strong>{order?.order_expires_at ? formatDate(order.order_expires_at) : "支付后计算"}</strong></div></div></section>
            <section className="checkout-panel checkout-payment-panel"><span className="checkout-eyebrow">PAYMENT METHOD</span><h2>支付方式</h2><div className="checkout-payment-option"><span className="checkout-payment-icon">¥</span><div><strong>模拟支付</strong><p>开发验收环境</p></div><span className="checkout-payment-selected">已选择</span></div><div className="checkout-payment-note">当前为模拟支付环境，不会产生真实扣款。支付成功后，服务端会立即更新当前方向的会员权益。</div></section>
          </main>
          <aside className="checkout-summary-panel"><span className="checkout-eyebrow">ORDER SUMMARY</span><h2>订单摘要</h2><div className="checkout-summary-line"><span>套餐</span><strong>{plan?.name || order?.target_plan}</strong></div><div className="checkout-summary-line"><span>周期</span><strong>{plan?.duration_days ? `${plan.duration_days} 天` : "-"}</strong></div><div className="checkout-summary-total"><span>应付金额</span><strong>¥{money(amount)}</strong></div><div className="checkout-summary-meta"><span>订单号</span><span>#{order.id}</span><span>订单状态</span><span>{statusLabel(order.status)}</span><span>支付剩余时间</span><span>{formatDate(order.order_expires_at)}</span></div>{order.status === "pending" ? <><button type="button" className="checkout-button checkout-button-primary" onClick={payOrder} disabled={working}> {working ? "处理中…" : `确认模拟支付 ¥${money(amount)}`}</button><button type="button" className="checkout-button checkout-button-secondary checkout-cancel-button" onClick={cancelOrder} disabled={working}>取消订单</button><p className="checkout-disclaimer">模拟支付不会产生真实扣款</p></> : <div className="checkout-closed-state">订单{statusLabel(order.status)}，请返回会员中心重新选择。</div>}</aside>
        </div>
      )}
      </div>
    </div>
  );
}
