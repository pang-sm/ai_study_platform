import { useEffect, useState } from "react";
import "./Sidebar.css";

const SIDEBAR_COLLAPSED_KEY = "ai_study_sidebar_collapsed";

export default function Sidebar({
  activePage,
  onNavigate,
  isAdmin,
  collapsed,
  onToggle,
}) {
  const mainNav = [
    { id: "home", icon: "🏠", label: "首页" },
    { id: "chat", icon: "💬", label: "AI 问答" },
  ];

  const studyNav = [
    { id: "dashboard", icon: "📋", label: "课程工作台" },
    { id: "practiceCenter", icon: "📝", label: "练习中心" },
    { id: "codeStudio", icon: "</>", label: "编程助手" },
    { id: "taskCenter", icon: "✅", label: "学习任务" },
  ];

  const resourceNav = [
    { id: "workspaceMaterials", icon: "📚", label: "资料库" },
    { id: "learningReportCenter", icon: "📄", label: "学习报告" },
    ...(isAdmin ? [{ id: "adminCenter", icon: "🛡️", label: "管理后台" }] : []),
  ];

  function isActive(id) {
    if (activePage === id) return true;
    if (id === "workspaceMaterials" && activePage === "materials") return true;
    return false;
  }

  function renderNavItem(item) {
    const active = isActive(item.id);
    return (
      <button
        key={item.id}
        className={`sb-nav-item${active ? " active" : ""}`}
        onClick={() => onNavigate(item.id)}
        title={collapsed ? item.label : undefined}
      >
        <span className="sb-nav-icon">{item.icon}</span>
        {!collapsed && <span className="sb-nav-label">{item.label}</span>}
      </button>
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

      {/* Navigation */}
      <nav className="sb-nav">
        {mainNav.map(renderNavItem)}

        {!collapsed && <div className="sb-section-label">学习</div>}
        {studyNav.map(renderNavItem)}

        {!collapsed && <div className="sb-section-label">资源</div>}
        {resourceNav.map(renderNavItem)}
      </nav>

      {/* Premium card / membership entry */}
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
