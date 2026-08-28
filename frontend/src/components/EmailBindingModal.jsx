import { useEffect, useState } from "react";

function maskEmailLocal(email) {
  if (!email) return "";
  const at = email.indexOf("@");
  if (at <= 0) return email;
  const name = email.slice(0, at);
  const domain = email.slice(at);
  if (name.length <= 3) return name.slice(0, 1) + "***" + domain;
  return name.slice(0, 3) + "****" + domain;
}

function detailMessage(data) {
  const d = data?.detail;
  if (d && typeof d === "object" && d.message) return d.message;
  if (typeof d === "string" && d) return d;
  return null;
}

/**
 * Shared "bind email once" modal. Reused by 11408 / course-learning / programming
 * profiles. Email can only be bound once; after a verified bind the parent hides
 * this modal entirely and the backend rejects any further bind attempt.
 */
export default function EmailBindingModal({ open, user, apiBase = "/api", onClose, onBound }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sending, setSending] = useState(false);
  const [binding, setBinding] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [countdown, setCountdown] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);

  useEffect(() => {
    if (open) {
      setEmail("");
      setCode("");
      setError("");
      setMsg("");
      setConfirmOpen(false);
      setCountdown(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open || countdown <= 0) return;
    const timer = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [open, countdown]);

  const sendCode = async () => {
    if (!email.trim() || !email.includes("@") || !email.split("@")[1].includes(".")) {
      setError("请输入有效的邮箱地址");
      return;
    }
    setSending(true);
    setError("");
    setMsg("");
    try {
      const res = await fetch(`${apiBase}/me/email/send-code?username=${encodeURIComponent(user?.username || "")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data) || "验证码发送失败");
      setMsg("验证码已发送");
      setCountdown(59);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  };

  const doBind = async () => {
    setBinding(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/me/email/verify?username=${encodeURIComponent(user?.username || "")}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), code: code.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(detailMessage(data) || "邮箱绑定失败");
      setConfirmOpen(false);
      onBound?.(email.trim());
      onClose?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBinding(false);
    }
  };

  const requestConfirm = () => {
    if (!email.trim() || !email.includes("@")) {
      setError("请输入有效的邮箱地址");
      return;
    }
    if (!/^\d{6}$/.test(code.trim())) {
      setError("请输入 6 位数字验证码");
      return;
    }
    setConfirmOpen(true);
  };

  if (!open) return null;

  return (
    <>
      <div className="eh-modal-backdrop" onClick={() => !binding && onClose?.()}>
        <div className="eh-modal" onClick={(e) => e.stopPropagation()}>
          <div className="eh-modal-head">
            <h3>绑定邮箱</h3>
            <button type="button" className="eh-modal-close" onClick={onClose}>×</button>
          </div>
          <div className="email-once-notice">注意：邮箱仅可绑定一次，绑定成功后不可更换，请确认邮箱填写正确。</div>
          {error && <div className="ob-error" style={{ marginBottom: 12 }}>{error}</div>}
          {msg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{msg}</div>}
          <label className="ob-label">邮箱地址</label>
          <input className="ep-modal-input" style={{ marginBottom: 14 }} value={email} placeholder="请输入邮箱地址" onChange={(e) => setEmail(e.target.value)} />
          <label className="ob-label">验证码</label>
          <div className="ob-row" style={{ marginBottom: 16 }}>
            <input className="ep-modal-input" style={{ flex: 1 }} value={code} placeholder="6 位数字验证码" maxLength={6} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />
            <button type="button" className="ob-btn-secondary" style={{ width: 120, height: 44, flexShrink: 0 }} onClick={sendCode} disabled={sending || countdown > 0}>
              {sending ? "发送中..." : countdown > 0 ? `${countdown}s 后重发` : "发送验证码"}
            </button>
          </div>
          <div className="eh-modal-actions">
            <button type="button" className="ob-btn-secondary" onClick={onClose}>取消</button>
            <button type="button" className="ob-btn-primary" onClick={requestConfirm}>确认绑定</button>
          </div>
        </div>
      </div>

      {confirmOpen && (
        <div className="eh-modal-backdrop" onClick={() => !binding && setConfirmOpen(false)}>
          <div className="eh-modal" onClick={(e) => e.stopPropagation()}>
            <div className="eh-modal-head"><h3>确认绑定此邮箱？</h3></div>
            <p style={{ color: "#475569", fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>{maskEmailLocal(email)}</p>
            <p style={{ color: "#64748b", fontSize: 13, lineHeight: 1.6, margin: "0 0 20px" }}>邮箱绑定成功后不可自行更换或解绑，请确认邮箱地址无误。</p>
            <div className="eh-modal-actions">
              <button type="button" className="ob-btn-secondary" onClick={() => setConfirmOpen(false)}>返回检查</button>
              <button type="button" className="ob-btn-primary" onClick={doBind} disabled={binding}>{binding ? "绑定中..." : "确认绑定"}</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
