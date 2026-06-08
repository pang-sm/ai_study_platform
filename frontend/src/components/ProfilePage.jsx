import { useState, useRef, useEffect } from "react";
import "./ProfilePage.css";

const GRADE_OPTIONS = ["大一", "大二", "大三", "大四", "研究生"];
const STAGE_OPTIONS = ["入门了解", "课堂跟上", "考试掌握", "项目实战", "深入精通"];
const ANSWER_STYLE_OPTIONS = ["通俗易懂", "严谨学术", "代码优先", "案例教学"];
const DETAIL_OPTIONS = ["简洁", "标准", "详细"];
const REF_PREF_OPTIONS = ["优先引用资料库", "综合知识库和资料", "不限制来源"];
const DAILY_MINUTES_OPTS = [15, 30, 60, 90, 120];
const PLAN_DISPLAY = { free: "普通用户", pro: "Pro 会员", admin: "管理员", developer: "开发者账号" };

function fmtDate(v) { if (!v) return ""; const d = new Date(v); return isNaN(d.getTime()) ? "" : d.toLocaleDateString("zh-CN"); }
function fmtDateFull(v) { if (!v) return ""; const d = new Date(v); return isNaN(d.getTime()) ? "" : d.toLocaleString("zh-CN"); }

export default function ProfilePage({ user, apiBase, onLogout, setPage, onProfileUpdate }) {
  const [profile, setProfile] = useState({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState("");
  const [confirmAction, setConfirmAction] = useState(null);
  const [quota, setQuota] = useState(null);
  const fileInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [cloudAvatarUrl, setCloudAvatarUrl] = useState(null);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(""), 2500); };

  // Load profile + quota
  const loadData = () => {
    if (!user?.username) return;
    setLoading(true);
    Promise.all([
      fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`).then(r => r.json()),
      fetch(`${apiBase}/me/quota?username=${encodeURIComponent(user.username)}`).then(r => r.json()).catch(() => null),
    ]).then(([pData, qData]) => {
      const p = pData.profile || pData;
      setProfile(p);
      if (p.avatar_url && String(p.avatar_url).startsWith("/me/avatar/")) {
        setCloudAvatarUrl(`${apiBase}${p.avatar_url}?username=${encodeURIComponent(user.username)}`);
      }
      if (qData) setQuota(qData);
    }).catch(() => {
      setProfile({ ...user });
    }).finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, [user?.username]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const body = {
        nickname: profile.nickname || "",
        grade: profile.grade || "",
        major: profile.major || "",
        school: profile.school || "",
        learning_direction: profile.learning_direction || "",
        default_course_id: profile.default_course_id || "",
        learning_stage: profile.learning_stage || "",
        daily_study_minutes: profile.daily_study_minutes || 0,
        ai_answer_style: profile.ai_answer_style || "",
        answer_detail_level: profile.answer_detail_level || "",
        material_reference_preference: profile.material_reference_preference || "",
        focus_courses: profile.focus_courses || "",
      };
      const res = await fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "保存失败"); return; }
      const updated = data.profile || data;
      setProfile(updated);
      try { const stored = JSON.parse(localStorage.getItem("ai_study_platform_user") || "{}"); localStorage.setItem("ai_study_platform_user", JSON.stringify({ ...stored, ...updated })); } catch {}
      if (onProfileUpdate) onProfileUpdate(updated);
      setEditing(false);
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
      const fd = new FormData(); fd.append("file", file); fd.append("username", user.username);
      const res = await fetch(`${apiBase}/me/avatar`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "上传失败"); return; }
      if (data.avatar_url) setCloudAvatarUrl(`${apiBase}${data.avatar_url}?username=${encodeURIComponent(user.username)}`);
      if (data.profile && onProfileUpdate) onProfileUpdate(data.profile);
      showToast("头像已更新");
    } catch { showToast("网络错误"); }
    finally { setUploading(false); }
  };

  const displayName = profile.nickname || user?.username || "同学";
  const initial = displayName.charAt(0);
  const planLabel = PLAN_DISPLAY[profile.plan] || (profile.is_admin ? "管理员" : "普通用户");
  const avatarSrc = cloudAvatarUrl || null;

  const setField = (k, v) => setProfile(p => ({ ...p, [k]: v }));

  if (loading) return <div className="pp-shell"><div className="pp-loading">加载中...</div></div>;

  return (
    <div className="pp-shell">
      {toast && <div className="pp-toast">{toast}</div>}
      <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={handleAvatarUpload} style={{ display: "none" }} />

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

      {/* Header */}
      <div className="pp-header"><button className="pp-back-btn" onClick={() => setPage("home")}>← 返回首页</button><h1 className="pp-title">账号中心</h1></div>

      <div className="pp-grid">
        {/* ═══ Top Profile Card ═══ */}
        <div className="pp-card pp-top-card">
          <div className="pp-top-avatar" onClick={() => fileInputRef.current?.click()} title="更换头像">
            {avatarSrc ? <img src={avatarSrc} alt="头像" className="pp-avatar-img" /> : <div className="pp-avatar-letter">{initial}</div>}
            <div className="pp-avatar-overlay"><span>{uploading ? "⏳" : "📷"}</span></div>
          </div>
          <div className="pp-top-info">
            <div className="pp-top-name-row">
              <h2 className="pp-top-name">{displayName}</h2>
              <span className={`pp-badge ${profile.is_admin ? "pp-badge-admin" : profile.plan && profile.plan !== "free" ? "pp-badge-pro" : "pp-badge-free"}`}>{planLabel}</span>
            </div>
            <p className="pp-top-welcome">欢迎回来，继续你的学习之旅</p>
            <div className="pp-top-meta">
              <span>📅 注册时间：{fmtDate(profile.created_at) || "—"}</span>
              <span>🕐 最近登录：{fmtDateFull(profile.last_login_at) || "—"}</span>
              <span className="pp-status-active">🟢 活跃学习中</span>
            </div>
          </div>
          <div className="pp-top-actions">
            <button className="pp-btn pp-btn-outline" onClick={() => fileInputRef.current?.click()} disabled={uploading}>{uploading ? "上传中..." : "更换头像"}</button>
            <button className="pp-btn pp-btn-primary" onClick={() => setEditing(true)}>编辑资料</button>
          </div>
        </div>

        {/* ═══ Left Column ═══ */}
        <div className="pp-col">
          {/* Basic Info */}
          <div className="pp-card">
            <h3 className="pp-card-title"><span className="pp-card-icon">👤</span>基础资料</h3>
            <div className="pp-rows">
              <InfoRow icon="🔑" label="用户名" value={user?.username || "—"} />
              <InfoRow icon="✏️" label="昵称" value={profile.nickname || "未填写"} editing={editing}><input className="pp-input" value={profile.nickname || ""} onChange={e => setField("nickname", e.target.value)} placeholder="输入昵称" maxLength={30} /></InfoRow>
              <InfoRow icon="🏫" label="学校" value={profile.school || "未填写"} editing={editing}><input className="pp-input" value={profile.school || ""} onChange={e => setField("school", e.target.value)} placeholder="输入学校名称" maxLength={100} /></InfoRow>
              <InfoRow icon="🎓" label="年级" value={profile.grade || "未填写"} editing={editing}>
                <select className="pp-input pp-select" value={profile.grade || ""} onChange={e => setField("grade", e.target.value)}>{GRADE_OPTIONS.map(g => <option key={g} value={g}>{g}</option>)}<option value="">未设置</option></select>
              </InfoRow>
              <InfoRow icon="📘" label="专业" value={profile.major || "未填写"} editing={editing}><input className="pp-input" value={profile.major || ""} onChange={e => setField("major", e.target.value)} placeholder="输入专业" maxLength={50} /></InfoRow>
              <InfoRow icon="🧭" label="学习方向" value={profile.learning_direction || "未填写"} editing={editing}><input className="pp-input" value={profile.learning_direction || ""} onChange={e => setField("learning_direction", e.target.value)} placeholder="例如：后端开发、数据分析" maxLength={100} /></InfoRow>
            </div>
          </div>

          {/* Learning Settings */}
          <div className="pp-card">
            <h3 className="pp-card-title"><span className="pp-card-icon">⚙️</span>学习设置</h3>
            <div className="pp-rows">
              <InfoRow icon="🎯" label="学习目标" value={profile.learning_goals ? JSON.parse(profile.learning_goals).map(g => g.subject).join("、") : "未设置"} editing={editing}>
                <input className="pp-input" value={profile.learning_goal_text || ""} onChange={e => setField("learning_goal_text", e.target.value)} placeholder="例如：通过离散数学期末考试" />
              </InfoRow>
              <InfoRow icon="⏱️" label="每日学习时长" value={profile.daily_study_minutes ? `${profile.daily_study_minutes} 分钟` : "未设置"} editing={editing}>
                <div className="pp-chips">{DAILY_MINUTES_OPTS.map(m => <button key={m} className={`pp-chip ${profile.daily_study_minutes === m ? "pp-chip--active" : ""}`} onClick={() => setField("daily_study_minutes", m)} type="button">{m} 分钟</button>)}</div>
              </InfoRow>
              <InfoRow icon="📊" label="当前学习阶段" value={profile.learning_stage || "未设置"} editing={editing}>
                <select className="pp-input pp-select" value={profile.learning_stage || ""} onChange={e => setField("learning_stage", e.target.value)}>{STAGE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select>
              </InfoRow>
              <InfoRow icon="📚" label="重点课程" value={profile.focus_courses || "未设置"} editing={editing}><input className="pp-input" value={profile.focus_courses || ""} onChange={e => setField("focus_courses", e.target.value)} placeholder="例如：离散数学 / 数据结构 / C语言" maxLength={200} /></InfoRow>
              <InfoRow icon="💬" label="AI 回答风格" value={profile.ai_answer_style || "未设置"} editing={editing}>
                <select className="pp-input pp-select" value={profile.ai_answer_style || ""} onChange={e => setField("ai_answer_style", e.target.value)}>{ANSWER_STYLE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select>
              </InfoRow>
              <InfoRow icon="📝" label="回答详细程度" value={profile.answer_detail_level || "未设置"} editing={editing}>
                <select className="pp-input pp-select" value={profile.answer_detail_level || ""} onChange={e => setField("answer_detail_level", e.target.value)}>{DETAIL_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select>
              </InfoRow>
              <InfoRow icon="📎" label="默认资料引用策略" value={profile.material_reference_preference || "未设置"} editing={editing}>
                <select className="pp-input pp-select" value={profile.material_reference_preference || ""} onChange={e => setField("material_reference_preference", e.target.value)}>{REF_PREF_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}<option value="">未设置</option></select>
              </InfoRow>
            </div>
          </div>
        </div>

        {/* ═══ Right Column ═══ */}
        <div className="pp-col">
          {/* Account Security */}
          <div className="pp-card">
            <h3 className="pp-card-title"><span className="pp-card-icon">🔒</span>账号安全</h3>
            <div className="pp-rows">
              <InfoRow icon="📱" label="手机号" value="暂未绑定"><button className="pp-btn pp-btn-mini" onClick={() => showToast("功能开发中")}>绑定</button></InfoRow>
              <InfoRow icon="📧" label="邮箱" value="暂未绑定"><button className="pp-btn pp-btn-mini" onClick={() => showToast("功能开发中")}>绑定</button></InfoRow>
              <InfoRow icon="🔑" label="密码" value="●●●●●●"><button className="pp-btn pp-btn-mini" onClick={() => showToast("修改密码功能开发中")}>修改</button></InfoRow>
              <InfoRow icon="💻" label="登录设备" value="当前设备 — Windows Chrome" />
            </div>
          </div>

          {/* Quota Summary */}
          <div className="pp-card pp-quota-card">
            <h3 className="pp-card-title"><span className="pp-card-icon">💎</span>会员与额度</h3>
            <div className="pp-quota-grid">
              <div className="pp-quota-item"><span className="pp-quota-val">{planLabel}</span><span className="pp-quota-lbl">当前套餐</span></div>
              <div className="pp-quota-item"><span className="pp-quota-val">{quota?.daily?.used ?? "—"}</span><span className="pp-quota-lbl">今日 AI 调用</span></div>
              <div className="pp-quota-item"><span className="pp-quota-val">{quota?.daily?.remaining ?? "—"}</span><span className="pp-quota-lbl">剩余额度</span></div>
              <div className="pp-quota-item"><span className="pp-quota-val">{quota?.materials?.used ?? "—"} / {quota?.materials?.limit ?? "—"}</span><span className="pp-quota-lbl">资料上传</span></div>
            </div>
            <button className="pp-btn pp-btn-outline" style={{ marginTop: 12, width: "100%" }} onClick={() => setPage("quotaCenter")}>查看我的额度 →</button>
          </div>

          {/* Privacy & Data */}
          <div className="pp-card">
            <h3 className="pp-card-title"><span className="pp-card-icon">🗄️</span>隐私与数据</h3>
            <div className="pp-rows">
              <InfoRow icon="📥" label="导出学习数据" value=""><button className="pp-btn pp-btn-mini" onClick={() => showToast("功能开发中")}>导出</button></InfoRow>
              <InfoRow icon="🗑️" label="清空聊天记录" value=""><button className="pp-btn pp-btn-mini pp-btn-warn" onClick={() => setConfirmAction({ title:"清空聊天记录", desc:"此操作不可恢复，确认清空所有聊天记录？", action: () => showToast("功能开发中") })}>清空</button></InfoRow>
              <InfoRow icon="📝" label="清空学习记录" value=""><button className="pp-btn pp-btn-mini pp-btn-warn" onClick={() => setConfirmAction({ title:"清空学习记录", desc:"此操作不可恢复，确认清空所有学习记录？", action: () => showToast("功能开发中") })}>清空</button></InfoRow>
              <InfoRow icon="✏️" label="清空练习记录" value=""><button className="pp-btn pp-btn-mini pp-btn-warn" onClick={() => setConfirmAction({ title:"清空练习记录", desc:"此操作不可恢复，确认清空所有练习记录？", action: () => showToast("功能开发中") })}>清空</button></InfoRow>
            </div>
          </div>

          {/* Danger Zone */}
          <div className="pp-card pp-danger-card">
            <h3 className="pp-card-title" style={{ color: "#b91c1c" }}><span className="pp-card-icon">⚠️</span>账号操作</h3>
            <div className="pp-danger-row">
              <div><div className="pp-danger-title">退出登录</div><div className="pp-danger-desc">退出后需要重新登录</div></div>
              <button className="pp-btn pp-btn-danger" onClick={onLogout}>退出登录</button>
            </div>
            <div className="pp-danger-row" style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #fecaca" }}>
              <div><div className="pp-danger-title">注销账号</div><div className="pp-danger-desc">永久删除账号及所有数据</div></div>
              <button className="pp-btn pp-btn-danger-outline" onClick={() => setConfirmAction({ title:"注销账号", desc:"此操作将永久删除你的账号和所有数据，不可恢复。确认注销？", action: () => showToast("注销功能需要后端支持，暂未开放") })}>注销账号</button>
            </div>
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {editing && (
        <div className="pp-overlay" onClick={() => setEditing(false)}>
          <div className="pp-modal pp-modal-wide" onClick={e => e.stopPropagation()}>
            <button className="pp-modal-close" onClick={() => setEditing(false)}>×</button>
            <h2>编辑资料与学习设置</h2>
            <div className="pp-modal-body">
              {["nickname","school","grade","major","learning_direction","focus_courses","learning_stage","daily_study_minutes","ai_answer_style","answer_detail_level","material_reference_preference"].map(k => null)}
              <p style={{ color: "#64748b", fontSize: 14, marginBottom: 12 }}>修改完成后点击保存，所有字段将同步到 AI 问答和学习计划。</p>
              {/* Reuse the editing rows — simplified: just a save/cancel bar */}
            </div>
            <div className="pp-modal-actions">
              <button className="pp-btn pp-btn-cancel" onClick={() => setEditing(false)} disabled={saving}>取消</button>
              <button className="pp-btn pp-btn-primary" onClick={handleSave} disabled={saving}>{saving ? "保存中..." : "保存全部更改"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ icon, label, value, editing, children }) {
  return (
    <div className="pp-row">
      <span className="pp-row-label"><span className="pp-row-icon">{icon}</span>{label}</span>
      {editing && children ? <span className="pp-row-edit">{children}</span> : <span className="pp-row-value">{value}</span>}
    </div>
  );
}
