import Sidebar, { useSidebarCollapsed } from "./Sidebar.jsx";
import "./AppLayout.css";

export default function AppLayout({
  activePage,
  onNavigate,
  isAdmin,
  showMembershipAd = true,
  children,
}) {
  const { collapsed, toggle } = useSidebarCollapsed();

  return (
    <div className="al-shell">
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        isAdmin={isAdmin}
        showMembershipAd={showMembershipAd}
        collapsed={collapsed}
        onToggle={toggle}
      />
      <main className="al-main">
        {children}
      </main>
    </div>
  );
}
