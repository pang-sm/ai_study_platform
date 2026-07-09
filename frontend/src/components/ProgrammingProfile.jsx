import { useEffect, useState } from "react";
import "./ProgrammingHome.css";

function maskEmail(email) {
  if (!email) return "未绑定";
  const at = email.indexOf("@");
  if (at <= 0) return email;
  return `${email.slice(0, Math.min(3, at))}***${email.slice(at)}`;
}

export default function ProgrammingProfile({ user, apiBase = "/api", setPage, onLogout }) {
  const [homeData, setHomeData] = useState(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!user?.username) return;
    fetch(`${apiBase}/programming/home?username=${encodeURIComponent(user.username)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setHomeData(data))
      .catch(() => setHomeData(null));
  }, [apiBase, user?.username]);

  const onboarding = homeData?.onboarding || {};
  const displayName = user?.nickname || user?.username || "同学";
  const planLabel = homeData?.plan_label || "免费模式";

  return (
    <div className="pp-page">
      <div className="pp-shell">
        <header className="pp-header">
          <button type="button" onClick={() => setPage?.("programmingHome")}>返回编程学习首页</button>
          <h1>编程学习 · 个人资料</h1>
        </header>

        {message && <div className="pp-message">{message}</div>}

        <section className="pp-card">
          <div className="pp-avatar">
            <span>{displayName.charAt(0).toUpperCase()}</span>
          </div>
          <div className="pp-info-grid">
            <div><span>用户名</span><strong>{user?.username || "-"}</strong></div>
            <div><span>昵称</span><strong>{displayName}</strong></div>
            <div><span>学习方向</span><strong>编程能力提升</strong></div>
            <div><span>当前套餐</span><strong>{planLabel}</strong></div>
            <div><span>主要语言</span><strong>{onboarding.main_language || "未设置"}</strong></div>
            <div><span>当前水平</span><strong>{onboarding.level || "未设置"}</strong></div>
            <div><span>遇到的问题</span><strong>{Array.isArray(onboarding.problems) && onboarding.problems.length ? onboarding.problems.join("、") : "未设置"}</strong></div>
            <div><span>绑定邮箱</span><strong>{maskEmail(user?.email)}</strong></div>
          </div>
        </section>

        <section className="pp-card">
          <div className="pp-card-head">
            <h2>账号操作</h2>
          </div>
          <div className="pp-actions">
            <button type="button" onClick={() => setMessage("基础资料编辑沿用全局账号资料，当前页面仅展示编程方向信息。")}>编辑资料</button>
            <button type="button" onClick={() => setPage?.("programmingPackageStep")}>查看套餐</button>
            <button type="button" className="is-danger" onClick={onLogout}>退出登录</button>
          </div>
        </section>
      </div>
    </div>
  );
}
