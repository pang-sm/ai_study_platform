import { useEffect, useRef, useState } from "react";
import { switchLearningDirection } from "../utils/serviceSwitch.js";

const PACKAGE_LABELS = {
  free: "免费模式",
  monthly: "月度包",
  quarterly: "季度包",
  full: "全程包",
};

function maskEmail(email) {
  if (!email) return "";
  const at = email.indexOf("@");
  if (at <= 0) return email;
  const name = email.slice(0, at);
  const domain = email.slice(at);
  if (name.length <= 3) return name.slice(0, 1) + "***" + domain;
  return name.slice(0, 3) + "***" + domain;
}

export default function CourseLearningProfile({ user, setPage, onLogout, API_BASE }) {
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [nickname, setNickname] = useState(user?.nickname || "");
  const [courseTrack, setCourseTrack] = useState(() =>
    (user?.tracks || []).find((t) => t.track_type === "university_course") || null
  );
  const [quotaData, setQuotaData] = useState(null);
  const [courseCount, setCourseCount] = useState(0);
  const [servicePlans, setServicePlans] = useState(() => user?.service_plans || {});
  const [courseEntitlements, setCourseEntitlements] = useState(null);
  const avatarInputRef = useRef(null);

  const servicePlan = servicePlans?.course_learning?.plan || user?.service_plans?.course_learning?.plan || "free";
  const pkgType = courseEntitlements?.plan || servicePlan || courseTrack?.package_type || "free";
  const permissions = courseEntitlements?.permissions || courseTrack?.permissions || {};
  const onboardingDetail = (() => {
    try {
      if (courseTrack?.onboarding_detail) return courseTrack.onboarding_detail;
      const d = user?.onboarding_detail;
      if (!d) return null;
      return typeof d === "string" ? JSON.parse(d) : d;
    } catch { return null; }
  })();

  const displayPkg = courseEntitlements?.plan_label || PACKAGE_LABELS[pkgType] || "免费模式";
  const entitlementQuota = courseEntitlements || {};
  const chatLimit = permissions.ai_chat_daily_limit ?? entitlementQuota?.feature_limits?.chat?.limit ?? 50;
  const questionLimit = permissions.ai_question_daily_limit ?? entitlementQuota?.feature_limits?.question_generate?.limit ?? 5;
  const uploadLimitMb = permissions.material_upload_limit_mb ?? entitlementQuota?.upload_limits?.single_file_size_mb ?? 100;
  const chatUsed = entitlementQuota?.feature_limits?.chat?.used ?? 0;
  const questionUsed = entitlementQuota?.feature_limits?.question_generate?.used ?? 0;
  const uploadUsed = entitlementQuota?.upload_limits?.material_upload_count?.used ?? 0;
  const formatUploadLimit = (mb) => Number(mb) >= 1024 ? `${Number(mb) / 1024}GB` : `${mb}MB`;

  const quotaItems = [
    { icon: "💬", label: "AI 问答次数", value: chatLimit, unit: "次 / 每天", sub: `已使用 ${chatUsed} 次` },
    { icon: "📝", label: "AI 出题次数", value: questionLimit, unit: "次 / 每天", sub: `已使用 ${questionUsed} 次` },
    { icon: "📁", label: "资料上传限制", value: formatUploadLimit(uploadLimitMb), unit: "", sub: `已上传 ${uploadUsed} 份资料` },
    { icon: "📋", label: "学习计划", value: permissions.learning_plan ? "已解锁" : "未解锁", unit: "", sub: permissions.learning_plan ? "当前套餐可用" : "升级后可用" },
    { icon: "🔄", label: "错题复盘", value: permissions.mistake_review ? "已解锁" : "未解锁", unit: "", sub: permissions.mistake_review ? "当前套餐可用" : "升级后可用" },
    { icon: "📊", label: "学习报告", value: permissions.learning_report ? "已解锁" : "未解锁", unit: "", sub: permissions.learning_report ? "当前套餐可用" : "升级后可用" },
  ];
  const fallbackBenefits = [
    { label: `AI 问答 ${chatLimit} 次 / 每天`, enabled: true },
    { label: `AI 出题 ${questionLimit} 次 / 每天`, enabled: true },
    { label: `资料上传限制 ${formatUploadLimit(uploadLimitMb)}`, enabled: true },
    { label: "学习计划", enabled: Boolean(permissions.learning_plan) },
    { label: "错题复盘", enabled: Boolean(permissions.mistake_review) },
    { label: "学习报告", enabled: Boolean(permissions.learning_report) },
  ];
  const packageBenefits = (courseEntitlements?.benefits || []).length > 0
    ? courseEntitlements.benefits.map((benefit) => ({
        label: benefit.limit ? `${benefit.label} ${benefit.limit}${benefit.unit ? ` ${benefit.unit}` : ""}` : benefit.label,
        enabled: Boolean(benefit.enabled),
      }))
    : fallbackBenefits;

  const fetchCourseAccountData = async () => {
    try {
      const res = await fetch(`${API_BASE}/me/tracks?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      const tracks = data.tracks || [];
      const courseT = tracks.find((t) => t.track_type === "university_course");
      if (courseT) setCourseTrack(courseT);
      const detail = courseT?.onboarding_detail || {};
      const courses = detail?.selected_courses || [];
      setCourseCount(courses.length || 0);
    } catch { /* keep current value */ }
    try {
      const entitlementRes = await fetch(`${API_BASE}/course-learning/entitlements?username=${encodeURIComponent(user.username)}`);
      const entitlementData = await entitlementRes.json().catch(() => ({}));
      if (entitlementRes.ok) setCourseEntitlements(entitlementData);
    } catch { /* keep current entitlements */ }
    try {
      const quotaRes = await fetch(`${API_BASE}/me/quota?username=${encodeURIComponent(user.username)}`);
      const quota = await quotaRes.json().catch(() => ({}));
      if (quotaRes.ok) setQuotaData(quota);
    } catch { /* keep current quota */ }
    // Refresh service plans for accurate switching
    try {
      const meRes = await fetch(`${API_BASE}/me`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username }),
      });
      const meData = await meRes.json().catch(() => ({}));
      if (meRes.ok && meData.user?.service_plans) {
        setServicePlans(meData.user.service_plans);
      }
    } catch { /* keep existing plans */ }
  };
  useEffect(() => { fetchCourseAccountData(); }, []);

  const displayName = user?.nickname || user?.username || "同学";
  const username = user?.username || "";
  const registerTime = user?.created_at || "";
  const realEmail = user?.email || "";
  const emailDisplay = realEmail ? maskEmail(realEmail) : "未绑定";
  const emailBtnLabel = realEmail ? "修改" : "绑定";

  const courseMajors = onboardingDetail?.major || user?.major || "未设置";
  const courseGrade = onboardingDetail?.grade || user?.grade || "未设置";
  const courseSemester = onboardingDetail?.current_semester || "未设置";

  const switchTrack = async (targetTrack) => {
    setActionErr("");
    await switchLearningDirection({
      targetTrack,
      user,
      apiBase: API_BASE,
      setPage,
      onError: setActionErr,
      onPlansUpdate: setServicePlans,
    });
  };

  // Avatar
  const uploadAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setAvatarUploading(true);
    setActionErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("username", user.username);
      const res = await fetch(`${API_BASE}/me/avatar`, { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "上传失败");
      setActionMsg("头像已更新");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (err) {
      setActionErr(err.message);
    } finally {
      setAvatarUploading(false);
    }
  };

  const saveBasicInfo = async () => {
    setActionErr("");
    try {
      const res = await fetch(`${API_BASE}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, grade: user?.grade || "", major: user?.major || "" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存失败");
      setEditing(false);
      setActionMsg("资料已保存");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (err) {
      setActionErr(err.message);
    }
  };

  // ── Password modal ──
  const [pwdModal, setPwdModal] = useState(false);
  const [pwdForm, setPwdForm] = useState({ old_password: "", new_password: "", confirm_password: "" });
  const [pwdSaving, setPwdSaving] = useState(false);
  const [pwdErr, setPwdErr] = useState("");

  const openPwdModal = () => { setPwdForm({ old_password: "", new_password: "", confirm_password: "" }); setPwdErr(""); setPwdModal(true); };
  const changePassword = async () => {
    setPwdErr("");
    if (pwdForm.new_password !== pwdForm.confirm_password) { setPwdErr("新密码和确认密码不一致"); return; }
    setPwdSaving(true);
    try {
      const res = await fetch(`${API_BASE}/me/password?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pwdForm),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "密码修改失败");
      setPwdModal(false);
      setActionMsg("密码修改成功");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (err) {
      setPwdErr(err.message);
    } finally {
      setPwdSaving(false);
    }
  };

  // ── Email modal ──
  const [emailModal, setEmailModal] = useState(false);
  const [emailForm, setEmailForm] = useState({ email: "", code: "" });
  const [emailSending, setEmailSending] = useState(false);
  const [emailBinding, setEmailBinding] = useState(false);
  const [emailErr, setEmailErr] = useState("");
  const [emailMsg, setEmailMsg] = useState("");

  const openEmailModal = () => {
    setEmailForm({ email: "", code: "" });
    setEmailErr(""); setEmailMsg("");
    setEmailModal(true);
  };

  const sendEmailCode = async () => {
    const em = emailForm.email.trim();
    if (!em) { setEmailErr("请输入邮箱地址"); return; }
    setEmailSending(true); setEmailErr(""); setEmailMsg("");
    try {
      const res = await fetch(`${API_BASE}/me/email/send-code?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: em }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "验证码发送失败");
      setEmailMsg("验证码已发送");
    } catch (err) {
      setEmailErr(err.message);
    } finally {
      setEmailSending(false);
    }
  };

  const bindEmail = async () => {
    setEmailBinding(true); setEmailErr(""); setEmailMsg("");
    try {
      const res = await fetch(`${API_BASE}/me/email/verify?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailForm.email.trim(), code: emailForm.code.trim() }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "邮箱绑定失败");
      setEmailModal(false);
      setActionMsg("邮箱已绑定");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (err) {
      setEmailErr(err.message);
    } finally {
      setEmailBinding(false);
    }
  };

  return (
    <div className="ep-page-wrap">
      <div className="ep-shell">
        <div className="ep-header">
          <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("home")}>← 返回课程学习主页</button>
          <h1 className="ep-title">📚 课程学习 · 个人中心</h1>
        </div>

        {actionMsg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{actionMsg}</div>}
        {actionErr && <div className="admin-dashboard-error" style={{ marginBottom: 12 }}>{actionErr}</div>}

        {/* ═══ Section 1: Basic Info ═══ */}
        <div className="ep-card">
          <div className="ep-card-head">
            <h2>基础信息</h2>
            <button type="button" className="ep-outline-btn" onClick={() => editing ? saveBasicInfo() : setEditing(true)}>
              ✎ {editing ? "保存资料" : "编辑资料"}
            </button>
          </div>
          <div className="ep-basic-grid">
            <div className="ep-avatar-col">
              <div className="ep-avatar-wrap">
                {user?.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="ep-avatar-img" />
                ) : (
                  <span className="ep-avatar-text">{displayName.charAt(0)}</span>
                )}
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
                {editing ? <input className="ep-info-input" value={nickname} onChange={(e) => setNickname(e.target.value)} /> : <span>{displayName}</span>}
              </div>
              <div className="ep-info-row"><span className="ep-info-label">学习方向</span><span className="ep-info-tag">课程学习</span></div>
              <div className="ep-info-row"><span className="ep-info-label">专业</span><span>{courseMajors}</span></div>
            </div>
            <div className="ep-info-col">
              <div className="ep-info-row"><span className="ep-info-label">年级</span><span>{courseGrade}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">已加入课程</span><span>{courseCount} 门</span></div>
              <div className="ep-info-row"><span className="ep-info-label">当前学期</span><span>{courseSemester}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">注册时间</span><span className="ep-info-time">{registerTime}</span></div>
            </div>
          </div>
        </div>

        {/* ═══ Section 2: Course Learning Overview ═══ */}
        <div className="ep-card">
          <div className="ep-card-head">
            <h2>课程学习概览 <span className="ep-help-icon" title="课程学习方向的功能与额度">?</span></h2>
            <div className="ep-switch-btns">
              <button type="button" className="ep-outline-btn" onClick={() => switchTrack("exam_408")}>切换到 11408</button>
              <button type="button" className="ep-outline-btn" onClick={() => switchTrack("programming")}>切换到编程</button>
            </div>
          </div>
          <div className="ep-quota-grid">
            {quotaItems.map((q, i) => (
              <div key={i} className="ep-quota-item">
                <span className="ep-quota-icon">{q.icon}</span>
                <span className="ep-quota-label">{q.label}</span>
                <strong className="ep-quota-value">{q.value}{q.unit ? <small> {q.unit}</small> : null}</strong>
                <span className="ep-quota-sub">{q.sub}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ═══ Section 3: Account Security ═══ */}
        <div className="ep-card">
          <div className="ep-card-head"><h2>账号安全</h2></div>
          <div className="ep-security-grid">
            <div className="ep-sec-item">
              <div>
                <strong>登录密码</strong>
                <p>用于登录账号的密码</p>
                <span>********</span>
              </div>
              <button type="button" className="ep-outline-btn" onClick={openPwdModal}>修改</button>
            </div>
            <div className="ep-sec-item">
              <div>
                <strong>绑定手机号</strong>
                <p>用于接收验证码和安全验证</p>
                <span>{user?.phone ? maskEmail(user.phone).replace("@","") : "未绑定"}</span>
              </div>
              <button type="button" className="ep-outline-btn" onClick={() => setActionErr("手机号绑定功能暂未开放")}>修改</button>
            </div>
            <div className="ep-sec-item">
              <div>
                <strong>绑定邮箱</strong>
                <p>用于接收重要通知和找回密码</p>
                <span>{emailDisplay}</span>
              </div>
              <button type="button" className="ep-outline-btn" onClick={openEmailModal}>{emailBtnLabel}</button>
            </div>
            <div className="ep-sec-item ep-sec-item--logout">
              <div>
                <strong>退出登录</strong>
                <p>退出后需要重新登录才能访问</p>
              </div>
              <button type="button" className="ep-logout-btn" onClick={onLogout}>退出登录</button>
            </div>
          </div>
        </div>

        {/* ═══ Section 4: My Package ═══ */}
        <div className="ep-card">
          <div className="ep-card-head"><h2>我的套餐</h2></div>
          <div className="ep-package-row">
            <div className="ep-package-badge-col">
              <div className="ep-package-badge-icon">🏆</div>
            </div>
            <div className="ep-package-info">
              <span className="ep-package-section-label">当前套餐</span>
              <div className="ep-package-name-row">
                <strong>{displayPkg}</strong>
              </div>
            </div>
            <div className="ep-package-perks">
              <span className="ep-package-section-label">套餐权益</span>
              <ul className="ep-perks-list">
                {packageBenefits.map((p, i) => (
                  <li key={`${p.label}-${i}`} className={p.enabled ? "" : "ep-perk--off"}>
                    <span className="ep-perk-check">{p.enabled ? "✓" : "✕"}</span> {p.label}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ep-package-action">
              <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("coursePlan")}>查看套餐详情</button>
            </div>
          </div>
        </div>

        <p className="ep-footer">如有疑问，请联系<span className="ep-footer-link">客服支持</span></p>
      </div>

      {/* ── Password Modal ── */}
      {pwdModal && (
        <div className="eh-modal-backdrop" onClick={() => setPwdModal(false)}>
          <div className="eh-modal" onClick={(e) => e.stopPropagation()}>
            <div className="eh-modal-head"><h3>修改密码</h3><button type="button" className="eh-modal-close" onClick={() => setPwdModal(false)}>×</button></div>
            {pwdErr && <div className="ob-error" style={{ marginBottom: 12 }}>{pwdErr}</div>}
            <label className="ob-label">当前密码</label>
            <input type="password" className="ep-modal-input" style={{ marginBottom: 14 }} value={pwdForm.old_password} placeholder="请输入当前密码" onChange={(e) => setPwdForm((p) => ({ ...p, old_password: e.target.value }))} />
            <label className="ob-label">新密码</label>
            <input type="password" className="ep-modal-input" style={{ marginBottom: 14 }} value={pwdForm.new_password} placeholder="请输入新密码" onChange={(e) => setPwdForm((p) => ({ ...p, new_password: e.target.value }))} />
            <label className="ob-label">确认新密码</label>
            <input type="password" className="ep-modal-input" style={{ marginBottom: 16 }} value={pwdForm.confirm_password} placeholder="请再次输入新密码" onChange={(e) => setPwdForm((p) => ({ ...p, confirm_password: e.target.value }))} />
            <div className="eh-modal-actions">
              <button type="button" className="ob-btn-secondary" onClick={() => setPwdModal(false)}>取消</button>
              <button type="button" className="ob-btn-primary" onClick={changePassword} disabled={pwdSaving}>{pwdSaving ? "修改中..." : "确认修改"}</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Email Modal ── */}
      {emailModal && (
        <div className="eh-modal-backdrop" onClick={() => setEmailModal(false)}>
          <div className="eh-modal" onClick={(e) => e.stopPropagation()}>
            <div className="eh-modal-head"><h3>{realEmail ? "更换邮箱" : "绑定邮箱"}</h3><button type="button" className="eh-modal-close" onClick={() => setEmailModal(false)}>×</button></div>
            {realEmail && <p style={{ color: "#64748b", fontSize: 13, margin: "0 0 12px" }}>当前邮箱：{maskEmail(realEmail)}</p>}
            {emailErr && <div className="ob-error" style={{ marginBottom: 12 }}>{emailErr}</div>}
            {emailMsg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{emailMsg}</div>}
            <label className="ob-label">新邮箱</label>
            <input className="ep-modal-input" style={{ marginBottom: 14 }} value={emailForm.email} placeholder="请输入新邮箱地址" onChange={(e) => setEmailForm((p) => ({ ...p, email: e.target.value }))} />
            <label className="ob-label">验证码</label>
            <div className="ob-row" style={{ marginBottom: 16 }}>
              <input className="ep-modal-input" style={{ flex: 1 }} value={emailForm.code} placeholder="请输入验证码" onChange={(e) => setEmailForm((p) => ({ ...p, code: e.target.value }))} />
              <button type="button" className="ob-btn-secondary" style={{ width: 120, height: 44, flexShrink: 0 }} onClick={sendEmailCode} disabled={emailSending}>{emailSending ? "发送中..." : "发送验证码"}</button>
            </div>
            <div className="eh-modal-actions">
              <button type="button" className="ob-btn-secondary" onClick={() => setEmailModal(false)}>取消</button>
              <button type="button" className="ob-btn-primary" onClick={bindEmail} disabled={emailBinding}>{emailBinding ? "绑定中..." : "确认绑定"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
