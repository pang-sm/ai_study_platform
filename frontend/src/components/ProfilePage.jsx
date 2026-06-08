import { useState, useRef, useEffect } from "react";
import "./ProfilePage.css";

const GRADE_OPTIONS = ["大一","大二","大三","大四","研究生"];
const STAGE_OPTIONS = ["入门了解","课堂跟上","考试掌握","项目实战","深入精通"];
const ANSWER_STYLE_OPTIONS = ["通俗易懂","严谨学术","代码优先","案例教学"];
const DETAIL_OPTIONS = ["简洁","标准","详细"];
const REF_PREF_OPTIONS = ["优先引用资料库","综合知识库和资料","不限制来源"];
const DAILY_MINUTES_OPTS = [15,30,60,90,120];
const PLAN_DISPLAY = { free:"普通用户", pro:"Pro 会员", admin:"管理员", developer:"开发者账号" };

function fmtDate(v) { if(!v) return ""; const d=new Date(v); return isNaN(d.getTime())?"":d.toLocaleDateString("zh-CN"); }
function fmtDateFull(v) { if(!v) return ""; const d=new Date(v); return isNaN(d.getTime())?"":d.toLocaleString("zh-CN"); }

export default function ProfilePage({ user, apiBase, onLogout, setPage, onProfileUpdate }) {
  const [profile, setProfile] = useState({});
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [confirmAction, setConfirmAction] = useState(null);
  const [quota, setQuota] = useState(null);
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [cloudAvatarUrl, setCloudAvatarUrl] = useState(null);

  const [pwdOpen, setPwdOpen] = useState(false);
  const [pwdForm, setPwdForm] = useState({ old_password:"", new_password:"", confirm_password:"" });
  const [pwdSaving, setPwdSaving] = useState(false);
  const [pwdError, setPwdError] = useState("");

  const [emailOpen, setEmailOpen] = useState(false);
  const [emailForm, setEmailForm] = useState({ email:"", code:"" });
  const [emailSending, setEmailSending] = useState(false);
  const [emailVerifying, setEmailVerifying] = useState(false);
  const [emailError, setEmailError] = useState("");
  const [emailCountdown, setEmailCountdown] = useState(0);

  useEffect(() => {
    if (emailCountdown <= 0) return;
    const t = setTimeout(() => setEmailCountdown(c => c-1), 1000);
    return () => clearTimeout(t);
  }, [emailCountdown]);

  const handleSendEmailCode = async () => {
    setEmailError(""); const e = emailForm.email.trim();
    if (!e || !e.includes("@")) { setEmailError("请输入有效的邮箱地址"); return; }
    setEmailSending(true);
    try {
      const res = await fetch(`${apiBase}/me/email/send-code?username=${encodeURIComponent(user.username)}`, {
        method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:e}),
      });
      const data = await res.json();
      if (!res.ok) { setEmailError(data.detail||"发送失败"); setEmailSending(false); return; }
      setEmailCountdown(60);
    } catch { setEmailError("网络错误"); }
    finally { setEmailSending(false); }
  };

  const handleVerifyEmail = async () => {
    setEmailError(""); const e=emailForm.email.trim(), c=emailForm.code.trim();
    if (!c) { setEmailError("请输入验证码"); return; }
    setEmailVerifying(true);
    try {
      const res = await fetch(`${apiBase}/me/email/verify?username=${encodeURIComponent(user.username)}`, {
        method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:e,code:c}),
      });
      const data = await res.json();
      if (!res.ok) { setEmailError(data.detail||"验证失败"); setEmailVerifying(false); return; }
      const updated = data.profile||data;
      setProfile(updated);
      try { const s=JSON.parse(localStorage.getItem("ai_study_platform_user")||"{}"); localStorage.setItem("ai_study_platform_user",JSON.stringify({...s,...updated})); } catch {}
      setEmailOpen(false);
      showToast("邮箱绑定成功");
    } catch { setEmailError("网络错误"); }
    finally { setEmailVerifying(false); }
  };

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(""), 2500); };

  const handleChangePassword = async () => {
    setPwdError("");
    const { old_password, new_password, confirm_password } = pwdForm;
    if (!old_password || !new_password || !confirm_password) { setPwdError("所有密码字段不能为空"); return; }
    if (new_password.length < 8) { setPwdError("新密码长度至少 8 位"); return; }
    if (new_password !== confirm_password) { setPwdError("两次输入的新密码不一致"); return; }
    if (new_password === old_password) { setPwdError("新密码不能与旧密码相同"); return; }
    setPwdSaving(true);
    try {
      const res = await fetch(`${apiBase}/me/password?username=${encodeURIComponent(user.username)}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password, new_password, confirm_password }),
      });
      const data = await res.json();
      if (!res.ok) { setPwdError(data.detail || "修改失败"); setPwdSaving(false); return; }
      setPwdOpen(false);
      setPwdForm({ old_password:"", new_password:"", confirm_password:"" });
      showToast("密码修改成功，请妥善保管新密码。");
    } catch { setPwdError("网络错误，请稍后重试"); }
    finally { setPwdSaving(false); }
  };
  const setDraftField = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  const loadData = () => {
    if (!user?.username) return;
    setLoading(true);
    Promise.all([
      fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`).then(r => r.json()),
      fetch(`${apiBase}/me/quota?username=${encodeURIComponent(user.username)}`).then(r => r.json()).catch(() => null),
    ]).then(([pData, qData]) => {
      const p = pData.profile || pData;
      setProfile(p);
      if (p.avatar_url && String(p.avatar_url).startsWith("/me/avatar/"))
        setCloudAvatarUrl(`${apiBase}${p.avatar_url}?username=${encodeURIComponent(user.username)}`);
      if (qData) setQuota(qData);
    }).catch(() => setProfile({ ...user })).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [user?.username]);

  const openEditModal = () => {
    setDraft({
      nickname: profile.nickname || "",
      school: profile.school || "",
      grade: profile.grade || "",
      major: profile.major || "",
      learning_direction: profile.learning_direction || "",
      default_course_id: profile.default_course_id || "",
      learning_goal_text: (Array.isArray(profile.learning_goals) ? profile.learning_goals.map(g => g.subject).join("、") : ""),
      daily_study_minutes: profile.daily_study_minutes || 60,
      learning_stage: profile.learning_stage || "",
      focus_courses: profile.focus_courses || "",
      ai_answer_style: profile.ai_answer_style || "",
      answer_detail_level: profile.answer_detail_level || "",
      material_reference_preference: profile.material_reference_preference || "",
    });
    setEditOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const body = {
        nickname: draft.nickname || "",
        school: draft.school || "",
        grade: draft.grade || "",
        major: draft.major || "",
        learning_direction: draft.learning_direction || "",
        default_course_id: draft.default_course_id || "",
        learning_stage: draft.learning_stage || "",
        daily_study_minutes: draft.daily_study_minutes || 0,
        ai_answer_style: draft.ai_answer_style || "",
        answer_detail_level: draft.answer_detail_level || "",
        material_reference_preference: draft.material_reference_preference || "",
        focus_courses: draft.focus_courses || "",
      };
      const res = await fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "保存失败"); setSaving(false); return; }
      const updated = data.profile || data;
      setProfile(updated);
      try { const s = JSON.parse(localStorage.getItem("ai_study_platform_user")||"{}"); localStorage.setItem("ai_study_platform_user", JSON.stringify({...s,...updated})); } catch {}
      if (onProfileUpdate) onProfileUpdate(updated);
      setEditOpen(false);
      showToast("保存成功");
    } catch { showToast("网络错误"); }
    finally { setSaving(false); }
  };

  const handleAvatarUpload = async (e) => {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    if (!["image/jpeg","image/png","image/webp","image/gif"].includes(file.type)) { showToast("仅支持 JPG/PNG/WebP/GIF"); return; }
    if (file.size > 3*1024*1024) { showToast("文件不能超过 3MB"); return; }
    setUploading(true);
    try {
      const fd = new FormData(); fd.append("file",file); fd.append("username",user.username);
      const res = await fetch(`${apiBase}/me/avatar`, { method:"POST", body:fd });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail||"上传失败"); return; }
      if (data.avatar_url) setCloudAvatarUrl(`${apiBase}${data.avatar_url}?username=${encodeURIComponent(user.username)}`);
      if (data.profile && onProfileUpdate) onProfileUpdate(data.profile);
      showToast("头像已更新");
    } catch { showToast("网络错误"); }
    finally { setUploading(false); }
  };

  const displayName = profile.nickname || user?.username || "同学";
  const initial = displayName.charAt(0);
  const planLabel = PLAN_DISPLAY[profile.plan] || (profile.is_admin ? "管理员" : "普通用户");

  if (loading) return <div className="pp-shell"><div className="pp-loading">加载中...</div></div>;

  return (
    <div className="pp-shell">
      {toast && <div className="pp-toast">{toast}</div>}
      <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={handleAvatarUpload} style={{display:"none"}} />

      {/* Confirm modal */}
      {confirmAction && (
        <div className="pp-overlay" onClick={() => setConfirmAction(null)}>
          <div className="pp-modal" onClick={e => e.stopPropagation()}>
            <h3>{confirmAction.title}</h3><p>{confirmAction.desc}</p>
            <div className="pp-modal-actions">
              <button className="pp-btn pp-btn-cancel" onClick={() => setConfirmAction(null)}>取消</button>
              <button className="pp-btn pp-btn-danger" onClick={() => { confirmAction.action(); setConfirmAction(null); }}>确认</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Edit Modal ── */}
      {editOpen && (
        <div className="pp-overlay">
          <div className="pp-modal pp-modal-edit" onClick={e => e.stopPropagation()}>
            <div className="pp-modal-header">
              <div>
                <h2>编辑资料与学习设置</h2>
                <p>修改完成后点击保存，所有字段将同步到 AI 问答和学习计划。</p>
              </div>
              <button className="pp-modal-close" onClick={() => setEditOpen(false)}>×</button>
            </div>
            <div className="pp-modal-body">
              <div className="pp-form-section">
                <div className="pp-form-section-title"><span>👤</span><strong>基础资料</strong></div>
                <div className="pp-form-grid">
                  <label className="pp-form-field"><span>昵称</span><input className="pp-field" value={draft.nickname} onChange={e => setDraftField("nickname", e.target.value)} placeholder="输入昵称" maxLength={30} /></label>
                  <label className="pp-form-field"><span>学校</span><input className="pp-field" value={draft.school} onChange={e => setDraftField("school", e.target.value)} placeholder="输入学校名称" maxLength={100} /></label>
                  <label className="pp-form-field"><span>年级</span><select className="pp-field pp-field-select" value={draft.grade} onChange={e => setDraftField("grade", e.target.value)}>{GRADE_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}<option value="">未设置</option></select></label>
                  <label className="pp-form-field"><span>专业</span><input className="pp-field" value={draft.major} onChange={e => setDraftField("major", e.target.value)} placeholder="输入专业" maxLength={50} /></label>
                  <label className="pp-form-field pp-form-field-full"><span>学习方向</span><input className="pp-field" value={draft.learning_direction} onChange={e => setDraftField("learning_direction", e.target.value)} placeholder="例如：后端开发、数据分析、人工智能" maxLength={100} /></label>
                </div>
              </div>
              <div className="pp-form-section">
                <div className="pp-form-section-title"><span>⚙️</span><strong>学习设置</strong></div>
                <div className="pp-form-grid">
                  <label className="pp-form-field pp-form-field-full"><span>每日学习时长</span>
                    <div className="pp-chips">{DAILY_MINUTES_OPTS.map(m => <button key={m} className={`pp-chip ${draft.daily_study_minutes===m?"pp-chip--active":""}`} onClick={() => setDraftField("daily_study_minutes",m)} type="button">{m} 分钟</button>)}</div>
                  </label>
                  <label className="pp-form-field"><span>当前学习阶段</span><select className="pp-field pp-field-select" value={draft.learning_stage} onChange={e => setDraftField("learning_stage", e.target.value)}>{STAGE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select></label>
                  <label className="pp-form-field"><span>AI 回答风格</span><select className="pp-field pp-field-select" value={draft.ai_answer_style} onChange={e => setDraftField("ai_answer_style", e.target.value)}>{ANSWER_STYLE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select></label>
                  <label className="pp-form-field"><span>回答详细程度</span><select className="pp-field pp-field-select" value={draft.answer_detail_level} onChange={e => setDraftField("answer_detail_level", e.target.value)}>{DETAIL_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select></label>
                  <label className="pp-form-field"><span>默认资料引用策略</span><select className="pp-field pp-field-select" value={draft.material_reference_preference} onChange={e => setDraftField("material_reference_preference", e.target.value)}>{REF_PREF_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select></label>
                  <label className="pp-form-field pp-form-field-full"><span>重点课程</span><input className="pp-field" value={draft.focus_courses} onChange={e => setDraftField("focus_courses", e.target.value)} placeholder="例如：离散数学、数据结构、C语言" maxLength={200} /></label>
                </div>
              </div>
            </div>
            <div className="pp-modal-footer">
              <button className="pp-btn pp-btn-cancel" onClick={() => setEditOpen(false)} disabled={saving}>取消</button>
              <button className="pp-btn pp-btn-primary" onClick={handleSave} disabled={saving}>{saving ? "保存中..." : "保存全部更改"}</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Password Modal ── */}
      {pwdOpen && (
        <div className="pp-overlay">
          <div className="pp-modal pp-modal-pwd" onClick={e => e.stopPropagation()}>
            <div className="pp-modal-header">
              <div><h2>修改密码</h2><p>请输入当前密码并设置新密码</p></div>
              <button className="pp-modal-close" onClick={() => { setPwdOpen(false); setPwdForm({old_password:"",new_password:"",confirm_password:""}); }}>×</button>
            </div>
            <div className="pp-modal-body">
              <div className="pp-pwd-form">
                <label className="pp-pwd-field"><span>当前密码</span><input className="pp-field" type="password" value={pwdForm.old_password} onChange={e => setPwdForm(p => ({...p, old_password: e.target.value}))} placeholder="输入当前密码" /></label>
                <label className="pp-pwd-field"><span>新密码</span><input className="pp-field" type="password" value={pwdForm.new_password} onChange={e => setPwdForm(p => ({...p, new_password: e.target.value}))} placeholder="输入新密码，至少 8 位" /></label>
                <label className="pp-pwd-field"><span>确认新密码</span><input className="pp-field" type="password" value={pwdForm.confirm_password} onChange={e => setPwdForm(p => ({...p, confirm_password: e.target.value}))} placeholder="再次输入新密码" /></label>
              </div>
              {pwdError && <div className="pp-pwd-error">{pwdError}</div>}
            </div>
            <div className="pp-modal-footer">
              <button className="pp-btn pp-btn-cancel" onClick={() => { setPwdOpen(false); setPwdForm({old_password:"",new_password:"",confirm_password:""}); }} disabled={pwdSaving}>取消</button>
              <button className="pp-btn pp-btn-primary" onClick={handleChangePassword} disabled={pwdSaving}>{pwdSaving ? "修改中..." : "确认修改"}</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Email Modal ── */}
      {emailOpen && (
        <div className="pp-overlay">
          <div className="pp-modal pp-modal-pwd" onClick={e => e.stopPropagation()}>
            <div className="pp-modal-header">
              <div><h2>{profile.email?"更换邮箱":"绑定邮箱"}</h2><p>输入邮箱地址并验证</p></div>
              <button className="pp-modal-close" onClick={()=>{setEmailOpen(false);setEmailForm({email:"",code:""});setEmailCountdown(0);}}>×</button>
            </div>
            <div className="pp-modal-body">
              <div className="pp-pwd-form">
                <label className="pp-pwd-field"><span>邮箱地址</span>
                  <div style={{display:"flex",gap:10}}>
                    <input className="pp-field" type="email" value={emailForm.email} onChange={e=>setEmailForm(p=>({...p,email:e.target.value}))} placeholder="输入邮箱地址" style={{flex:1}} />
                    <button className="pp-btn pp-btn-outline" style={{height:42,flexShrink:0}} onClick={handleSendEmailCode} disabled={emailSending||emailCountdown>0}>
                      {emailCountdown>0?`${emailCountdown}s`:"发送验证码"}
                    </button>
                  </div>
                </label>
                <label className="pp-pwd-field"><span>验证码</span><input className="pp-field" value={emailForm.code} onChange={e=>setEmailForm(p=>({...p,code:e.target.value}))} placeholder="输入 6 位验证码" maxLength={6} /></label>
              </div>
              {emailError && <div className="pp-pwd-error">{emailError}</div>}
            </div>
            <div className="pp-modal-footer">
              <button className="pp-btn pp-btn-cancel" onClick={()=>{setEmailOpen(false);setEmailForm({email:"",code:""});setEmailCountdown(0);}}>取消</button>
              <button className="pp-btn pp-btn-primary" onClick={handleVerifyEmail} disabled={emailVerifying}>{emailVerifying?"验证中...":"确认绑定"}</button>
            </div>
          </div>
        </div>
      )}

      <div className="pp-header"><button className="pp-back-btn" onClick={() => setPage("home")}>← 返回首页</button><h1 className="pp-title">账号中心</h1></div>

      <div className="pp-grid">
        {/* Top card */}
        <div className="pp-card pp-top-card">
          <div className="pp-top-avatar" onClick={() => fileInputRef.current?.click()} title="更换头像">
            {cloudAvatarUrl ? <img src={cloudAvatarUrl} alt="头像" className="pp-avatar-img" /> : <div className="pp-avatar-letter">{initial}</div>}
            <div className="pp-avatar-overlay"><span>{uploading ? "⏳" : "📷"}</span></div>
          </div>
          <div className="pp-top-info">
            <div className="pp-top-name-row"><h2 className="pp-top-name">{displayName}</h2><span className={`pp-badge ${profile.is_admin?"pp-badge-admin":profile.plan&&profile.plan!=="free"?"pp-badge-pro":"pp-badge-free"}`}>{planLabel}</span></div>
            <p className="pp-top-welcome">欢迎回来，继续你的学习之旅</p>
            <div className="pp-top-meta"><span>📅 注册时间：{fmtDate(profile.created_at)||"—"}</span><span>🕐 最近登录：{fmtDateFull(profile.last_login_at)||"—"}</span><span className="pp-status-active">🟢 活跃学习中</span></div>
          </div>
          <div className="pp-top-actions">
            <button className="pp-btn pp-btn-outline" onClick={() => fileInputRef.current?.click()} disabled={uploading}>{uploading ? "上传中..." : "更换头像"}</button>
            <button className="pp-btn pp-btn-primary" onClick={openEditModal}>编辑资料</button>
          </div>
        </div>

        {/* Left */}
        <div className="pp-col">
          <div className="pp-card"><h3 className="pp-card-title"><span className="pp-card-icon">👤</span>基础资料</h3>
            <div className="pp-rows">
              <InfoRow icon="🔑" label="用户名" value={user?.username||"—"} />
              <InfoRow icon="✏️" label="昵称" value={profile.nickname||"未填写"} />
              <InfoRow icon="🏫" label="学校" value={profile.school||"未填写"} />
              <InfoRow icon="🎓" label="年级" value={profile.grade||"未填写"} />
              <InfoRow icon="📘" label="专业" value={profile.major||"未填写"} />
              <InfoRow icon="🧭" label="学习方向" value={profile.learning_direction||"未填写"} />
            </div>
          </div>
          <div className="pp-card"><h3 className="pp-card-title"><span className="pp-card-icon">⚙️</span>学习设置</h3>
            <div className="pp-rows">
              <InfoRow icon="⏱️" label="每日学习时长" value={profile.daily_study_minutes?`${profile.daily_study_minutes} 分钟`:"未设置"} />
              <InfoRow icon="📊" label="当前学习阶段" value={profile.learning_stage||"未设置"} />
              <InfoRow icon="📚" label="重点课程" value={profile.focus_courses||"未设置"} />
              <InfoRow icon="💬" label="AI 回答风格" value={profile.ai_answer_style||"未设置"} />
              <InfoRow icon="📝" label="回答详细程度" value={profile.answer_detail_level||"未设置"} />
              <InfoRow icon="📎" label="默认资料引用策略" value={profile.material_reference_preference||"未设置"} />
            </div>
          </div>
        </div>

        {/* Right */}
        <div className="pp-col">
          <div className="pp-card"><h3 className="pp-card-title"><span className="pp-card-icon">🔒</span>账号安全</h3>
            <div className="pp-rows">
              <InfoRow icon="📱" label="手机号" value="暂未绑定"><button className="pp-btn pp-btn-mini" onClick={()=>showToast("手机号绑定需要接入短信服务，暂未开放。")}>绑定</button></InfoRow>
              <InfoRow icon="📧" label="邮箱" value={profile.email||"暂未绑定"}><button className="pp-btn pp-btn-mini" onClick={()=>{setEmailForm({email:profile.email||"",code:""});setEmailError("");setEmailCountdown(0);setEmailOpen(true);}}>{profile.email?"更换":"绑定"}</button></InfoRow>
              <InfoRow icon="🔑" label="密码" value="●●●●●●"><button className="pp-btn pp-btn-mini" onClick={()=>{setPwdForm({old_password:"",new_password:"",confirm_password:""});setPwdError("");setPwdOpen(true);}}>修改密码</button></InfoRow>
              <InfoRow icon="💻" label="登录设备" value="当前设备 — Windows Chrome" />
            </div>
          </div>
          <div className="pp-card pp-quota-card"><h3 className="pp-card-title"><span className="pp-card-icon">💎</span>会员与额度</h3>
            <div className="pp-quota-grid">
              <div className="pp-quota-item"><span className="pp-quota-val">{planLabel}</span><span className="pp-quota-lbl">当前套餐</span></div>
              <div className="pp-quota-item"><span className="pp-quota-val">{quota?.daily?.used??"—"}</span><span className="pp-quota-lbl">今日 AI 调用</span></div>
              <div className="pp-quota-item"><span className="pp-quota-val">{quota?.daily?.remaining??"—"}</span><span className="pp-quota-lbl">剩余额度</span></div>
              <div className="pp-quota-item"><span className="pp-quota-val">{quota?.materials?.used??"—"} / {quota?.materials?.limit??"—"}</span><span className="pp-quota-lbl">资料上传</span></div>
            </div>
            <button className="pp-btn pp-btn-outline" style={{marginTop:12,width:"100%"}} onClick={()=>setPage("quotaCenter")}>查看我的额度 →</button>
          </div>
          <div className="pp-card"><h3 className="pp-card-title"><span className="pp-card-icon">🗄️</span>隐私与数据</h3>
            <div className="pp-rows">
              <InfoRow icon="🗑️" label="清空聊天记录" value=""><button className="pp-btn pp-btn-mini pp-btn-warn" onClick={()=>setConfirmAction({title:"清空聊天记录",desc:"此操作不可恢复",action:()=>showToast("功能开发中")})}>清空</button></InfoRow>
              <InfoRow icon="📝" label="清空学习记录" value=""><button className="pp-btn pp-btn-mini pp-btn-warn" onClick={()=>setConfirmAction({title:"清空学习记录",desc:"此操作不可恢复",action:()=>showToast("功能开发中")})}>清空</button></InfoRow>
              <InfoRow icon="✏️" label="清空练习记录" value=""><button className="pp-btn pp-btn-mini pp-btn-warn" onClick={()=>setConfirmAction({title:"清空练习记录",desc:"此操作不可恢复",action:()=>showToast("功能开发中")})}>清空</button></InfoRow>
            </div>
          </div>
          <div className="pp-card pp-danger-card"><h3 className="pp-card-title" style={{color:"#b91c1c"}}><span className="pp-card-icon">⚠️</span>账号操作</h3>
            <div className="pp-danger-row"><div><div className="pp-danger-title">退出登录</div><div className="pp-danger-desc">退出后需要重新登录</div></div><button className="pp-btn pp-btn-danger" onClick={onLogout}>退出登录</button></div>
            <div className="pp-danger-row" style={{marginTop:12,paddingTop:12,borderTop:"1px solid #fecaca"}}><div><div className="pp-danger-title">注销账号</div><div className="pp-danger-desc">永久删除账号及所有数据</div></div><button className="pp-btn pp-btn-danger-outline" onClick={()=>setConfirmAction({title:"注销账号",desc:"永久删除不可恢复",action:()=>showToast("注销功能需要后端支持，暂未开放")})}>注销账号</button></div>
          </div>
        </div>
      </div>
    </div>
  );
}

function InfoRow({ icon, label, value, children }) {
  return <div className="pp-row"><span className="pp-row-label"><span className="pp-row-icon">{icon}</span>{label}</span><span className="pp-row-value">{value}</span>{children}</div>;
}
