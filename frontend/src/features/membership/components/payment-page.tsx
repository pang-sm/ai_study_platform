import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';
import { Container } from '@/components/ui/container';
import { StatusNote } from '@/components/ui/status-note';
import { Spinner } from '@/components/ui/spinner';
import { ApiRequestError } from '@/features/exam/api/content-status';
import { serverMessage } from '@/lib/api/server-message';
import { formatDateTime } from '@/lib/format';
import {
  useCreateSubscriptionOrder, usePaySubscriptionOrder, useSubscriptionPlans, useSubscriptionState,
  type OrderableTier, type PendingOrder,
} from '../api/subscription';
import { formatPeriod, formatPrice, planRows, tierLabel } from '../view-models/membership';

/**
 * Ordering a tier, and finding out whether it can actually be paid for.
 *
 * THE ONE RULE THIS PAGE FOLLOWS
 * It never says a payment succeeded unless the server said so. The order endpoint writes a
 * PENDING row and activates nothing; activation happens on a verified payment callback. So the
 * page is built as two visible steps — 确认订单 (real, server-side) and 支付 (real, server-side) —
 * and whatever the second step answers is what the learner is told.
 *
 * Today the second step answers 403 in production: the only payment adapter is a mock, and
 * production refuses it. That 403 is rendered as itself — "在线支付尚未开通" — together with the
 * one fact that matters to someone who just pressed a button: no money moved and no order was
 * settled. A screen that instead showed a green "开通成功" would be inventing a subscription the
 * database does not have, and the learner would find out at the next locked feature.
 *
 * The order itself is NOT created on mount. Writing a row because a page was opened puts an
 * abandoned pending order in the audit trail for every learner who looked, which is a cost with
 * no matching intent.
 */
export function MembershipPaymentPage({ tier }: { tier: OrderableTier }) {
  const plans = useSubscriptionPlans();
  const subscription = useSubscriptionState();
  const create = useCreateSubscriptionOrder();
  const pay = usePaySubscriptionOrder();
  const [order, setOrder] = useState<PendingOrder>();
  const [orderId, setOrderId] = useState<number>();
  const [paid, setPaid] = useState(false);

  const row = planRows(plans.data?.plans, subscription.data?.tier).find((item) => item.tier === tier);
  const alreadyOnThisTier = subscription.data?.tier === tier;

  const confirmOrder = () => {
    create.mutate(tier, {
      onSuccess: (response) => {
        setOrder(response.order);
        const id = (response.order as { id?: number }).id;
        setOrderId(typeof id === 'number' ? id : undefined);
      },
    });
  };

  const submitPayment = () => {
    if (orderId === undefined) return;
    pay.mutate(orderId, { onSuccess: () => setPaid(true) });
  };

  const payRefusal = pay.error instanceof ApiRequestError ? pay.error : undefined;

  return (
    <div className="membership">
      <Container className="membership__inner">
        <header className="membership__header">
          <p>会员 / 订单确认</p>
          <h1 className="text-page-title font-semibold text-text-primary">
            {tierLabel(tier)} · {plans.isPending ? '…' : formatPrice(row?.priceCents ?? null)}
          </h1>
          <p className="membership-note">
            {row?.durationDays ? `一次开通 ${formatPeriod(row.durationDays)}，到期不会自动续费。` : null}
          </p>
        </header>

        {alreadyOnThisTier ? (
          <StatusNote className="mt-6">
            你现在已经是 {tierLabel(tier)}。继续下单会从今天起重新计算这一个周期。
          </StatusNote>
        ) : null}

        {plans.isError ? (
          <StatusNote tone="danger" className="mt-6">
            档位信息暂时读不到，因此这里不能安全地下单。稍后重试。
          </StatusNote>
        ) : null}

        {/* Step 1 — a real order, written server-side. */}
        {!order ? (
          <section aria-labelledby="payment-step-one" className="mt-8">
            {/* Stated BEFORE the learner spends a click on it. Discovering that the payment
                channel is not connected only after pressing 去支付 is a worse answer than
                saying so on arrival — and the order is still real, so the page explains what
                creating one does and does not do. */}
            <StatusNote tone="warning">
              在线支付暂未开放：<strong>现在下单不会产生任何扣款</strong>，档位也不会变化。
              订单可以先创建并保留，支付通道接入后按这个订单继续。
            </StatusNote>
            <h2 id="payment-step-one" className="mt-6 text-card-title font-semibold text-text-primary">
              确认订单
            </h2>
            <dl className="membership__facts mt-4">
              <div><dt>档位</dt><dd>{tierLabel(tier)}</dd></div>
              <div><dt>金额</dt><dd>{formatPrice(row?.priceCents ?? null)}</dd></div>
              <div><dt>时长</dt><dd>{formatPeriod(row?.durationDays ?? null) || '—'}</dd></div>
            </dl>
            <Button
              className="mt-6"
              onClick={confirmOrder}
              disabled={create.isPending || plans.isError || !row?.priceCents}
            >
              {create.isPending ? '正在创建订单…' : '创建订单'}
            </Button>
            {create.isError ? (
              <StatusNote tone="danger" className="mt-4">
                {create.error instanceof ApiRequestError && serverMessage(create.error.detail)
                  ? serverMessage(create.error.detail)
                  : '订单没有创建成功，稍后再试。'}
              </StatusNote>
            ) : null}
          </section>
        ) : (
          <section aria-labelledby="payment-step-two" className="mt-8">
            <h2 id="payment-step-two" className="text-card-title font-semibold text-text-primary">
              订单已创建
            </h2>
            <dl className="membership__facts mt-4">
              <div><dt>订单号</dt><dd>{order.order_no ?? '—'}</dd></div>
              <div>
                <dt>金额</dt>
                <dd>{order.amount_cents !== undefined ? formatPrice(order.amount_cents) : '—'}</dd>
              </div>
              <div><dt>状态</dt><dd>{order.status === 'pending' ? '待支付' : (order.status ?? '—')}</dd></div>
              {order.order_expires_at ? (
                <div><dt>订单有效期</dt><dd>{formatDateTime(order.order_expires_at)}</dd></div>
              ) : null}
            </dl>

            {paid ? (
              <StatusNote tone="success" className="mt-6">
                支付已完成，当前档位已更新为 {tierLabel(tier)}。
                <Link to="/membership" className="ml-3 underline">返回会员页</Link>
              </StatusNote>
            ) : (
              <>
                <Button
                  className="mt-6"
                  onClick={submitPayment}
                  disabled={pay.isPending || orderId === undefined}
                >
                  {pay.isPending ? <><Spinner className="mr-2" />正在提交支付…</> : '去支付'}
                </Button>

                {payRefusal?.status === 403 ? (
                  // The honest end of this path. The order is real and still pending; the payment
                  // that would settle it is not available here, so nothing was charged and nothing
                  // was activated.
                  <StatusNote tone="warning" className="mt-4">
                    在线支付暂未开放：<strong>没有产生任何扣款</strong>，你的档位也没有变化。
                    订单号可以保留，支付通道接入后按这个订单继续即可。
                  </StatusNote>
                ) : pay.isError ? (
                  <StatusNote tone="danger" className="mt-4">
                    {serverMessage(payRefusal?.detail) ?? '支付没有提交成功，订单仍是待支付状态。'}
                  </StatusNote>
                ) : null}
              </>
            )}

            <p className="membership-note mt-6">
              订单创建不等于开通：只有支付确认之后档位才会变化。
              <Link to="/membership" className="ml-2 underline">返回会员页</Link>
            </p>
          </section>
        )}
      </Container>
    </div>
  );
}
