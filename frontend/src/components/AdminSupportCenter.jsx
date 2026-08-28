import { useCallback, useEffect, useRef, useState } from "react";
import "./AdminSupportCenter.css";

const API_BASE = "/api";

const SERVICE_OPTIONS = [
  { value: "", label: "全部业务" },
  { value: "exam_11408", label: "11408" },
  { value: "course_learning", label: "课程学习" },
  { value: "programming", label: "编程学习" },
  { value: "account", label: "账户与会员" },
  { value: "general", label: "其他" },
];

const CATEGORY_OPTIONS = [
  { value: "", label: "全部类型" },
  { value: "functional_bug", label: "功能异常" },
  { value: "ai", label: "AI 功能" },
  { value: "materials", label: "资料库" },
  { value: "question", label: "题目 / 答案问题" },
  { value: "workbench", label: "编程工作台" },
  { value: "membership", label: "会员 / 套餐 / 权限" },
  { value: "payment", label: "支付问题" },
  { value: "account", label: "账户问题" },
  { value: "suggestion", label: "使用建议" },
  { value: "other", label: "其他" },
];

const STATUS_TABS = [
  { value: "", label: "全部" },
  { value: "unread", label: "未读" },
  { value: "pending", label: "待处理" },
  { value: "in_progress", label: "处理中" },
  { value: "waiting_confirmation", label: "等待确认" },
  { value: "resolved", label: "已解决" },
  { value: "unresolved", label: "未解决" },
];

const STATUS_LABELS = {
  pending: "待处理",
  in_progress: "处理中",
  waiting_confirmation: "等待用户确认",
  resolved: "已解决",
  unresolved: "未解决",
  closed: "已关闭",
};

function serviceLabel(value) {
  return SERVICE_OPTIONS.find((item) => item.value === value)?.label || value || "其他";
}

function categoryLabel(value) {
  return CATEGORY_OPTIONS.find((item) => item.value === value)?.label || value || "其他";
}

function formatTime(value) {
  if (!value) return "";
  const text = String(value).trim();
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(text);
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !hasTz ? `${text}Z` : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export default function AdminSupportCenter({ user, onUnreadCountChange }) {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterService, setFilterService] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterUsername, setFilterUsername] = useState("");

  const [activeTicket, setActiveTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  const activeTicketRef = useRef(activeTicket);
  activeTicketRef.current = activeTicket;
  const filterRef = useRef({ filterStatus, filterService, filterCategory, filterUsername });
  filterRef.current = { filterStatus, filterService, filterCategory, filterUsername };

  const api = useCallback(async (path, options = {}) => {
    const res = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "请求失败，请稍后重试");
    return data;
  }, []);

  const loadUnreadCount = useCallback(async () => {
    try {
      const data = await api("/admin/support/unread-count");
      onUnreadCountChange?.(Number(data.count || 0));
    } catch { /* ignore */ }
  }, [api, onUnreadCountChange]);

  const loadTickets = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const { filterStatus: status, filterService: service, filterCategory: category, filterUsername: username } = filterRef.current;
      const params = new URLSearchParams();
      if (status && status !== "unread") params.set("status", status);
      if (service) params.set("service_key", service);
      if (category) params.set("category", category);
      if (username.trim()) params.set("username", username.trim());
      params.set("page_size", "200");
      const data = await api(`/admin/support/tickets?${params.toString()}`);
      let items = data.tickets || [];
      if (status === "unread") items = items.filter((t) => t.unread);
      setTickets(items);
      setError("");
    } catch (err) {
      if (!silent) setError(err.message || "加载工单失败");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [api]);

  const refreshActiveTicket = useCallback(async () => {
    const ticket = activeTicketRef.current;
    if (!ticket?.id) return;
    try {
      const data = await api(`/admin/support/tickets/${ticket.id}`);
      setActiveTicket(data.ticket);
      setMessages(data.ticket?.messages || []);
    } catch { /* ignore */ }
  }, [api]);

  useEffect(() => {
    loadTickets();
    loadUnreadCount();
    const id = setInterval(() => {
      loadTickets(true);
      loadUnreadCount();
      if (activeTicketRef.current?.id) refreshActiveTicket();
    }, 6000);
    return () => clearInterval(id);
  }, [loadTickets, loadUnreadCount, refreshActiveTicket]);

  useEffect(() => {
    loadTickets();
  }, [filterStatus, filterService, filterCategory, filterUsername, loadTickets]);

  const openTicket = async (ticket) => {
    setError("");
    try {
      const data = await api(`/admin/support/tickets/${ticket.id}`);
      setActiveTicket(data.ticket);
      setMessages(data.ticket?.messages || []);
      try {
        await api(`/admin/support/tickets/${ticket.id}/read`, { method: "POST" });
      } catch { /* ignore */ }
      await loadUnreadCount();
      await loadTickets(true);
    } catch (err) {
      setError(err.message || "加载工单失败");
    }
  };

  const sendMessage = async () => {
    const content = draft.trim();
    if (!content || !activeTicket?.id) return;
    setDraft("");
    setSending(true);
    try {
      const data = await api(`/admin/support/tickets/${activeTicket.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setMessages((prev) => [...prev, data.message]);
      setActiveTicket((prev) => (prev ? { ...prev, ...data.ticket } : prev));
      await loadTickets(true);
    } catch (err) {
      setError(err.message || "发送失败");
      setDraft(content);
    } finally {
      setSending(false);
    }
  };

  const markWaitingConfirmation = async () => {
    if (!activeTicket?.id) return;
    setError("");
    try {
      const data = await api(`/admin/support/tickets/${activeTicket.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "waiting_confirmation" }),
      });
      setActiveTicket((prev) => (prev ? { ...prev, ...data.ticket } : prev));
      await loadTickets(true);
    } catch (err) {
      setError(err.message || "操作失败");
    }
  };

  const markInProgress = async () => {
    if (!activeTicket?.id) return;
    try {
      const data = await api(`/admin/support/tickets/${activeTicket.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "in_progress" }),
      });
      setActiveTicket((prev) => (prev ? { ...prev, ...data.ticket } : prev));
      await loadTickets(true);
    } catch (err) {
      setError(err.message || "操作失败");
    }
  };

  const statusTone = activeTicket?.status || "";

  return (
    <div className="asc-shell">
      <div className="asc-left">
        <div className="asc-filters">
          <div className="asc-tabs">
            {STATUS_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                className={`asc-tab${filterStatus === tab.value ? " active" : ""}`}
                onClick={() => setFilterStatus(tab.value)}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="asc-filter-row">
            <select className="asc-select" value={filterService} onChange={(e) => setFilterService(e.target.value)}>
              {SERVICE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <select className="asc-select" value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
              {CATEGORY_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <input
              className="asc-input"
              placeholder="用户名"
              value={filterUsername}
              onChange={(e) => setFilterUsername(e.target.value)}
            />
          </div>
        </div>

        {error && <div className="asc-error">{error}</div>}

        <div className="asc-list">
          {loading ? (
            <div className="asc-empty">加载中...</div>
          ) : tickets.length === 0 ? (
            <div className="asc-empty">暂无工单</div>
          ) : (
            tickets.map((ticket) => (
              <button
                key={ticket.id}
                type="button"
                className={`asc-item${ticket.unread ? " asc-item--unread" : ""}${activeTicket?.id === ticket.id ? " asc-item--active" : ""}`}
                onClick={() => openTicket(ticket)}
              >
                <div className="asc-item-top">
                  <span className="asc-item-title">
                    {ticket.unread && <span className="asc-unread-dot" />}
                    {ticket.title}
                  </span>
                  <span className={`asc-status asc-status--${ticket.status}`}>{STATUS_LABELS[ticket.status] || ticket.status}</span>
                </div>
                <div className="asc-item-meta">
                  用户：{ticket.username} · {serviceLabel(ticket.service_key)} · {categoryLabel(ticket.category)}
                </div>
                <div className="asc-item-time">{formatTime(ticket.updated_at)}</div>
              </button>
            ))
          )}
        </div>
      </div>

      <div className="asc-right">
        {!activeTicket ? (
          <div className="asc-empty">选择左侧工单查看详情</div>
        ) : (
          <>
            <div className="asc-detail-head">
              <div>
                <h2 className="asc-detail-title">{activeTicket.title}</h2>
                <span className={`asc-status asc-status--${activeTicket.status}`}>{STATUS_LABELS[activeTicket.status] || activeTicket.status}</span>
              </div>
              <div className="asc-detail-actions">
                {(activeTicket.status === "pending" || activeTicket.status === "in_progress" || activeTicket.status === "unresolved") && (
                  <button type="button" className="asc-btn-primary" onClick={markWaitingConfirmation}>标记为等待用户确认</button>
                )}
                {activeTicket.status === "unresolved" && (
                  <button type="button" className="asc-btn-ghost" onClick={markInProgress}>恢复处理中</button>
                )}
              </div>
            </div>

            <div className="asc-info-card">
              <div className="asc-info-row"><span>用户</span><strong>{activeTicket.user?.nickname ? `${activeTicket.user.nickname}（${activeTicket.username}）` : activeTicket.username}</strong></div>
              <div className="asc-info-row"><span>业务</span><strong>{serviceLabel(activeTicket.service_key)}</strong></div>
              <div className="asc-info-row"><span>类型</span><strong>{categoryLabel(activeTicket.category)}</strong></div>
              <div className="asc-info-row"><span>来源页面</span><strong>{activeTicket.source_page || "-"}</strong></div>
              <div className="asc-info-row"><span>提交时间</span><strong>{formatTime(activeTicket.created_at)}</strong></div>
              <div className="asc-info-row"><span>当前状态</span><strong>{STATUS_LABELS[activeTicket.status] || activeTicket.status}</strong></div>
              {activeTicket.status === "resolved" && (
                <>
                  <div className="asc-info-row"><span>解决情况</span><strong>{activeTicket.resolved_by_user ? "用户确认已解决" : "已解决"}</strong></div>
                  {activeTicket.rating && (
                    <div className="asc-info-row"><span>评分</span><strong className="asc-stars-inline">{"★".repeat(activeTicket.rating)}{"☆".repeat(5 - activeTicket.rating)}</strong></div>
                  )}
                  {activeTicket.feedback && (
                    <div className="asc-info-row"><span>用户评价</span><strong>{activeTicket.feedback}</strong></div>
                  )}
                </>
              )}
            </div>

            <div className="asc-messages">
              {messages.map((msg) => (
                <div key={msg.id} className={`asc-msg ${msg.sender_type === "admin" ? "asc-msg--admin" : "asc-msg--user"}`}>
                  <div className="asc-msg-meta">
                    <span>{msg.sender_type === "admin" ? "客服（管理员）" : activeTicket.username}</span>
                    <span>{formatTime(msg.created_at)}</span>
                  </div>
                  <div className="asc-msg-bubble">{msg.content}</div>
                </div>
              ))}
            </div>

            <div className="asc-composer">
              <input
                className="asc-input"
                value={draft}
                placeholder="输入回复……"
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
              />
              <button type="button" className="asc-btn-primary" disabled={sending} onClick={sendMessage}>发送</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
