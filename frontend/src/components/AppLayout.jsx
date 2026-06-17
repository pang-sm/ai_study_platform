import Figure2Sidebar, { useFigure2SidebarCollapsed } from "./Figure2Sidebar.jsx";
import "./AppLayout.css";

export default function AppLayout({
  activePage,
  onNavigate,
  isAdmin,
  showMembershipAd = true,
  onLogout,
  children,
}) {
  const { collapsed, toggle } = useFigure2SidebarCollapsed();

  return (
    <div className="al-shell">
      <Figure2Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        isAdmin={isAdmin}
        showMembershipAd={showMembershipAd}
        collapsed={collapsed}
        onToggle={toggle}
        onLogout={onLogout}
      />
      <main className="al-main">
        {children}
      </main>
    </div>
  );
}
