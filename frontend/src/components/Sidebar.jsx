import { useEffect, useState } from "react";
import "./Sidebar.css";
import { APP_PAGES, SIDEBAR_NAV_GROUPS } from "../config/navigation.js";

const SIDEBAR_COLLAPSED_KEY = "ai_study_sidebar_collapsed";

export default function Sidebar({
  activePage,
  onNavigate,
  isAdmin,
  showMembershipAd = true,
  collapsed,
  onToggle,
  onLogout,
}) {
  function isActive(id) {
    if (activePage === id) return true;
    return false;
  }

  function renderNavItem(item) {
    const active = isActive(item.key);
    return (
      <button
        key={item.key}
        className={`sb-nav-item${active ? " active" : ""}`}
        onClick={() => onNavigate(item.key)}
        title={collapsed ? item.label : undefined}
      >
        <span className="sb-nav-icon">{item.icon}</span>
        {!collapsed && <span className="sb-nav-label">{item.label}</span>}
      </button>
    );
  }

  function renderNavGroup(group) {
    // Filter out admin-only items if not admin
    const items = group.items.filter((item) => {
      if (item.key === "adminCenter" && !isAdmin) return false;
      return true;
    });

    if (items.length === 0) return null;

    return (
      <div key={group.id} className="sb-nav-group">
        {!collapsed && <div className="sb-section-label">{group.title}</div>}
        {items.map(renderNavItem)}
      </div>
    );
  }

  return (
    <aside className={`sb-sidebar${collapsed ? " sb-collapsed" : ""}`}>
      {/* Logo area */}
      <div className="sb-logo-area">
        <div className="sb-logo">
          <div className="sb-logo-icon">🧠</div>
          {!collapsed && <span className="sb-logo-text">AI 学习助手</span>}
        </div>
        <button
          className="sb-toggle-btn"
          onClick={onToggle}
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {collapsed ? "»" : "«"}
        </button>
      </div>

      {/* Navigation groups */}
      <nav className="sb-nav">
        {SIDEBAR_NAV_GROUPS.map(renderNavGroup)}

        {/* Admin center — special group for admin only */}
        {isAdmin && (
          <div className="sb-nav-group">
            {!collapsed && <div className="sb-section-label">管理</div>}
            <button
              className={`sb-nav-item${activePage === "adminCenter" ? " active" : ""}`}
              onClick={() => onNavigate("adminCenter")}
              title={collapsed ? "管理后台" : undefined}
            >
              <span className="sb-nav-icon">🛡️</span>
              {!collapsed && <span className="sb-nav-label">管理后台</span>}
            </button>
          </div>
        )}

        {/* Logout button */}
        {onLogout && (
          <div className="sb-nav-group sb-nav-group--logout">
            {!collapsed && <div className="sb-section-label">系统</div>}
            <button
              className="sb-nav-item sb-nav-item--logout"
              onClick={onLogout}
              title={collapsed ? "退出登录" : undefined}
            >
              <span className="sb-nav-icon">🚪</span>
              {!collapsed && <span className="sb-nav-label">退出登录</span>}
            </button>
          </div>
        )}
      </nav>

      {showMembershipAd && (
        <div className="sb-footer">
          {collapsed ? (
            <button
              className="sb-premium-btn-collapsed"
              onClick={() => onNavigate("membership")}
              title="开通会员"
            >
              <span className="sb-premium-crown">👑</span>
            </button>
          ) : (
            <div className="sb-premium-card">
              <div className="sb-premium-top">
                <span className="sb-premium-crown">👑</span>
                <span className="sb-premium-title">开通会员</span>
              </div>
              <p className="sb-premium-desc">解锁更多高级学习功能</p>
              <button
                className="sb-premium-btn"
                onClick={() => onNavigate("membership")}
              >
                立即开通
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
    } catch { /* ignore */ }
  }, [collapsed]);

  const toggle = () => setCollapsed((prev) => !prev);

  return { collapsed, toggle };
}
