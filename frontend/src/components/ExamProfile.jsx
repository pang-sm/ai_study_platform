import { useEffect, useRef, useState } from "react";
import { switchLearningDirection } from "../utils/serviceSwitch.js";
import { resolveMediaUrl } from "../utils/mediaUrl.js";

const EXAM_408_SCHOOLS = [
  "北京大学", "南京大学", "浙江大学", "上海交通大学",
  "复旦大学", "中国科学技术大学", "武汉大学", "华中科技大学",
  "同济大学", "中国人民大学", "北京邮电大学", "北京工业大学",
  "北京交通大学", "南京理工大学", "华东理工大学", "上海大学",
  "郑州大学", "云南大学", "河北工业大学", "武汉理工大学",
];

const PACKAGE_LABELS = {
  free: "免费模式",
  monthly_sprint: "月度冲刺包",
  quarterly_boost: "季度强化包",
  full_exam: "全程考包",
};
const GRADE_OPTIONS = ["大一", "大二", "大三", "大四", "研究生"];
const SEMESTER_OPTIONS = ["上学期", "下学期"];
const EXAM_STAGES = ["基础阶段", "强化阶段", "冲刺阶段"];
const EXAM_DAILY = ["4 小时以内", "4 - 6 小时", "6 - 8 小时", "8 小时以上"];

function maskEmail(email) {
  if (!email) return "";
  const at = email.indexOf("@");
  if (at <= 0) return email;
  const name = email.slice(0, at);
  const domain = email.slice(at);
  if (name.length <= 3) return name.slice(0, 1) + "***" + domain;
  return name.slice(0, 3) + "***" + domain;
}

function maskPhone(phone) {
  const value = String(phone || "").trim();
  if (!value) return "";
  const digits = value.replace(/\D/g, "");
  const local = digits.length > 11 ? digits.slice(-11) : digits;
  if (local.length !== 11) return value;
  return `${local.slice(0, 3)}****${local.slice(-4)}`;
}

export default function ExamProfile({ user, setPage, onLogout, API_BASE, onProfileUpdate, onReplayGuide }) {
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [actionMsg, setActionMsg] = useState("");
  const [actionErr, setActionErr] = useState("");
  const [editing, setEditing] = useState(false);
  const [nickname, setNickname] = useState(user?.nickname || "");
  const [major, setMajor] = useState(user?.major || "");
  const [grade, setGrade] = useState(user?.grade || "");
  const [semester, setSemester] = useState(user?.semester || "");
  const [examTrack, setExamTrack] = useState(() => (user?.tracks || []).find((t) => t.track_type === "exam_408") || null);
  const [quotaData, setQuotaData] = useState(null);
  const avatarInputRef = useRef(null);

  // Target school search
  const [targetSchool, setTargetSchool] = useState("");
  const [schoolQuery, setSchoolQuery] = useState("");
  const [schoolResults, setSchoolResults] = useState([]);
  const [schoolFocused, setSchoolFocused] = useState(false);
  const schoolRef = useRef(null);
  const [examTimeDraft, setExamTimeDraft] = useState("");
  const [examStageDraft, setExamStageDraft] = useState("基础阶段");
  const [examDailyDraft, setExamDailyDraft] = useState("6 - 8 小时");
  const [examTimeUncertain, setExamTimeUncertain] = useState(false);
  const [examInfoSaving, setExamInfoSaving] = useState(false);

  useEffect(() => {
    if (!editing) {
      setNickname(user?.nickname || "");
      setMajor(user?.major || "");
      setGrade(user?.grade || "");
      setSemester(user?.semester || "");
    }
  }, [user?.nickname, user?.major, user?.grade, user?.semester, editing]);

  const pkgType = examTrack?.package_type || "free";
  const permissions = examTrack?.permissions || {};
  const onboardingDetail = (() => {
    try {
      if (examTrack?.onboarding_detail) return examTrack.onboarding_detail;
      const d = user?.onboarding_detail;
      if (!d) return null;
      return typeof d === "string" ? JSON.parse(d) : d;
    } catch { return null; }
  })();

  // Sync editable exam-info drafts when entering edit mode.
  useEffect(() => {
    if (editing) {
      const t = onboardingDetail?.exam_time || "";
      const uncertain = !t || t === "暂不确定";
      setExamTimeUncertain(uncertain);
      setExamTimeDraft(uncertain ? "" : t);
      setExamStageDraft(onboardingDetail?.stage || "基础阶段");
      setExamDailyDraft(onboardingDetail?.daily_study_time || "6 - 8 小时");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  const displayPkg = examTrack?.package_display_name || PACKAGE_LABELS[pkgType] || "免费模式";
  const chatLimit = permissions.ai_chat_daily_limit ?? quotaData?.feature_limits?.chat?.limit ?? 50;
  const questionLimit = permissions.ai_question_daily_limit ?? quotaData?.feature_limits?.question_generate?.limit ?? 5;
  const uploadLimitMb = permissions.material_upload_limit_mb ?? quotaData?.upload_limits?.single_file_size_mb ?? 100;
  const chatUsed = quotaData?.feature_limits?.chat?.used ?? 0;
  const questionUsed = quotaData?.feature_limits?.question_generate?.used ?? 0;
  const uploadUsed = quotaData?.upload_limits?.material_upload_count?.used ?? 0;
  const formatUploadLimit = (mb) => Number(mb) >= 1024 ? `${Number(mb) / 1024}GB` : `${mb}MB`;

  const quotaItems = [
    { icon: "💬", label: "AI 问答次数", value: chatLimit, unit: "次 / 每天", sub: `已使用 ${chatUsed} 次` },
    { icon: "📝", label: "AI 出题次数", value: questionLimit, unit: "次 / 每天", sub: `已使用 ${questionUsed} 次` },
    { icon: "📁", label: "资料上传限制", value: formatUploadLimit(uploadLimitMb), unit: "", sub: `已上传 ${uploadUsed} 份资料` },
    { icon: "📋", label: "学习计划", value: permissions.learning_plan ? "已解锁" : "未解锁", unit: "", sub: permissions.learning_plan ? "当前套餐可用" : "升级后可用" },
    { icon: "🔄", label: "错题复盘", value: permissions.mistake_review ? "已解锁" : "未解锁", unit: "", sub: permissions.mistake_review ? "当前套餐可用" : "升级后可用" },
    { icon: "📊", label: "学习报告", value: permissions.learning_report ? "已解锁" : "未解锁", unit: "", sub: permissions.learning_report ? "当前套餐可用" : "升级后可用" },
  ];

  const fetchExamAccountData = async () => {
    try {
      const res = await fetch(`${API_BASE}/me/tracks?username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      const tracks = data.tracks || [];
      const examT = tracks.find((t) => t.track_type === "exam_408");
      if (examT) setExamTrack(examT);
      const detail = examT?.onboarding_detail || {};
      const school = detail?.target_school || "";
      setTargetSchool(school);
      setSchoolQuery(school);
    } catch { /* keep current value */ }
    try {
      const quotaRes = await fetch(`${API_BASE}/me/quota?username=${encodeURIComponent(user.username)}`);
      const quota = await quotaRes.json().catch(() => ({}));
      if (quotaRes.ok) setQuotaData(quota);
    } catch { /* keep current quota */ }
  };
  useEffect(() => { fetchExamAccountData(); }, []);

  const fetchSchools = async (q) => {
    const query = (q || "").trim();
    // Try backend API first
    try {
      const res = await fetch(`${API_BASE}/exam-408/schools?q=${encodeURIComponent(query)}`);
      const data = await res.json().catch(() => ({}));
      if (data.schools && data.schools.length > 0) {
        setSchoolResults(data.schools);
        return;
      }
    } catch { /* fallback to local list */ }
    // Fallback: filter local constant
    const lower = query.toLowerCase();
    const results = query
      ? EXAM_408_SCHOOLS.filter((s) => s.toLowerCase().includes(lower))
      : EXAM_408_SCHOOLS;
    setSchoolResults(results);
  };

  const selectSchool = async (school) => {
    if (!EXAM_408_SCHOOLS.includes(school)) {
      setActionErr("请选择 11408 院校库中的学校");
      return;
    }
    setSchoolQuery(school);
    setTargetSchool(school);
    setSchoolFocused(false);
    // Save to backend
    try {
      const res = await fetch(`${API_BASE}/exam-408/target-school`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, school }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存失败");
      await fetchExamAccountData();
      setActionMsg("目标院校已更新");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (err) {
      setActionErr(err.message);
      fetchExamAccountData();
    }
  };

  // Click outside to close dropdown
  useEffect(() => {
    const handler = (e) => { if (schoolRef.current && !schoolRef.current.contains(e.target)) setSchoolFocused(false); };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const displayName = user?.nickname || user?.username || "小庞同学";
  const username = user?.username || "xiaopang";
  const examTime = onboardingDetail?.exam_time || "2026 年 12 月";
  const examStage = onboardingDetail?.stage || "基础阶段";
  const examDaily = onboardingDetail?.daily_study_time || "6 - 8 小时";
  const registerTime = user?.created_at ? String(user.created_at).slice(0, 10) : "暂无";
  const realEmail = user?.email || "";
  const emailDisplay = realEmail ? maskEmail(realEmail) : "未绑定";
  const emailBtnLabel = realEmail ? "修改" : "绑定";
  const avatarSrc = resolveMediaUrl(user?.avatar_url, API_BASE);

  const hasCourseTrack = (user?.tracks || []).some((t) => t.track_type === "university_course");
  const hasCodeTrack = (user?.tracks || []).some((t) => t.track_type === "programming");

  const switchTrack = async (targetTrack) => {
    setActionErr("");
    await switchLearningDirection({
      targetTrack,
      user,
      apiBase: API_BASE,
      setPage,
      onError: setActionErr,
      returnPage: "examHome",
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
      if (data.profile) onProfileUpdate?.(data.profile);
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
        body: JSON.stringify({ nickname, major, grade, semester }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存失败");
      if (data.profile) onProfileUpdate?.(data.profile);
    } catch (err) {
      setActionErr(err.message);
      return;
    }

    // Persist editable 11408 exam-info (reuses onboarding_detail fields).
    try {
      const res = await fetch(`${API_BASE}/exam-408/exam-info`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          exam_time: examTimeUncertain ? "暂不确定" : examTimeDraft,
          stage: examStageDraft,
          daily_study_time: examDailyDraft,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "备考信息保存失败");
      setExamTrack((prev) => prev ? { ...prev, onboarding_detail: { ...(prev.onboarding_detail || {}), exam_time: data.exam_time, stage: data.stage, daily_study_time: data.daily_study_time } } : prev);
    } catch (err) {
      setActionErr(err.message);
      return;
    }

    setEditing(false);
    setActionMsg("资料已保存");
    setTimeout(() => setActionMsg(""), 2500);
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

  // ── Phone bind/change modal ──
  const [phoneModal, setPhoneModal] = useState(false);
  const [phoneForm, setPhoneForm] = useState({ phone: "", code: "" });
  const [phoneSending, setPhoneSending] = useState(false);
  const [phoneBinding, setPhoneBinding] = useState(false);
  const [phoneErr, setPhoneErr] = useState("");
  const [phoneMsg, setPhoneMsg] = useState("");
  const [phoneCountdown, setPhoneCountdown] = useState(0);
  const phoneCountdownRef = useRef(null);
  const phoneHasBound = Boolean(user?.phone_verified);

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

  const phoneErrorText = (data) => {
    const d = data?.detail;
    if (d && typeof d === "object" && d.message) return d.message;
    if (typeof d === "string" && d) return d;
    return null;
  };

  const openPhoneModal = () => {
    setPhoneForm({ phone: "", code: "" });
    setPhoneErr(""); setPhoneMsg("");
    setPhoneModal(true);
  };

  useEffect(() => {
    if (!phoneModal || phoneCountdown <= 0) return;
    const timer = setTimeout(() => setPhoneCountdown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [phoneModal, phoneCountdown]);

  const sendPhoneCode = async () => {
    const phone = phoneForm.phone.trim();
    if (!/^1[3-9]\d{9}$/.test(phone)) { setPhoneErr("请输入有效的中国大陆手机号"); return; }
    setPhoneSending(true); setPhoneErr(""); setPhoneMsg("");
    try {
      const path = phoneHasBound ? "/me/phone/change/send-code" : "/me/phone/send-code";
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(phoneErrorText(data) || "验证码发送失败");
      setPhoneMsg("验证码已发送");
      setPhoneCountdown(59);
    } catch (err) {
      setPhoneErr(err.message);
    } finally {
      setPhoneSending(false);
    }
  };

  const bindPhone = async () => {
    const phone = phoneForm.phone.trim();
    const code = phoneForm.code.trim();
    if (!/^1[3-9]\d{9}$/.test(phone)) { setPhoneErr("请输入有效的中国大陆手机号"); return; }
    if (!/^\d{6}$/.test(code)) { setPhoneErr("请输入 6 位数字验证码"); return; }
    setPhoneBinding(true); setPhoneErr(""); setPhoneMsg("");
    try {
      const path = phoneHasBound ? "/me/phone/change/verify" : "/me/phone/verify";
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, code }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(phoneErrorText(data) || "手机号绑定失败");
      setPhoneModal(false);
      onProfileUpdate?.({ phone: data.phone, phone_verified: true, phone_verified_at: data.phone_verified_at });
      setActionMsg(phoneHasBound ? "手机号已更换" : "手机号已绑定");
      setTimeout(() => setActionMsg(""), 2500);
    } catch (err) {
      setPhoneErr(err.message);
    } finally {
      setPhoneBinding(false);
    }
  };

  return (
    <div className="ep-page-wrap">
      <div className="ep-shell">
        <div className="ep-header">
          <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("examHome")}>← 返回 11408 主页</button>
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
            <div className="ep-avatar-col">
              <div className="ep-avatar-wrap">
                {avatarSrc ? (
                  <img src={avatarSrc} alt="" className="ep-avatar-img" />
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
              <div className="ep-info-row"><span className="ep-info-label">专业</span>{editing ? <input className="ep-info-input" value={major} onChange={(event) => setMajor(event.target.value)} maxLength={50} /> : <span>{major || "未设置"}</span>}</div>
              <div className="ep-info-row"><span className="ep-info-label">学习方向</span><span className="ep-info-tag">11408 考研</span></div>
              <div className="ep-info-row">
                <span className="ep-info-label">目标院校</span>
                <div className="ep-school-wrap" ref={schoolRef}>
                  {editing ? (
                    <>
                      <input
                        className="ep-school-input"
                        value={schoolQuery}
                        placeholder="输入院校名称搜索..."
                        onChange={(e) => { setSchoolQuery(e.target.value); fetchSchools(e.target.value); }}
                        onFocus={() => { setSchoolFocused(true); if (!schoolQuery) fetchSchools(""); }}
                      />
                      {schoolFocused && (
                        <div className="ep-school-drop">
                          {schoolResults.length === 0 ? (
                            <span className="ep-school-none">未找到匹配院校</span>
                          ) : (
                            schoolResults.map((s) => (
                              <button key={s} type="button" className="ep-school-opt" onClick={() => selectSchool(s)}>{s}</button>
                            ))
                          )}
                        </div>
                      )}
                    </>
                  ) : (
                    <span>{targetSchool || "未设置"}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="ep-info-col">
              <div className="ep-info-row"><span className="ep-info-label">年级</span>{editing ? <select className="ep-info-input" value={grade} onChange={(event) => setGrade(event.target.value)}><option value="">未设置</option>{GRADE_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <span>{grade || "未设置"}</span>}</div>
              <div className="ep-info-row"><span className="ep-info-label">当前学期</span>{editing ? <select className="ep-info-input" value={semester} onChange={(event) => setSemester(event.target.value)}><option value="">未设置</option>{SEMESTER_OPTIONS.map((option) => <option key={option} value={option}>{option}</option>)}</select> : <span>{semester || "未设置"}</span>}</div>
              <div className="ep-info-row">
                <span className="ep-info-label">考试时间</span>
                {editing ? (
                  <span className="ep-exam-info-edit">
                    <input type="date" className="ep-info-input" value={examTimeUncertain ? "" : examTimeDraft} disabled={examTimeUncertain} onChange={(event) => setExamTimeDraft(event.target.value)} />
                    <label className="ep-uncertain-toggle">
                      <input type="checkbox" checked={examTimeUncertain} onChange={(event) => { setExamTimeUncertain(event.target.checked); if (event.target.checked) setExamTimeDraft(""); }} />
                      暂不确定
                    </label>
                  </span>
                ) : (
                  <span>{examTime || "暂不确定"}</span>
                )}
              </div>
              <div className="ep-info-row">
                <span className="ep-info-label">当前备考阶段</span>
                {editing ? (
                  <select className="ep-info-input" value={examStageDraft} onChange={(event) => setExamStageDraft(event.target.value)}>
                    {EXAM_STAGES.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                ) : (
                  <span>{examStage}</span>
                )}
              </div>
              <div className="ep-info-row">
                <span className="ep-info-label">每天学习时间</span>
                {editing ? (
                  <select className="ep-info-input" value={examDailyDraft} onChange={(event) => setExamDailyDraft(event.target.value)}>
                    {EXAM_DAILY.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                ) : (
                  <span>{examDaily}</span>
                )}
              </div>
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

        <div className="ep-card">
          <div className="ep-card-head"><h2>帮助与引导</h2></div>
          <div className="ep-sec-item">
            <div><strong>新手引导</strong><p>重新查看 11408 方向的功能介绍，不会重置首次自动展示状态。</p></div>
            <button type="button" className="ep-outline-btn" onClick={onReplayGuide}>重新查看</button>
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
                <span>{user?.phone ? maskPhone(user.phone) : "未绑定"}</span>
                {user?.phone_verified && <em className="ep-verified-tag">已验证</em>}
              </div>
              <button type="button" className="ep-outline-btn" onClick={openPhoneModal}>{user?.phone_verified ? "更换手机号" : "绑定手机号"}</button>
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
                {pkgType === "quarterly_boost" && <span className="ep-package-recommend-tag">推荐</span>}
              </div>
              <span className="ep-package-expire">有效期至：2025-03-01</span>
            </div>
            <div className="ep-package-perks">
              <span className="ep-package-section-label">套餐权益</span>
              <ul className="ep-perks-list">
                {[
                  { label: `AI 问答 ${chatLimit} 次 / 每天`, ok: true },
                  { label: `AI 出题 ${questionLimit} 次 / 每天`, ok: true },
                  { label: `资料上传限制 ${formatUploadLimit(uploadLimitMb)}`, ok: true },
                  { label: "学习计划", ok: Boolean(permissions.learning_plan) },
                  { label: "错题复盘", ok: Boolean(permissions.mistake_review) },
                  { label: "学习报告", ok: Boolean(permissions.learning_report) },
                ].map((p, i) => (
                  <li key={i} className={p.ok ? "" : "ep-perk--off"}>
                    <span className="ep-perk-check">{p.ok ? "✓" : "✕"}</span> {p.label}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ep-package-action">
              <button type="button" className="ep-outline-btn" onClick={() => setPage && setPage("membership", { serviceKey: "exam_11408", profilePage: "examProfile", returnPage: "examHome" })}>查看套餐详情</button>
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
      {phoneModal && (
        <div className="eh-modal-backdrop" onClick={() => !phoneBinding && setPhoneModal(false)}>
          <div className="eh-modal" onClick={(e) => e.stopPropagation()}>
            <div className="eh-modal-head"><h3>{phoneHasBound ? "更换手机号" : "绑定手机号"}</h3><button type="button" className="eh-modal-close" onClick={() => setPhoneModal(false)}>×</button></div>
            {phoneHasBound && user?.phone && <p style={{ color: "#64748b", fontSize: 13, margin: "0 0 12px" }}>当前手机号：{maskPhone(user.phone)}</p>}
            {phoneErr && <div className="ob-error" style={{ marginBottom: 12 }}>{phoneErr}</div>}
            {phoneMsg && <div className="admin-dashboard-success" style={{ marginBottom: 12 }}>{phoneMsg}</div>}
            <label className="ob-label">手机号</label>
            <div className="ob-row" style={{ marginBottom: 14 }}>
              <span style={{ flexShrink: 0, color: "#64748b", fontSize: 14, fontWeight: 700 }}>+86</span>
              <input className="ep-modal-input" style={{ flex: 1, marginLeft: 8 }} value={phoneForm.phone} placeholder="13812345678" maxLength={11} onChange={(e) => setPhoneForm((p) => ({ ...p, phone: e.target.value.replace(/\D/g, "") }))} />
            </div>
            <label className="ob-label">验证码</label>
            <div className="ob-row" style={{ marginBottom: 16 }}>
              <input className="ep-modal-input" style={{ flex: 1 }} value={phoneForm.code} placeholder="6 位数字验证码" maxLength={6} onChange={(e) => setPhoneForm((p) => ({ ...p, code: e.target.value.replace(/\D/g, "") }))} />
              <button type="button" className="ob-btn-secondary" style={{ width: 120, height: 44, flexShrink: 0 }} onClick={sendPhoneCode} disabled={phoneSending || phoneCountdown > 0}>{phoneSending ? "发送中..." : phoneCountdown > 0 ? `${phoneCountdown}s 后重发` : "获取验证码"}</button>
            </div>
            <div className="eh-modal-actions">
              <button type="button" className="ob-btn-secondary" onClick={() => setPhoneModal(false)}>取消</button>
              <button type="button" className="ob-btn-primary" onClick={bindPhone} disabled={phoneBinding}>{phoneBinding ? "绑定中..." : "确认绑定"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
