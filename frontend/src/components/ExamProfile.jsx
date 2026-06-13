import { useEffect, useRef, useState } from "react";

const PACKAGE_LABELS = {
  free: "免费模式",
  monthly_sprint: "月度冲刺",
  quarterly_boost: "季度强化包",
  full_exam: "全程考包",
};

const PACKAGE_PERKS = {
  free: [
    { label: "AI 问答 50 次 / 每天", ok: true },
    { label: "AI 出题 5 次 / 每天", ok: true },
    { label: "资料上传限制 100MB", ok: true },
    { label: "学习计划", ok: false },
    { label: "错题复盘", ok: false },
    { label: "学习报告", ok: false },
  ],
  monthly_sprint: [
    { label: "AI 问答 300 次 / 每天", ok: true },
    { label: "AI 出题 30 次 / 每天", ok: true },
    { label: "资料上传限制 500MB", ok: true },
    { label: "学习计划", ok: true },
    { label: "错题复盘", ok: true },
    { label: "学习报告", ok: true },
  ],
  quarterly_boost: [
    { label: "AI 问答 300 次 / 每天", ok: true },
    { label: "AI 出题 30 次 / 每天", ok: true },
    { label: "资料上传限制 500MB", ok: true },
    { label: "学习计划", ok: true },
    { label: "错题复盘", ok: true },
    { label: "学习报告", ok: true },
  ],
  full_exam: [
    { label: "AI 问答 1000 次 / 每天", ok: true },
    { label: "AI 出题 100 次 / 每天", ok: true },
    { label: "资料上传限制 2GB", ok: true },
    { label: "学习计划", ok: true },
    { label: "错题复盘", ok: true },
    { label: "学习报告", ok: true },
  ],
};

export default function ExamProfile({ user, setPage, onLogout, API_BASE }) {
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [nickname, setNickname] = useState(user?.nickname || "");
  const avatarInputRef = useRef(null);

  // Resolve package data from tracks
  const examTrack = (user?.tracks || []).find((t) => t.track_type === "exam_408");
  const pkgType = examTrack?.package_type || "";
  const onboardingDetail = (() => {
    try {
      if (examTrack?.onboarding_detail) return examTrack.onboarding_detail;
      const d = user?.onboarding_detail;
      if (!d) return null;
      return typeof d === "string" ? JSON.parse(d) : d;
    } catch { return null; }
  })();

  const displayPkg = PACKAGE_LABELS[pkgType] || "免费模式";
  const perks = PACKAGE_PERKS[pkgType] || PACKAGE_PERKS.free;

  // Quota items
  const quotaItems = [
    { icon: "💬", label: "AI 问答次数", value: perks.find((p) => p.label.includes("AI 问答"))?.label.split("AI 问答 ")[1]?.split(" ")[0] || "300", unit: "次 / 每天", used: "45", sub: "已使用 45 次" },
    { icon: "📝", label: "AI 出题次数", value: perks.find((p) => p.label.includes("AI 出题"))?.label.split("AI 出题 ")[1]?.split(" ")[0] || "30", unit: "次 / 每天", used: "8", sub: "已使用 8 次" },
    { icon: "📁", label: "资料上传限制", value: perks.find((p) => p.label.includes("资料上传"))?.label.split("限制 ")[1]?.replace("MB", "") || "500", unit: "MB", used: "120", sub: "已使用 120 MB" },
    { icon: "📋", label: "学习计划", value: perks[3]?.ok ? "已解锁" : "未解锁", unit: "", used: "", sub: perks[3]?.ok ? "进阶版可用" : "升级后可用" },
    { icon: "🔄", label: "错题复盘", value: perks[4]?.ok ? "已解锁" : "未解锁", unit: "", used: "", sub: perks[4]?.ok ? "进阶版可用" : "升级后可用" },
    { icon: "📊", label: "学习报告", value: perks[5]?.ok ? "已解锁" : "未解锁", unit: "", used: "", sub: perks[5]?.ok ? "进阶版可用" : "升级后可用" },
  ];

  const displayName = user?.nickname || user?.username || "小庞同学";
  const username = user?.username || "xiaopang";
  const examTime = onboardingDetail?.exam_time || "2026 年 12 月";
  const examStage = onboardingDetail?.stage || "基础阶段";
  const examDaily = onboardingDetail?.daily_study_time || "6 - 8 小时";
  const registerTime = user?.created_at || "2024-12-01 10:30:25";
  const targetSchool = onboardingDetail?.target_school || "北京大学";
  const emailDisplay = user?.email ? `${user.email.slice(0, 4)}***@${user.email.split("@")[1] || "example.com"}` : "pang***@example.com";

  const hasCourseTrack = (user?.tracks || []).some((t) => t.track_type === "university_course");
  const hasCodeTrack = (user?.tracks || []).some((t) => t.track_type === "programming");

  const switchTrack = (targetTrack) => {
    const has = (user?.tracks || []).some((t) => t.track_type === targetTrack);
    if (!has) {
      const names = { university_course: "课程学习", programming: "编程能力提升" };
      setActionErr(`请先开通${names[targetTrack] || targetTrack}方向`);
      return;
    }
    const pages = { university_course: "home", programming: "codeStudio" };
    if (setPage) setPage(pages[targetTrack] || "home");
  };

  // Avatar upload
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
      const res = await fetch(`${API_BASE || "/api"}/me/avatar`, { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "上传失败");
      setActionMsg("头像已更新");
      setTimeout(() => setActionMsg(""), 2000);
    } catch (err) {
      setActionErr(err.message);
    } finally {
      setAvatarUploading(false);
    }
  };

  const saveBasicInfo = async () => {
    setActionErr("");
    try {
      const res = await fetch(`${API_BASE || "/api"}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname, grade: user?.grade || "", major: user?.major || "" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存失败");
      setEditing(false);
      setActionMsg("资料已保存");
      setTimeout(() => setActionMsg(""), 2000);
    } catch (err) {
      setActionErr(err.message);
    }
  };

  return (
    <div className="onboarding-v2-page" style={{ alignItems: "flex-start", paddingTop: 32 }}>
      <div className="ep-shell">
        {/* ── Header ── */}
        <div className="ep-header">
          <h1 className="ep-title">🛡 个人中心</h1>
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
            {/* Avatar */}
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
            {/* Info columns */}
            <div className="ep-info-col">
              <div className="ep-info-row"><span className="ep-info-label">用户名</span><span>{username}</span></div>
              <div className="ep-info-row">
                <span className="ep-info-label">昵称</span>
                {editing ? <input className="ep-info-input" value={nickname} onChange={(e) => setNickname(e.target.value)} /> : <span>{displayName}</span>}
              </div>
              <div className="ep-info-row"><span className="ep-info-label">学习方向</span><span className="ep-info-tag">11408 考研</span></div>
              <div className="ep-info-row"><span className="ep-info-label">目标院校</span><span>{targetSchool}</span></div>
            </div>
            <div className="ep-info-col">
              <div className="ep-info-row"><span className="ep-info-label">考试时间</span><span>{examTime}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">当前备考阶段</span><span>{examStage}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">每天学习时间</span><span>{examDaily}</span></div>
              <div className="ep-info-row"><span className="ep-info-label">注册时间</span><span className="ep-info-time">{registerTime}</span></div>
            </div>
          </div>
        </div>

        {/* ═══ Section 2: Account Overview ═══ */}
        <div className="ep-card">
          <div className="ep-card-head">
            <h2>账号概览 <span className="ep-help-icon" title="当前方向的功能与额度">?</span></h2>
            <div className="ep-switch-btns">
              <button type="button" className="ep-outline-btn" onClick={() => switchTrack("university_course")}>切换到课程</button>
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
              <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("profile")}>修改</button>
            </div>
            <div className="ep-sec-item">
              <div>
                <strong>绑定手机号</strong>
                <p>用于接收验证码和安全验证</p>
                <span>138****5678</span>
              </div>
              <button type="button" className="ep-outline-btn" onClick={() => setActionErr("手机绑定暂未开放")}>修改</button>
            </div>
            <div className="ep-sec-item">
              <div>
                <strong>绑定邮箱</strong>
                <p>用于接收重要通知和找回密码</p>
                <span>{emailDisplay}</span>
              </div>
              <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("profile")}>修改</button>
            </div>
            <div className="ep-sec-item">
              <div>
                <strong>账号安全等级</strong>
                <p>较高的安全等级可以更好保护账号</p>
                <span className="ep-sec-high">高</span>
              </div>
              <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("profile")}>查看</button>
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
                {pkgType === "quarterly_boost" && <span className="ep-package-recommend-tag">推荐</span>}
              </div>
              <span className="ep-package-expire">有效期至：2025-03-01</span>
            </div>
            <div className="ep-package-perks">
              <span className="ep-package-section-label">套餐权益</span>
              <ul className="ep-perks-list">
                {perks.map((p, i) => (
                  <li key={i} className={p.ok ? "" : "ep-perk--off"}>
                    <span className="ep-perk-check">{p.ok ? "✓" : "✕"}</span> {p.label}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ep-package-action">
              <button type="button" className="ep-outline-btn" onClick={() => setActionErr("套餐详情暂未开放")}>查看套餐详情</button>
            </div>
          </div>
        </div>

        {/* ── Footer ── */}
        <p className="ep-footer">如有疑问，请联系<span className="ep-footer-link">客服支持</span></p>
      </div>
    </div>
  );
}
