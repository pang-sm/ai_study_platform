import { useCallback, useEffect, useRef, useState } from "react";
import "./CustomerSupportModal.css";

const API_BASE = "/api";

const SERVICE_OPTIONS = [
  { value: "exam_11408", label: "11408" },
  { value: "course_learning", label: "课程学习" },
  { value: "programming", label: "编程学习" },
  { value: "account", label: "账户与会员" },
  { value: "general", label: "其他" },
];

const CATEGORY_OPTIONS = [
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

const STATUS_LABELS = {
  pending: "待处理",
  in_progress: "处理中",
  waiting_confirmation: "等待用户确认",
  resolved: "已解决",
  unresolved: "未解决",
  closed: "已关闭",
};

function serviceLabel(value) {
  return SERVICE_OPTIONS.find((item) => item.value === value)?.label || "其他";
}

function categoryLabel(value) {
  return CATEGORY_OPTIONS.find((item) => item.value === value)?.label || "其他";
}

function formatTime(value) {
  if (!value) return "";
  const text = String(value).trim();
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(text);
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !hasTz ? `${text}Z` : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export default function CustomerSupportModal({ user, defaultServiceKey = "general", sourcePage = "", onClose }) {
  const [view, setView] = useState("list"); // list | form | chat
  const [tickets, setTickets] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeTicket, setActiveTicket] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");

  // new-ticket form
  const [form, setForm] = useState({
    serviceKey: defaultServiceKey,
    category: "functional_bug",
    title: "",
    description: "",
  });
  const [submitting, setSubmitting] = useState(false);

  // resolution
  const [resolveMode, setResolveMode] = useState(""); // "" | "rating" | "unresolved"
  const [rating, setRating] = useState(0);
  const [ratingHover, setRatingHover] = useState(0);
  const [feedback, setFeedback] = useState("");
  const [unresolvedMsg, setUnresolvedMsg] = useState("");
  const [resolving, setResolving] = useState(false);

  const sourceUrlRef = useRef("");
  if (!sourceUrlRef.current) sourceUrlRef.current = window.location.pathname;

  const viewRef = useRef(view);
  viewRef.current = view;
  const activeTicketRef = useRef(activeTicket);
  activeTicketRef.current = activeTicket;

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
      const data = await api("/support/unread-count");
      setUnreadCount(Number(data.count || 0));
    } catch {
      /* ignore polling errors */
    }
  }, [api]);

  const loadTickets = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await api("/support/tickets");
      setTickets(data.tickets || []);
      setError("");
    } catch (err) {
      if (!silent) setError(err.message || "加载客服记录失败");
    } finally {
      if (!silent) setLoading(false);
    }
  }, [api]);

  const refreshActiveTicket = useCallback(async (silent = false) => {
    const ticket = activeTicketRef.current;
    if (!ticket?.id) return;
    try {
      const data = await api(`/support/tickets/${ticket.id}`);
      setActiveTicket(data.ticket);
      setMessages(data.ticket?.messages || []);
    } catch {
      /* ignore transient polling errors */
    }
  }, [api]);

  useEffect(() => {
    loadTickets();
    loadUnreadCount();
    const id = setInterval(() => {
      loadUnreadCount();
      if (viewRef.current === "list") loadTickets(true);
      if (viewRef.current === "chat") refreshActiveTicket(true);
    }, 6000);
    return () => clearInterval(id);
  }, [loadTickets, loadUnreadCount, refreshActiveTicket]);

  const openTicket = async (ticket) => {
    setError("");
    try {
      const data = await api(`/support/tickets/${ticket.id}`);
      setActiveTicket(data.ticket);
      setMessages(data.ticket?.messages || []);
      setView("chat");
      setResolveMode("");
      setFeedback("");
      setUnresolvedMsg("");
      // Mark the ticket read so the unread badge drops.
      try {
        await api(`/support/tickets/${ticket.id}/read`, { method: "POST" });
      } catch { /* ignore */ }
      await loadUnreadCount();
      await loadTickets(true);
    } catch (err) {
      setError(err.message || "加载工单失败");
    }
  };

  const openForm = () => {
    setForm((prev) => ({
      ...prev,
      serviceKey: prev.serviceKey || defaultServiceKey || "general",
      category: "functional_bug",
      title: "",
      description: "",
    }));
    setError("");
    setView("form");
  };

  const submitNewTicket = async () => {
    const description = (form.description || "").trim();
    if (!description) {
      setError("请填写问题描述");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const data = await api("/support/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_key: form.serviceKey,
          category: form.category,
          title: form.title.trim(),
          description,
          source_url: sourceUrlRef.current,
          source_page: sourcePage || serviceLabel(form.serviceKey),
        }),
      });
      await loadTickets(true);
      setSubmitting(false);
      await openTicket(data.ticket);
    } catch (err) {
      setError(err.message || "提交失败");
      setSubmitting(false);
    }
  };

  const sendMessage = async () => {
    const content = draft.trim();
    if (!content || !activeTicket?.id) return;
    setDraft("");
    try {
      const data = await api(`/support/tickets/${activeTicket.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setMessages((prev) => [...prev, data.message]);
      setActiveTicket((prev) => (prev ? { ...prev, status: prev.status } : prev));
      await refreshActiveTicket(true);
    } catch (err) {
      setError(err.message || "发送失败");
      setDraft(content);
    }
  };

  const submitResolution = async (resolved) => {
    if (!activeTicket?.id) return;
    if (resolved && rating < 1) {
      setError("请先选择评分");
      return;
    }
    setResolving(true);
    setError("");
    try {
      await api(`/support/tickets/${activeTicket.id}/confirm-resolution`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resolved,
          rating: resolved ? rating : null,
          feedback: resolved ? feedback.trim() : "",
          message: resolved ? "" : unresolvedMsg.trim(),
        }),
      });
      setResolveMode("");
      setFeedback("");
      setUnresolvedMsg("");
      await refreshActiveTicket();
      await loadTickets(true);
    } catch (err) {
      setError(err.message || "提交失败");
    } finally {
      setResolving(false);
    }
  };

  const backToList = () => {
    setView("list");
    setActiveTicket(null);
    setMessages([]);
    setResolveMode("");
    loadTickets();
    loadUnreadCount();
  };

  const headerTitle = view === "chat" ? (activeTicket?.title || "工单详情") : "客服支持";

  return (
    <div className="csm-backdrop" onClick={onClose}>
      <div className="csm-modal" onClick={(event) => event.stopPropagation()}>
        <div className="csm-header">
          <div>
            <h2 className="csm-title">{headerTitle}</h2>
            <p className="csm-subtitle">
              {view === "chat"
                ? "与客服的对话记录"
                : "遇到问题？提交反馈后，管理员会在这里回复你。"}
            </p>
          </div>
          <button type="button" className="csm-close" onClick={onClose} aria-label="关闭">×</button>
        </div>

        {error && <div className="csm-error">{error}</div>}

        {view === "list" && (
          <div className="csm-body">
            {unreadCount > 0 && (
              <div className="csm-unread-banner">管理员有 {unreadCount} 条新回复</div>
            )}
            <button type="button" className="csm-primary" onClick={openForm}>
              发起新问题
            </button>

            <div className="csm-section-title">我的问题</div>
            {loading ? (
              <div className="csm-empty">加载中...</div>
            ) : tickets.length === 0 ? (
              <div className="csm-empty">还没有客服记录</div>
            ) : (
              <div className="csm-ticket-list">
                {tickets.map((ticket) => (
                  <button
                    key={ticket.id}
                    type="button"
                    className={`csm-ticket${ticket.unread ? " csm-ticket--unread" : ""}`}
                    onClick={() => openTicket(ticket)}
                  >
                    <div className="csm-ticket-top">
                      <span className="csm-ticket-title">{ticket.title}</span>
                      {ticket.unread && <span className="csm-dot" />}
                    </div>
                    <div className="csm-ticket-meta">
                      <span className={`csm-status csm-status--${ticket.status}`}>
                        {STATUS_LABELS[ticket.status] || ticket.status}
                      </span>
                      <span className="csm-ticket-time">{formatTime(ticket.updated_at)}</span>
                    </div>
                    {ticket.last_message?.content && (
                      <div className="csm-ticket-preview">
                        {ticket.last_message.sender_type === "admin" ? "客服： " : "我： "}
                        {ticket.last_message.content}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {view === "form" && (
          <div className="csm-body">
            <div className="csm-field">
              <label className="csm-label">问题所属业务</label>
              <select
                className="csm-input"
                value={form.serviceKey}
                onChange={(event) => setForm((prev) => ({ ...prev, serviceKey: event.target.value }))}
              >
                {SERVICE_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>

            <div className="csm-field">
              <label className="csm-label">问题类型</label>
              <select
                className="csm-input"
                value={form.category}
                onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}
              >
                {CATEGORY_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>

            <div className="csm-field">
              <label className="csm-label">问题标题（可选）</label>
              <input
                className="csm-input"
                value={form.title}
                placeholder="简单概括你的问题"
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              />
            </div>

            <div className="csm-field">
              <label className="csm-label">问题描述 <span className="csm-required">*</span></label>
              <textarea
                className="csm-textarea"
                rows={4}
                value={form.description}
                placeholder="请描述你遇到的问题"
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              />
            </div>

            <div className="csm-actions">
              <button type="button" className="csm-ghost" onClick={backToList}>返回</button>
              <button type="button" className="csm-primary" disabled={submitting} onClick={submitNewTicket}>
                {submitting ? "提交中..." : "提交工单"}
              </button>
            </div>
          </div>
        )}

        {view === "chat" && activeTicket && (
          <div className="csm-body csm-chat-body">
            <div className="csm-chat-head">
              <button type="button" className="csm-back" onClick={backToList}>← 我的问题</button>
              <span className={`csm-status csm-status--${activeTicket.status}`}>
                {STATUS_LABELS[activeTicket.status] || activeTicket.status}
              </span>
            </div>

            <div className="csm-messages">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`csm-msg ${msg.sender_type === "user" ? "csm-msg--user" : "csm-msg--admin"}`}
                >
                  <div className="csm-msg-meta">
                    <span>{msg.sender_type === "user" ? "我" : "客服"}</span>
                    <span>{formatTime(msg.created_at)}</span>
                  </div>
                  <div className="csm-msg-bubble">{msg.content}</div>
                </div>
              ))}

              {activeTicket.status === "waiting_confirmation" && resolveMode === "" && (
                <div className="csm-resolution">
                  <p className="csm-resolution-text">客服认为该问题已经处理完成，请确认问题是否解决。</p>
                  <div className="csm-resolution-actions">
                    <button type="button" className="csm-primary" onClick={() => setResolveMode("rating")}>已解决</button>
                    <button type="button" className="csm-ghost" onClick={() => setResolveMode("unresolved")}>仍未解决</button>
                  </div>
                </div>
              )}

              {resolveMode === "rating" && (
                <div className="csm-resolution">
                  <p className="csm-resolution-text">本次客服体验如何？</p>
                  <div className="csm-stars">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        className="csm-star"
                        onMouseEnter={() => setRatingHover(star)}
                        onMouseLeave={() => setRatingHover(0)}
                        onClick={() => setRating(star)}
                      >
                        {star <= (ratingHover || rating) ? "★" : "☆"}
                      </button>
                    ))}
                  </div>
                  <textarea
                    className="csm-textarea"
                    rows={2}
                    value={feedback}
                    placeholder="补充评价（可选）"
                    onChange={(event) => setFeedback(event.target.value)}
                  />
                  <div className="csm-resolution-actions">
                    <button type="button" className="csm-ghost" onClick={() => setResolveMode("")}>取消</button>
                    <button type="button" className="csm-primary" disabled={resolving} onClick={() => submitResolution(true)}>
                      {resolving ? "提交中..." : "提交评价"}
                    </button>
                  </div>
                </div>
              )}

              {resolveMode === "unresolved" && (
                <div className="csm-resolution">
                  <p className="csm-resolution-text">还有什么问题？请补充说明。</p>
                  <textarea
                    className="csm-textarea"
                    rows={2}
                    value={unresolvedMsg}
                    placeholder="请描述仍未解决的问题"
                    onChange={(event) => setUnresolvedMsg(event.target.value)}
                  />
                  <div className="csm-resolution-actions">
                    <button type="button" className="csm-ghost" onClick={() => setResolveMode("")}>取消</button>
                    <button type="button" className="csm-primary" disabled={resolving} onClick={() => submitResolution(false)}>
                      {resolving ? "提交中..." : "提交"}
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="csm-composer">
              <input
                className="csm-input"
                value={draft}
                placeholder="输入消息……"
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    sendMessage();
                  }
                }}
              />
              <button type="button" className="csm-primary" onClick={sendMessage}>发送</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
