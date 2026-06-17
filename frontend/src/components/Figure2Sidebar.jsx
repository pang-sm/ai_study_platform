import { useEffect, useState } from "react";
import { APP_PAGES, SIDEBAR_NAV_GROUPS } from "../config/navigation.js";
import "./Figure2Sidebar.css";

const SIDEBAR_COLLAPSED_KEY = "ai_study_sidebar_collapsed";

const SYSTEM_GROUP = {
  id: "system",
  title: "系统",
  items: [],
};

export default function Figure2Sidebar({
  activePage,
  onNavigate,
  isAdmin,
  showMembershipAd = true,
  collapsed,
  onToggle,
  onLogout,
}) {
  const isActive = (key) => activePage === key;

  const renderNavItem = (item) => (
    <button
      key={item.key}
      type="button"
      className={`fig2-nav-item${isActive(item.key) ? " active" : ""}`}
      onClick={() => onNavigate(item.key)}
      title={collapsed ? item.label : undefined}
    >
      <span className="fig2-nav-icon">{item.icon}</span>
      {!collapsed && <span className="fig2-nav-label">{item.label}</span>}
    </button>
  );

  const renderGroup = (group) => {
    const items = group.items.filter((item) => item.key !== "adminCenter" || isAdmin);
    if (items.length === 0) return null;

    return (
      <div key={group.id} className="fig2-nav-group">
        {!collapsed && <div className="fig2-section-label">{group.title}</div>}
        {items.map(renderNavItem)}
      </div>
    );
  };

  return (
    <aside className={`fig2-sidebar${collapsed ? " fig2-collapsed" : ""}`}>
      <div className="fig2-brand">
        <button
          type="button"
          className="fig2-brand-mark"
          onClick={() => onNavigate(APP_PAGES.home.key)}
          title="返回首页"
        >
          AI
        </button>
        {!collapsed && (
          <div className="fig2-brand-copy">
            <strong>11408 学习系统</strong>
            <span>AI Study Platform</span>
          </div>
        )}
        <button
          type="button"
          className="fig2-toggle"
          onClick={onToggle}
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {collapsed ? "›" : "‹"}
        </button>
      </div>

      <nav className="fig2-nav" aria-label="主导航">
        {SIDEBAR_NAV_GROUPS.map(renderGroup)}

        {isAdmin && (
          <div className="fig2-nav-group">
            {!collapsed && <div className="fig2-section-label">管理</div>}
            <button
              type="button"
              className={`fig2-nav-item${activePage === "adminCenter" ? " active" : ""}`}
              onClick={() => onNavigate("adminCenter")}
              title={collapsed ? "管理后台" : undefined}
            >
              <span className="fig2-nav-icon">管</span>
              {!collapsed && <span className="fig2-nav-label">管理后台</span>}
            </button>
          </div>
        )}

        {onLogout && (
          <div className="fig2-nav-group fig2-nav-group--system">
            {!collapsed && <div className="fig2-section-label">{SYSTEM_GROUP.title}</div>}
            <button
              type="button"
              className="fig2-nav-item fig2-nav-item--logout"
              onClick={onLogout}
              title={collapsed ? "退出登录" : undefined}
            >
              <span className="fig2-nav-icon">退</span>
              {!collapsed && <span className="fig2-nav-label">退出登录</span>}
            </button>
          </div>
        )}
      </nav>

      {showMembershipAd && (
        <div className="fig2-footer">
          {collapsed ? (
            <button
              type="button"
              className="fig2-premium-mini"
              onClick={() => onNavigate(APP_PAGES.membership.key)}
              title="开通会员"
            >
              会员
            </button>
          ) : (
            <div className="fig2-premium-card">
              <strong>开通会员</strong>
              <span>解锁更多高级学习功能</span>
              <button type="button" onClick={() => onNavigate(APP_PAGES.membership.key)}>
                立即开通
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

export function useFigure2SidebarCollapsed() {
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
    } catch {
      // Ignore storage failures.
    }
  }, [collapsed]);

  return {
    collapsed,
    toggle: () => setCollapsed((prev) => !prev),
  };
}
