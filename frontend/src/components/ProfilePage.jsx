import { useState, useRef } from "react";
import "./ProfilePage.css";

function getLocalAvatar(username) {
  try {
    return localStorage.getItem(`avatar:${username}`);
  } catch {
    return null;
  }
}

function setLocalAvatar(username, dataUrl) {
  try {
    localStorage.setItem(`avatar:${username}`, dataUrl);
  } catch {
    // storage full or unavailable
  }
}

export default function ProfilePage({ user, apiBase, onLogout, setPage }) {
  const [localAvatar, setLocalAvatar] = useState(() => getLocalAvatar(user?.username || ""));
  const [toast, setToast] = useState("");
  const fileInputRef = useRef(null);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 2500);
  };

  const hasBackendAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");
  const avatarSrc = localAvatar
    || (hasBackendAvatar ? `${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}` : null);
  const displayName = user?.nickname || user?.username || "同学";
  const initial = displayName.charAt(0);

  const handleFileChange = (e) => {
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

    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      setLocalAvatar(dataUrl);
      setLocalAvatar(user.username, dataUrl);
      showToast("头像已更新");
    };
    reader.onerror = () => showToast("图片读取失败");
    reader.readAsDataURL(file);
  };

  /* ── info rows ── */

  const infoItems = [
    { label: "用户名", value: user?.username || "—" },
    { label: "昵称", value: user?.nickname || "—" },
    { label: "年级", value: user?.grade || "—" },
    { label: "专业", value: user?.major || "—" },
    { label: "会员状态", value: user?.is_member ? "会员用户" : "普通用户", highlight: user?.is_member },
  ];

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

      {/* Top profile card */}
      <div className="pp-card pp-profile-card">
        <div className="pp-avatar-section">
          <div className="pp-avatar-wrap" onClick={() => fileInputRef.current?.click()} title="点击更换头像">
            {avatarSrc ? (
              <img className="pp-avatar-img" src={avatarSrc} alt="头像" />
            ) : (
              <div className="pp-avatar-letter">{initial}</div>
            )}
            <div className="pp-avatar-overlay">
              <span>📷</span>
            </div>
          </div>
          <div className="pp-avatar-info">
            <div className="pp-display-name">{displayName}</div>
            <div className="pp-display-role">
              {user?.grade ? `${user.grade}` : "学习者"}
              {user?.major ? ` · ${user.major}` : ""}
            </div>
          </div>
        </div>
        <button className="pp-btn pp-btn-outline" onClick={() => fileInputRef.current?.click()}>
          更换头像
        </button>
      </div>

      {/* Personal info card */}
      <div className="pp-card pp-info-card">
        <h2 className="pp-card-title">个人信息</h2>
        <div className="pp-info-grid">
          {infoItems.map((item) => (
            <div key={item.label} className="pp-info-row">
              <span className="pp-info-label">{item.label}</span>
              <span className={`pp-info-value${item.highlight ? " pp-member-badge" : ""}`}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Membership card */}
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
                : "升级会员，解锁无限 AI 问答和更多高级功能"}
            </div>
          </div>
        </div>
        {!user?.is_member && (
          <button className="pp-btn pp-btn-primary" onClick={() => showToast("充值功能正在开发中")}>
            充值 / 开通会员
          </button>
        )}
      </div>

      {/* Account security card */}
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

      {/* Danger zone — logout */}
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
