import Sidebar, { useSidebarCollapsed } from "./Sidebar.jsx";
import "./AppLayout.css";

export default function AppLayout({
  activePage,
  onNavigate,
  isAdmin,
  children,
}) {
  const { collapsed, toggle } = useSidebarCollapsed();

  return (
    <div className="al-shell">
      <Sidebar
        activePage={activePage}
        onNavigate={onNavigate}
        isAdmin={isAdmin}
        collapsed={collapsed}
        onToggle={toggle}
      />
      <main className="al-main">
        {children}
      </main>
    </div>
  );
}
