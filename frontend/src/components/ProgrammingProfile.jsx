import { useEffect, useRef, useState } from "react";
import { switchLearningDirection } from "../utils/serviceSwitch.js";
import { resolveMediaUrl } from "../utils/mediaUrl.js";
import EmailBindingModal from "./EmailBindingModal.jsx";
import CustomerSupportModal from "./CustomerSupportModal.jsx";
import FirstTimeGuideLauncher from "./FirstTimeGuideLauncher.jsx";
import { PROGRAMMING_GUIDE_STEPS } from "./firstTimeGuideFlows.js";
import "./ProgrammingHome.css";

// Fallback only — the authoritative plan name/limit come from the backend
// (/programming/entitlements + /programming/home), which read the unified
// Programming Plan Catalog. Do NOT add plan-specific quota numbers here.
const PROGRAMMING_PLAN_LABELS = {
  free: "免费版",
  monthly: "编程进阶月卡",
  quarterly: "实验与算法强化季卡",
  full: "编程全能年卡",
};
const GRADE_OPTIONS = ["大一", "大二", "大三", "大四", "研究生"];
const SEMESTER_OPTIONS = ["上学期", "下学期"];

// Phone verification backend is reserved for future commercial deployment.
// Production UI is currently disabled because SMS provider credentials /
// enterprise SMS qualification are not available.
const PHONE_BINDING_UI_ENABLED = false;

function maskEmail(email) {
  if (!email) return "";
  const at = email.indexOf("@");
  if (at <= 0) return email;
  const name = email.slice(0, at);
  const domain = email.slice(at);
  if (name.length <= 3) return `${name.slice(0, 1)}***${domain}`;
  return `${name.slice(0, 3)}***${domain}`;
}

function formatAiQuota(remaining, limit) {
  return `${remaining ?? 0} / ${limit ?? 0}`;
}

export default function ProgrammingProfile({ user, apiBase = "/api", setPage, onLogout, onProfileUpdate, onReplayGuide }) {
  const [homeData, setHomeData] = useState(null);
  const [showSupport, setShowSupport] = useState(false);
  const [entitlements, setEntitlements] = useState(null);
  const [servicePlans, setServicePlans] = useState(() => user?.service_plans || {});
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [nickname, setNickname] = useState(user?.nickname || "");
  const [major, setMajor] = useState(user?.major || "");
  const [grade, setGrade] = useState(user?.grade || "");
  const [semester, setSemester] = useState(user?.semester || "");
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");
  const avatarInputRef = useRef(null);

  useEffect(() => {
    if (!editing) {
      setNickname(user?.nickname || "");
      setMajor(user?.major || "");
      setGrade(user?.grade || "");
      setSemester(user?.semester || "");
    }
  }, [user?.nickname, user?.major, user?.grade, user?.semester, editing]);

  const fetchProgrammingProfileData = async () => {
    if (!user?.username) return;
    try {
      const response = await fetch(`${apiBase}/programming/home?username=${encodeURIComponent(user.username)}`);
      const data = await response.json().catch(() => ({}));
      if (response.ok) setHomeData(data);
    } catch {
      // Keep the current snapshot when the dashboard endpoint is temporarily unavailable.
    }
    try {
      const response = await fetch(`${apiBase}/programming/entitlements?username=${encodeURIComponent(user.username)}`);
      const data = await response.json().catch(() => ({}));
      if (response.ok) setEntitlements(data);
    } catch {
      // Entitlements are also present in /programming/home as quota fallback.
    }
    try {
      const response = await fetch(`${apiBase}/me`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.user?.service_plans) setServicePlans(data.user.service_plans);
    } catch {
      // Use profile service plans already loaded at login.
    }
  };

  useEffect(() => {
    fetchProgrammingProfileData();
  }, [apiBase, user?.username]);

  const onboarding = homeData?.onboarding || {};
  const quota = homeData?.quota || {};
  const permissions = entitlements?.permissions || {};
  const plan = entitlements?.plan || homeData?.plan || servicePlans?.programming?.plan || "free";
  const planLabel =
    entitlements?.plan_label ||
    homeData?.plan_label ||
    servicePlans?.programming?.plan_label ||
    PROGRAMMING_PLAN_LABELS[plan] ||
    "免费版";
  const displayName = nickname || user?.nickname || user?.username || "同学";
  const username = user?.username || "";
  const displayGrade = grade || onboarding?.grade || "未设置";
  const registerTime = user?.created_at || "";
  const realEmail = user?.email || "";
  const emailDisplay = realEmail ? maskEmail(realEmail) : "未绑定";
  const emailBtnLabel = realEmail ? "修改" : "绑定";
  const avatarSrc = resolveMediaUrl(user?.avatar_url, apiBase);
  const problemRecordsEnabled = Boolean(permissions.problem_records);

  const quotaItems = [
    {
      label: "AI 问答 / 纠错额度",
      value: formatAiQuota(quota.ai_chat?.remaining, quota.ai_chat?.limit ?? permissions.ai_chat_daily_limit),
      unit: "次 / 每天",
      sub: `今日已使用 ${quota.ai_chat?.used ?? 0} 次`,
    },
    {
      label: "AI 出题额度",
      value: `${quota.ai_question?.remaining ?? 0} / ${quota.ai_question?.limit ?? permissions.ai_question_daily_limit ?? 0}`,
      unit: "次 / 每天",
      sub: `今日已使用 ${quota.ai_question?.used ?? 0} 次`,
    },
    {
      label: "题目记录",
      value: problemRecordsEnabled ? "已开通" : "未开通",
      unit: "",
      sub: problemRecordsEnabled ? "当前套餐可保存题目记录" : "升级后可用",
    },
    {
      label: "当前编程语言",
      value: onboarding.main_language || "未设置",
      unit: "",
      sub: "来自编程学习详情",
    },
    {
      label: "当前学习水平",
      value: onboarding.level || "未设置",
      unit: "",
      sub: "来自编程学习详情",
    },
  ];

  const packageBenefits = entitlements?.benefits?.length
    ? entitlements.benefits.filter((benefit) => !/文件库|file library/i.test(benefit.label || "")).map((benefit) => ({
        label: benefit.limit ? `${benefit.label} ${benefit.limit}${benefit.unit ? ` ${benefit.unit}` : ""}` : benefit.label,
        enabled: Boolean(benefit.enabled),
      }))
    : [
        { label: `AI 问答 / 纠错 ${quota.ai_chat?.limit ?? permissions.ai_chat_daily_limit ?? 0} 次 / 每天`, enabled: true },
        { label: `AI 出题 ${quota.ai_question?.limit ?? permissions.ai_question_daily_limit ?? 0} 次 / 每天`, enabled: true },
        { label: "题目记录", enabled: problemRecordsEnabled },
      ];

  const switchTrack = async (targetTrack) => {
    setActionErr("");
    await switchLearningDirection({
      targetTrack,
      user,
      apiBase,
      setPage,
      onError: setActionErr,
      onPlansUpdate: setServicePlans,
      returnPage: "programmingHome",
    });
  };

  const uploadAvatar = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    event.target.value = "";
    setAvatarUploading(true);
    setActionErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("username", user.username);
      const response = await fetch(`${apiBase}/me/avatar`, { method: "POST", body: fd });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "头像上传失败");
      if (data.profile) onProfileUpdate?.(data.profile);
      setActionMsg("头像已更新");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (error) {
      setActionErr(error.message || "头像上传失败");
    } finally {
      setAvatarUploading(false);
    }
  };

  const saveBasicInfo = async () => {
    setActionErr("");
    try {
      const response = await fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, major, grade, semester }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "保存失败");
      if (data.profile) onProfileUpdate?.(data.profile);
      setEditing(false);
      setActionMsg("资料已保存");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (error) {
      setActionErr(error.message || "保存失败");
    }
  };

  const [pwdModal, setPwdModal] = useState(false);
  const [pwdForm, setPwdForm] = useState({ old_password: "", new_password: "", confirm_password: "" });
  const [pwdSaving, setPwdSaving] = useState(false);
  const [pwdErr, setPwdErr] = useState("");
  const openPwdModal = () => {
    setPwdForm({ old_password: "", new_password: "", confirm_password: "" });
    setPwdErr("");
    setPwdModal(true);
  };
  const changePassword = async () => {
    setPwdErr("");
    if (pwdForm.new_password !== pwdForm.confirm_password) {
      setPwdErr("新密码和确认密码不一致");
      return;
    }
    setPwdSaving(true);
    try {
      const response = await fetch(`${apiBase}/me/password?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pwdForm),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "密码修改失败");
      setPwdModal(false);
      setActionMsg("密码修改成功");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (error) {
      setPwdErr(error.message || "密码修改失败");
    } finally {
      setPwdSaving(false);
    }
  };

  const [emailModal, setEmailModal] = useState(false);
  const [emailForm, setEmailForm] = useState({ email: "", code: "" });
  const [emailSending, setEmailSending] = useState(false);
  const [emailBinding, setEmailBinding] = useState(false);
  const [emailErr, setEmailErr] = useState("");
  const [emailMsg, setEmailMsg] = useState("");
  const openEmailModal = () => {
    setEmailForm({ email: "", code: "" });
    setEmailErr("");
    setEmailMsg("");
    setEmailModal(true);
  };
  const sendEmailCode = async () => {
    const email = emailForm.email.trim();
    if (!email) {
      setEmailErr("请输入邮箱地址");
      return;
    }
    setEmailSending(true);
    setEmailErr("");
    setEmailMsg("");
    try {
      const response = await fetch(`${apiBase}/me/email/send-code?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "验证码发送失败");
      setEmailMsg("验证码已发送");
    } catch (error) {
      setEmailErr(error.message || "验证码发送失败");
    } finally {
      setEmailSending(false);
    }
  };
  const bindEmail = async () => {
    setEmailBinding(true);
    setEmailErr("");
    setEmailMsg("");
    try {
      const response = await fetch(`${apiBase}/me/email/verify?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailForm.email.trim(), code: emailForm.code.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "邮箱绑定失败");
      setEmailModal(false);
      setActionMsg("邮箱已绑定");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (error) {
      setEmailErr(error.message || "邮箱绑定失败");
    } finally {
      setEmailBinding(false);
    }
  };

  return (
    <div className="ep-page-wrap">
      <div className="ep-shell" data-guide-id="programming-profile">
        <div className="ep-header">
          <button type="button" className="ep-outline-btn" onClick={() => setPage?.("programmingHome")}>返回编程学习主页</button>
          <h1 className="ep-title">编程学习 · 个人中心</h1>
        </div>

        {actionMsg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{actionMsg}</div>}
        {actionErr && <div className="admin-dashboard-error" style={{ marginBottom: 12 }}>{actionErr}</div>}

        <div className="ep-card">
          <div className="ep-card-head">
            <h2>基础信息</h2>
            <button type="button" className="ep-outline-btn" onClick={() => (editing ? saveBasicInfo() : setEditing(true))}>
              {editing ? "保存资料" : "编辑资料"}
            </button>
          </div>
          <div className="ep-basic-grid">
            <div className="ep-avatar-col">
              <div className="ep-avatar-wrap">
                {avatarSrc ? <img src={avatarSrc} alt="头像" className="ep-avatar-img" /> : <span className="ep-avatar-text">{displayName.charAt(0)}</span>}
              </div>
              <input ref={avatarInputRef} type="file" accept="image/jpeg,image/png,image/webp" className="apv2-avatar-input" onChange={uploadAvatar} />
              <button type="button" className="ep-avatar-btn" onClick={() => avatarInputRef.current?.click()} disabled={avatarUploading}>
                {avatarUploading ? "上传中..." : "更换头像"}
              </button>
            </div>
            <div className="ep-info-col">
              <div className="ep-info-row"><span className="ep-info-label">用户名</span><span>{username}</span></div>
              <div className="ep-info-row">
                <span className="ep-info-label">昵称</span>
                {editing ? <input className="ep-info-input" value={nickname} onChange={(event) => setNickname(event.target.value)} /> : <span>{displayName}</span>}
              </div>
              <div className="ep-info-row"><span className="ep-info-label">专业</span>{editing ? <input className="ep-info-input" value={major} onChange={(event) => setMajor(event.target.value)} maxLength={50} /> : <span>{major || "未设置"}</span>}</div>
              <div className="ep-info-row"><span className="ep-info-label">学习方向</span><span className="ep-info-tag">编程能力提升</span></div>
              <div className="ep-info-row"><span className="ep-info-label">当前套餐</span><span>{planLabel}</span></div>
            </div>
            <div className="ep-info-col">
              <div className="ep-info-row"><span className="ep-info-label">年级</span>{editing ? <select className="ep-info-input" value={grade} onChange={(event) => setGrade(event.target.value)}><option value="">未设置</option>{GRADE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <span>{displayGrade}</span>}</div>
              <div className="ep-info-row"><span className="ep-info-label">当前学期</span>{editing ? <select className="ep-info-input" value={semester} onChange={(event) => setSemester(event.target.value)}><option value="">未设置</option>{SEMESTER_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <span>{semester || "未设置"}</span>}</div>
              <div className="ep-info-row"><span className="ep-info-label">主要语言</span><span>{onboarding.main_language || "未设置"}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">当前水平</span><span>{onboarding.level || "未设置"}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">注册时间</span><span className="ep-info-time">{registerTime || "未记录"}</span></div>
            </div>
          </div>
        </div>

        <div className="ep-card">
          <div className="ep-card-head">
            <h2>编程学习概览 <span className="ep-help-icon" title="编程方向的真实功能与额度">?</span></h2>
            <div className="ep-switch-btns">
              <button type="button" className="ep-outline-btn" onClick={() => switchTrack("exam_408")}>切换到 11408</button>
              <button type="button" className="ep-outline-btn" onClick={() => switchTrack("university_course")}>切换到课程学习</button>
            </div>
          </div>
          <div className="ep-quota-grid">
            {quotaItems.map((item) => (
              <div key={item.label} className="ep-quota-item">
                <span className="ep-quota-label">{item.label}</span>
                <strong className="ep-quota-value">{item.value}{item.unit ? <small> {item.unit}</small> : null}</strong>
                <span className="ep-quota-sub">{item.sub}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="ep-card">
          <div className="ep-card-head"><h2>帮助与引导</h2></div>
          <div className="ep-sec-item">
            <div><strong>新手引导</strong><p>重新查看编程学习方向的功能介绍，不会重置首次自动展示状态。</p></div>
            <button type="button" className="ep-outline-btn" onClick={onReplayGuide}>重新查看</button>
          </div>
        </div>

        <div className="ep-card">
          <div className="ep-card-head"><h2>账号安全</h2></div>
          <div className="ep-security-grid">
            <div className="ep-sec-item">
              <div><strong>登录密码</strong><p>用于登录账号的密码</p><span>********</span></div>
              <button type="button" className="ep-outline-btn" onClick={openPwdModal}>修改</button>
            </div>
            {PHONE_BINDING_UI_ENABLED && (
              <div className="ep-sec-item">
                <div><strong>绑定手机号</strong><p>用于接收验证码和安全验证</p><span>{user?.phone || "未绑定"}</span></div>
              </div>
            )}
            <div className="ep-sec-item">
              <div><strong>邮箱</strong><span>{emailDisplay}</span>{user?.email_verified && <em className="ep-verified-tag">已验证</em>}</div>
              {!user?.email_verified && (
                <button type="button" className="ep-outline-btn" onClick={openEmailModal}>绑定邮箱</button>
              )}
            </div>
            <div className="ep-sec-item ep-sec-item--logout">
              <div><strong>退出登录</strong><p>退出后需要重新登录才能访问</p></div>
              <button type="button" className="ep-logout-btn" onClick={onLogout}>退出登录</button>
            </div>
          </div>
        </div>

        <div className="ep-card">
          <div className="ep-card-head"><h2>我的套餐</h2></div>
          <div className="ep-package-row">
            <div className="ep-package-badge-col"><div className="ep-package-badge-icon">P</div></div>
            <div className="ep-package-info">
              <span className="ep-package-section-label">当前编程套餐</span>
              <div className="ep-package-name-row"><strong>{planLabel}</strong></div>
            </div>
            <div className="ep-package-perks">
              <span className="ep-package-section-label">套餐权益</span>
              <ul className="ep-perks-list">
                {packageBenefits.map((benefit, index) => (
                  <li key={`${benefit.label}-${index}`} className={benefit.enabled ? "" : "ep-perk--off"}>
                    <span className="ep-perk-check">{benefit.enabled ? "✓" : "!"}</span> {benefit.label}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ep-package-action">
              <button
                type="button"
                className="ep-outline-btn"
                onClick={() => setPage?.("membership", {
                  serviceKey: "programming",
                  profilePage: "programmingProfile",
                  returnPage: "programmingHome",
                })}
              >查看套餐详情</button>
            </div>
          </div>
        </div>

        <p className="ep-footer">如有疑问，请联系<span className="ep-footer-link" role="button" tabIndex={0} onClick={() => setShowSupport(true)}>客服支持</span></p>
      </div>

      {pwdModal && (
        <div className="eh-modal-backdrop" onClick={() => setPwdModal(false)}>
          <div className="eh-modal" onClick={(event) => event.stopPropagation()}>
            <div className="eh-modal-head"><h3>修改密码</h3><button type="button" className="eh-modal-close" onClick={() => setPwdModal(false)}>×</button></div>
            {pwdErr && <div className="ob-error" style={{ marginBottom: 12 }}>{pwdErr}</div>}
            <label className="ob-label">当前密码</label>
            <input type="password" className="ep-modal-input" style={{ marginBottom: 14 }} value={pwdForm.old_password} placeholder="请输入当前密码" onChange={(event) => setPwdForm((prev) => ({ ...prev, old_password: event.target.value }))} />
            <label className="ob-label">新密码</label>
            <input type="password" className="ep-modal-input" style={{ marginBottom: 14 }} value={pwdForm.new_password} placeholder="请输入新密码" onChange={(event) => setPwdForm((prev) => ({ ...prev, new_password: event.target.value }))} />
            <label className="ob-label">确认新密码</label>
            <input type="password" className="ep-modal-input" style={{ marginBottom: 16 }} value={pwdForm.confirm_password} placeholder="请再次输入新密码" onChange={(event) => setPwdForm((prev) => ({ ...prev, confirm_password: event.target.value }))} />
            <div className="eh-modal-actions">
              <button type="button" className="ob-btn-secondary" onClick={() => setPwdModal(false)}>取消</button>
              <button type="button" className="ob-btn-primary" onClick={changePassword} disabled={pwdSaving}>{pwdSaving ? "修改中..." : "确认修改"}</button>
            </div>
          </div>
        </div>
      )}

      <EmailBindingModal
        open={emailModal}
        user={user}
        apiBase={apiBase}
        onClose={() => setEmailModal(false)}
        onBound={(email) => onProfileUpdate?.({ email, email_verified: true })}
      />

      {showSupport && (
        <CustomerSupportModal
          user={user}
          defaultServiceKey="programming"
          sourcePage="编程学习 / 个人主页"
          onClose={() => setShowSupport(false)}
        />
      )}
      <FirstTimeGuideLauncher
        serviceKey="programming"
        serviceLabel="编程学习"
        steps={PROGRAMMING_GUIDE_STEPS}
        apiBase={apiBase}
        ready={false}
        onStepChange={(index, step, direction) => {
          // Only the last step (个人中心) lives on this page; going back returns
          // to the ProgrammingHome where the previous step's real page renders.
          if (direction === "previous") setPage?.("programmingHome");
        }}
        onComplete={() => {
          // 结束引导后回到正常编程学习首页（重置内部 nav 状态 + URL）。
          try { localStorage.removeItem("ai_study_programming_active_nav"); } catch { /* ignore */ }
          const courseId = (window.location.pathname.match(/^\/programming\/([^/]+)/) || [])[1] || "python_programming";
          window.location.assign(`/programming/${courseId}/home`);
        }}
      />
    </div>
  );
}
