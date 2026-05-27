import { useState, useRef, useEffect } from "react";
import "./ProfilePage.css";

const GRADE_OPTIONS = ["大一", "大二", "大三", "大四", "研究生"];

function getLocalAvatar(username) {
  try {
    return localStorage.getItem(`avatar:${username}`);
  } catch {
    return null;
  }
}

function setLocalAvatar(username, dataUrl) {
  try {
    if (dataUrl) {
      localStorage.setItem(`avatar:${username}`, dataUrl);
    } else {
      localStorage.removeItem(`avatar:${username}`);
    }
  } catch {
    // storage full or unavailable
  }
}

function syncUserToStorage(updatedUser) {
  try {
    const stored = localStorage.getItem("ai_study_platform_user");
    if (stored) {
      const parsed = JSON.parse(stored);
      const merged = { ...parsed, ...updatedUser };
      localStorage.setItem("ai_study_platform_user", JSON.stringify(merged));
    }
  } catch {
    // ignore
  }
}

export default function ProfilePage({ user, apiBase, onLogout, setPage, onProfileUpdate }) {
  // Cloud avatar_url from profile — primary source
  const [cloudAvatarUrl, setCloudAvatarUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState("");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef(null);

  // Profile form loaded from backend
  const [profile, setProfile] = useState({
    nickname: user?.nickname || "",
    grade: user?.grade || "",
    major: user?.major || "",
  });

  // Snapshot for cancel
  const [savedProfile, setSavedProfile] = useState({ ...profile });

  // ── Load profile from backend on mount ──

  useEffect(() => {
    if (!user?.username) return;
    fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load profile");
        return res.json();
      })
      .then((data) => {
        const p = data.profile || data;
        setProfile({
          nickname: p.nickname || "",
          grade: p.grade || "",
          major: p.major || "",
        });
        setSavedProfile({
          nickname: p.nickname || "",
          grade: p.grade || "",
          major: p.major || "",
        });
        // Cloud avatar — primary source
        if (p.avatar_url && String(p.avatar_url).startsWith("/me/avatar/")) {
          setCloudAvatarUrl(`${apiBase}${p.avatar_url}?username=${encodeURIComponent(user.username)}`);
        }
      })
      .catch(() => {
        setProfile({
          nickname: user?.nickname || "",
          grade: user?.grade || "",
          major: user?.major || "",
        });
        setSavedProfile({
          nickname: user?.nickname || "",
          grade: user?.grade || "",
          major: user?.major || "",
        });
      });
  }, [user?.username, apiBase]);

  // ── Helpers ──

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  };

  // Avatar priority: cloud > localStorage fallback > letter
  const localFallback = getLocalAvatar(user?.username || "");
  const avatarSrc = cloudAvatarUrl || localFallback || null;
  const displayName = user?.nickname || user?.username || "同学";
  const initial = displayName.charAt(0);

  // ── Avatar upload to cloud ──

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;

    if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(file.type)) {
      showToast("仅支持 JPG、PNG、WebP 或 GIF 格式");
      return;
    }
    if (file.size > 3 * 1024 * 1024) {
      showToast("头像文件不能超过 3MB");
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("username", user.username);

      const res = await fetch(`${apiBase}/me/avatar`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        showToast(data.detail || "头像上传失败");
        return;
      }

      // Update cloud avatar URL
      if (data.avatar_url && String(data.avatar_url).startsWith("/me/avatar/")) {
        const newUrl = `${apiBase}${data.avatar_url}?username=${encodeURIComponent(user.username)}`;
        setCloudAvatarUrl(newUrl);
      }

      // Also save to localStorage as fallback
      if (data.profile?.avatar_url) {
        setLocalAvatar(user.username, null);
      }

      // Sync to parent (App.jsx) so topbar updates
      if (data.profile) {
        const p = data.profile;
        syncUserToStorage({
          avatar: p.avatar || "",
          avatar_url: p.avatar_url || null,
        });
        if (onProfileUpdate) {
          onProfileUpdate({
            avatar: p.avatar || "",
            avatar_url: p.avatar_url || null,
          });
        }
      }

      showToast("头像已更新");
    } catch {
      showToast("网络错误，上传失败");
    } finally {
      setUploading(false);
    }
  };

  // ── Edit actions ──

  const handleEdit = () => {
    setSavedProfile({ ...profile });
    setEditing(true);
  };

  const handleCancel = () => {
    setProfile({ ...savedProfile });
    setEditing(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: profile.nickname,
          grade: profile.grade,
          major: profile.major,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        showToast(data.detail || "保存失败，请稍后重试");
        return;
      }

      const updated = data.profile || data;
      const fresh = {
        nickname: updated.nickname || "",
        grade: updated.grade || "",
        major: updated.major || "",
      };
      setProfile(fresh);
      setSavedProfile(fresh);

      syncUserToStorage(fresh);

      // Notify parent to update user state
      if (onProfileUpdate) {
        onProfileUpdate(fresh);
      }

      setEditing(false);
      showToast("保存成功");
    } catch {
      showToast("网络错误，请稍后重试");
    } finally {
      setSaving(false);
    }
  };

  // ── Security items ──

  const securityItems = [
    { label: "手机号", value: "暂未绑定", action: "去绑定" },
    { label: "邮箱", value: "暂未绑定", action: "去绑定" },
    { label: "密码", value: "●●●●●●", action: "修改密码" },
  ];

  return (
    <div className="pp-shell">
      {/* Toast */}
      {toast && <div className="pp-toast">{toast}</div>}

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        onChange={handleFileChange}
        className="pp-hidden-input"
      />

      {/* Header */}
      <div className="pp-header">
        <button className="pp-back-btn" onClick={() => setPage("home")}>
          ← 返回首页
        </button>
        <h1 className="pp-title">个人主页</h1>
      </div>

      {/* ── Top avatar card (centered, no text beside avatar) ── */}
      <div className="pp-card pp-avatar-card">
        <div className="pp-avatar-wrap" onClick={() => !uploading && fileInputRef.current?.click()} title="点击更换头像">
          {avatarSrc ? (
            <img className="pp-avatar-img" src={avatarSrc} alt="头像" />
          ) : (
            <div className="pp-avatar-letter">{initial}</div>
          )}
          <div className="pp-avatar-overlay">
            <span>{uploading ? "⏳" : "📷"}</span>
          </div>
        </div>
        <button
          className="pp-btn pp-btn-outline"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "上传中..." : "更换头像"}
        </button>
      </div>

      {/* ── Personal info card ── */}
      <div className="pp-card pp-info-card">
        <div className="pp-info-header">
          <h2 className="pp-card-title">个人信息</h2>
          {!editing ? (
            <button className="pp-btn pp-btn-outline-sm" onClick={handleEdit}>
              编辑资料
            </button>
          ) : (
            <div className="pp-edit-actions">
              <button className="pp-btn pp-btn-cancel" onClick={handleCancel} disabled={saving}>
                取消
              </button>
              <button className="pp-btn pp-btn-save" onClick={handleSave} disabled={saving}>
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          )}
        </div>

        {/* Info rows */}
        <div className="pp-info-grid">
          {/* Username — read only */}
          <div className="pp-info-row">
            <span className="pp-info-label">
              <span className="pp-info-icon">👤</span> 用户名
            </span>
            <span className="pp-info-value">{user?.username || "—"}</span>
          </div>

          {/* Nickname */}
          <div className="pp-info-row">
            <span className="pp-info-label">
              <span className="pp-info-icon">✏️</span> 昵称
            </span>
            {editing ? (
              <input
                className="pp-input"
                value={profile.nickname}
                onChange={(e) => setProfile((p) => ({ ...p, nickname: e.target.value }))}
                placeholder="输入昵称"
                maxLength={30}
              />
            ) : (
              <span className="pp-info-value">{profile.nickname || "未填写"}</span>
            )}
          </div>

          {/* Grade */}
          <div className="pp-info-row">
            <span className="pp-info-label">
              <span className="pp-info-icon">🎓</span> 年级
            </span>
            {editing ? (
              <select
                className="pp-input pp-select"
                value={profile.grade}
                onChange={(e) => setProfile((p) => ({ ...p, grade: e.target.value }))}
              >
                <option value="">未设置</option>
                {GRADE_OPTIONS.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            ) : (
              <span className="pp-info-value">{profile.grade || "未填写"}</span>
            )}
          </div>

          {/* Major */}
          <div className="pp-info-row">
            <span className="pp-info-label">
              <span className="pp-info-icon">📘</span> 专业
            </span>
            {editing ? (
              <input
                className="pp-input"
                value={profile.major}
                onChange={(e) => setProfile((p) => ({ ...p, major: e.target.value }))}
                placeholder="输入专业名称"
                maxLength={50}
              />
            ) : (
              <span className="pp-info-value">{profile.major || "未填写"}</span>
            )}
          </div>
        </div>

        {/* Info banners */}
        <div className="pp-info-banner">
          <span className="pp-banner-icon">💡</span>
          <span>年级和专业将同步用于 AI 问答、学习计划和课程推荐</span>
        </div>
      </div>

      {/* ── Membership card ── */}
      <div className="pp-card pp-membership-card">
        <div className="pp-membership-left">
          <span className="pp-membership-icon">👑</span>
          <div>
            <div className="pp-membership-title">
              {user?.is_member ? "会员用户" : "普通用户"}
            </div>
            <div className="pp-membership-desc">
              {user?.is_member
                ? "您已解锁全部高级功能"
                : "升级会员，解锁更多 AI 问答和高级功能"}
            </div>
          </div>
        </div>
        {!user?.is_member && (
          <button className="pp-btn pp-btn-primary" onClick={() => showToast("充值功能正在开发中")}>
            充值 / 开通会员
          </button>
        )}
      </div>

      {/* ── Account security card ── */}
      <div className="pp-card pp-security-card">
        <h2 className="pp-card-title">账号安全</h2>
        <div className="pp-info-grid">
          {securityItems.map((item) => (
            <div key={item.label} className="pp-info-row">
              <span className="pp-info-label">{item.label}</span>
              <div className="pp-security-right">
                <span className="pp-info-value">{item.value}</span>
                <button
                  className="pp-btn pp-btn-mini"
                  onClick={() => showToast("功能正在开发中")}
                >
                  {item.action}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Danger zone — logout ── */}
      <div className="pp-card pp-danger-card">
        <div className="pp-danger-row">
          <div>
            <div className="pp-danger-title">退出登录</div>
            <div className="pp-danger-desc">退出后需要重新登录才能使用</div>
          </div>
          <button className="pp-btn pp-btn-danger" onClick={onLogout}>
            退出登录
          </button>
        </div>
      </div>
    </div>
  );
}
