import { useEffect, useMemo, useState } from "react";
import "./CheckoutPage.css";

function money(cents) {
  return (Number(cents || 0) / 100).toFixed(2);
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function CheckoutPage({ apiBase, serviceKey, planCode, onBack, onComplete }) {
  const [catalog, setCatalog] = useState(null);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const plan = useMemo(
    () => catalog?.plans?.find((item) => item.plan_code === planCode) || null,
    [catalog, planCode],
  );

  const loadCheckout = async () => {
    setLoading(true);
    setError("");
    try {
      const [catalogRes, ordersRes] = await Promise.all([
        fetch(`${apiBase}/membership/catalog?service_key=${encodeURIComponent(serviceKey)}`),
        fetch(`${apiBase}/membership/orders?service_key=${encodeURIComponent(serviceKey)}`),
      ]);
      const catalogData = await catalogRes.json().catch(() => ({}));
      const ordersData = await ordersRes.json().catch(() => ({}));
      if (!catalogRes.ok) throw new Error(catalogData.detail || "套餐信息加载失败");
      if (!ordersRes.ok) throw new Error(ordersData.detail || "订单信息加载失败");
      setCatalog(catalogData);
      const existing = (ordersData.orders || []).find((item) => (
        item.target_plan === planCode && ["pending", "paid"].includes(item.status)
      ));
      setOrder(existing || null);
    } catch (err) {
      setError(err.message || "结算信息加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadCheckout(); }, [apiBase, serviceKey, planCode]);

  const createOrder = async () => {
    setWorking(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/membership/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_key: serviceKey, target_plan: planCode }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "订单创建失败");
      setOrder(data.order);
    } catch (err) {
      setError(err.message || "订单创建失败");
    } finally {
      setWorking(false);
    }
  };

  const payOrder = async () => {
    if (!order?.id) return;
    setWorking(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/membership/orders/${order.id}/pay`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "支付失败");
      setOrder(data.order);
      onComplete?.(data.order);
    } catch (err) {
      setError(err.message || "支付失败");
    } finally {
      setWorking(false);
    }
  };

  const cancelOrder = async () => {
    if (!order?.id || order.status !== "pending") return;
    setWorking(true);
    setError("");
    try {
      const response = await fetch(`${apiBase}/membership/orders/${order.id}/cancel`, { method: "POST" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "订单取消失败");
      setOrder(data.order);
    } catch (err) {
      setError(err.message || "订单取消失败");
    } finally {
      setWorking(false);
    }
  };

  if (loading) return <div className="checkout-shell"><div className="checkout-card">结算信息加载中...</div></div>;

  return (
    <div className="checkout-shell">
      <div className="checkout-card">
        <button type="button" className="checkout-back" onClick={onBack}>← 返回会员中心</button>
        <div className="checkout-kicker">安全结算</div>
        <h1>{plan?.name || "套餐结算"}</h1>
        <p className="checkout-subtitle">当前方向：{catalog?.service_key || serviceKey}</p>
        <div className="checkout-notice">模拟支付环境，不产生真实扣款。</div>
        {error && <div className="checkout-error" role="alert">{error}</div>}
        {plan ? (
          <div className="checkout-summary">
            <div><span>应付金额</span><strong>¥{money(plan.price_cents)}</strong></div>
            <div><span>有效期</span><span>{plan.duration_days} 天</span></div>
            <div><span>订单状态</span><span>{order?.status || "未创建"}</span></div>
            {order?.order_expires_at && <div><span>订单有效至</span><span>{formatDate(order.order_expires_at)}</span></div>}
            {order?.membership_expires_at && <div><span>会员有效至</span><span>{formatDate(order.membership_expires_at)}</span></div>}
          </div>
        ) : (
          <div className="checkout-error">套餐不存在或已下架。</div>
        )}
        <div className="checkout-actions">
          {!order || ["cancelled", "expired"].includes(order.status) ? (
            <button type="button" className="checkout-primary" disabled={!plan || working} onClick={createOrder}>
              {working ? "处理中..." : "创建模拟订单"}
            </button>
          ) : order.status === "pending" ? (
            <>
              <button type="button" className="checkout-secondary" disabled={working} onClick={cancelOrder}>取消订单</button>
              <button type="button" className="checkout-primary" disabled={working} onClick={payOrder}>模拟支付并开通</button>
            </>
          ) : (
            <button type="button" className="checkout-primary" disabled>已开通</button>
          )}
        </div>
        {order?.status === "paid" && <div className="checkout-success">会员已生效，刷新页面后仍会从服务端恢复。</div>}
      </div>
    </div>
  );
}
