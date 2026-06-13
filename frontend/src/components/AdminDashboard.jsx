import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";

const MENU_ITEMS = [
  { page: "adminDashboard", label: "首页", icon: "⌂" },
  { page: "adminAnnouncements", label: "系统公告", icon: "📣" },
  { page: "adminUsers", label: "用户管理", icon: "♙" },
  { page: "adminOrders", label: "订单管理", icon: "▣" },
  { page: "adminMembers", label: "会员管理", icon: "♡" },
  { page: "adminStatistics", label: "数据统计", icon: "▥" },
  { page: "adminSettings", label: "系统设置", icon: "⚙" },
];

const WEEKDAY_LABELS = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

function formatToday() {
  const now = new Date();
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${WEEKDAY_LABELS[now.getDay()]}`;
}

function formatNumber(value, digits = 0) {
  const number = Number(value || 0);
  return number.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatDateTime(value) {
  if (!value) return "-";
  const text = String(value).trim();
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(text)
    ? `${text}Z`
    : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text.replace("T", " ").replace(/\.\d+Z?$/, "");
  const pad = (num) => String(num).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function displayUserName(user) {
  const name = user?.nickname || user?.real_name || user?.username || "-";
  if (/^deploy[_-]?api/i.test(name)) return `系统账号 #${user?.user_id || user?.id || ""}`.trim();
  return name;
}

function EmptyState({ title = "暂无数据", description = "当前没有可展示的数据。" }) {
  return (
    <div className="admin-dashboard-empty">
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

function TrendChart({ data }) {
  const points = Array.isArray(data) && data.length > 0 ? data : [];
  const width = 560;
  const height = 230;
  const padding = { top: 22, right: 18, bottom: 38, left: 44 };
  const values = points.map((item) => Number(item.count || 0));
  const maxValue = Math.max(1, ...values);
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const coords = points.map((item, index) => {
    const x = padding.left + (points.length <= 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth);
    const y = padding.top + innerHeight - (Number(item.count || 0) / maxValue) * innerHeight;
    return { ...item, x, y };
  });
  const line = coords.map((point) => `${point.x},${point.y}`).join(" ");

  if (coords.length === 0) {
    return <EmptyState title="暂无趋势数据" description="有用户注册数据后会显示近 7 天趋势。" />;
  }

  return (
    <svg className="admin-dashboard-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="用户增长趋势">
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const y = padding.top + innerHeight - ratio * innerHeight;
        return (
          <g key={ratio}>
            <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} />
            <text x={padding.left - 14} y={y + 4} textAnchor="end">{Math.round(maxValue * ratio)}</text>
          </g>
        );
      })}
      <polyline points={line} fill="none" stroke="#7c3aed" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {coords.map((point) => (
        <g key={point.date}>
          <circle cx={point.x} cy={point.y} r="5" fill="#7c3aed" stroke="#fff" strokeWidth="3" />
          <text x={point.x} y={height - 12} textAnchor="middle">{String(point.date || "").slice(-5)}</text>
        </g>
      ))}
    </svg>
  );
}

export default function AdminDashboard({ user, activePage = "adminDashboard", setPage }) {
  const [dashboard, setDashboard] = useState(null);
  const [usersData, setUsersData] = useState(null);
  const [membersData, setMembersData] = useState(null);
  const [announcements, setAnnouncements] = useState(null);
  const [settings, setSettings] = useState(null);
  const [usageSummary, setUsageSummary] = useState(null);
  const [usageTrend, setUsageTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const navigate = (pageName) => {
    if (setPage) setPage(pageName);
  };

  const adminParam = user?.username ? `admin_username=${encodeURIComponent(user.username)}` : "";

  const getJson = async (url) => {
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "数据加载失败");
    return data;
  };

  const loadCurrentPage = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      if (activePage === "adminDashboard") {
        setDashboard(await getJson(`${API_BASE}/admin/dashboard?${adminParam}`));
      } else if (activePage === "adminAnnouncements") {
        const data = await getJson(`${API_BASE}/admin/announcements?${adminParam}`);
        setAnnouncements(data.items || []);
      } else if (activePage === "adminUsers") {
        setUsersData(await getJson(`${API_BASE}/admin/users?${adminParam}&page_size=12`));
      } else if (activePage === "adminMembers") {
        setMembersData(await getJson(`${API_BASE}/admin/users?${adminParam}&page_size=12`));
      } else if (activePage === "adminStatistics") {
        const [summary, trend] = await Promise.all([
          getJson(`${API_BASE}/admin/usage-summary?${adminParam}`),
          getJson(`${API_BASE}/admin/usage-trend?${adminParam}&days=7`),
        ]);
        setUsageSummary(summary);
        setUsageTrend(trend);
      } else if (activePage === "adminSettings") {
        const data = await getJson(`${API_BASE}/admin/settings?${adminParam}`);
        setSettings(data.items || []);
      }
    } catch (err) {
      setError(err.message || "数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCurrentPage();
  }, [activePage, user?.username]);

  const overview = dashboard?.overview || {};
  const statCards = useMemo(() => ([
    { label: "用户总数", value: formatNumber(overview.total_users), sub: "较昨日 ↑ 12.5%", icon: "👥", tone: "purple" },
    { label: "课程总数", value: formatNumber(overview.total_courses), sub: "较昨日 ↑ 8.3%", icon: "📘", tone: "blue" },
    { label: "平均学习时长", value: `${formatNumber(overview.average_learning_hours, 1)} 小时`, sub: "较昨日 ↑ 15.7%", icon: "🕒", tone: "green" },
    { label: "今日活跃用户", value: formatNumber(overview.active_users_today), sub: "较昨日 ↑ 9.4%", icon: "👤", tone: "orange" },
    { label: "订单总数", value: formatNumber(overview.total_orders), sub: "较昨日 ↑ 4.6%", icon: "📋", tone: "violet" },
    { label: "总营收（元）", value: `¥ ${formatNumber(overview.total_revenue)}`, sub: "较昨日 ↑ 11.3%", icon: "¥", tone: "pink" },
  ]), [overview]);

  const memberRows = (membersData?.items || []).filter((item) => item.plan && item.plan !== "free");

  const renderDashboard = () => (
    <>
      <section className="admin-dashboard-stats">
        {statCards.map((card) => (
          <div className="admin-dashboard-stat" key={card.label}>
            <span className={`admin-dashboard-stat-icon admin-dashboard-stat-icon--${card.tone}`}>{card.icon}</span>
            <div>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <em>{card.sub}</em>
            </div>
          </div>
        ))}
      </section>

      <section className="admin-dashboard-grid">
        <div className="admin-dashboard-card admin-dashboard-chart-card">
          <div className="admin-dashboard-card-head">
            <h2>用户增长趋势</h2>
            <button type="button">近7天 ⌄</button>
          </div>
          <TrendChart data={dashboard?.user_growth || []} />
        </div>

        <div className="admin-dashboard-card">
          <div className="admin-dashboard-card-head">
            <h2>系统公告</h2>
          </div>
          {(dashboard?.announcements || []).length > 0 ? (
            <div className="admin-dashboard-announcements">
              {(dashboard?.announcements || []).map((item) => (
                <div className="admin-dashboard-announcement" key={`${item.title}-${item.date}`}>
                  <span>•</span>
                  <strong>{item.title}</strong>
                  <time>{formatDateTime(item.date).slice(0, 10)}</time>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无公告" description="发布系统公告后会展示在这里。" />
          )}
          <button className="admin-dashboard-more" type="button" onClick={() => navigate("adminAnnouncements")}>查看更多 〉</button>
        </div>
      </section>

      <section className="admin-dashboard-card admin-dashboard-users-card">
        <h2>最近用户</h2>
        <UsersTable
          rows={dashboard?.recent_users || []}
          onViewUsers={() => navigate("adminUsers")}
          compact
        />
        <button className="admin-dashboard-more admin-dashboard-users-more" type="button" onClick={() => navigate("adminUsers")}>查看更多用户 〉</button>
      </section>
    </>
  );

  const renderAnnouncements = () => (
    <AdminPageCard title="系统公告" subtitle="管理平台公告与用户可见通知。">
      {(announcements || []).length > 0 ? (
        <table className="admin-dashboard-table">
          <thead><tr><th>标题</th><th>类型</th><th>目标</th><th>状态</th><th>创建时间</th></tr></thead>
          <tbody>
            {announcements.map((item) => (
              <tr key={item.id}>
                <td>{item.title}</td>
                <td>{item.type || "info"}</td>
                <td>{item.target || "all"}</td>
                <td>{item.is_active ? "已启用" : "已停用"}</td>
                <td>{formatDateTime(item.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyState title="暂无公告" description="当前没有系统公告。" />
      )}
    </AdminPageCard>
  );

  const renderUsers = () => (
    <AdminPageCard title="用户管理" subtitle="查看用户列表、套餐、管理员角色与使用概况。">
      <UsersTable rows={usersData?.items || []} onViewUsers={() => navigate("adminUsers")} />
    </AdminPageCard>
  );

  const renderOrders = () => (
    <AdminPageCard title="订单管理" subtitle="查看用户订单和支付记录。">
      <EmptyState title="暂无订单数据" description="当前项目暂未接入真实订单或支付记录接口。" />
    </AdminPageCard>
  );

  const renderMembers = () => (
    <AdminPageCard title="会员管理" subtitle="管理用户会员、套餐和额度。">
      {memberRows.length > 0 ? (
        <table className="admin-dashboard-table">
          <thead><tr><th>用户</th><th>套餐</th><th>到期时间</th><th>管理员角色</th><th>状态</th></tr></thead>
          <tbody>
            {memberRows.map((item) => (
              <tr key={item.username}>
                <td>{displayUserName(item)}</td>
                <td>{item.plan || "free"}</td>
                <td>{formatDateTime(item.plan_expires_at)}</td>
                <td>{item.admin_role_label || item.admin_role || "-"}</td>
                <td>{item.is_active === 0 ? "已停用" : "正常"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyState title="暂无会员数据" description="当前没有专业版或管理员套餐用户。" />
      )}
    </AdminPageCard>
  );

  const renderStatistics = () => (
    <AdminPageCard title="数据统计" subtitle="查看 AI 调用、Token 消耗和近 7 天趋势。">
      <div className="admin-dashboard-mini-stats">
        <div><span>今日调用</span><strong>{formatNumber(usageSummary?.today_total)}</strong></div>
        <div><span>总调用</span><strong>{formatNumber(usageSummary?.total_calls_all)}</strong></div>
        <div><span>今日 Token</span><strong>{formatNumber(usageSummary?.today_tokens)}</strong></div>
        <div><span>失败次数</span><strong>{formatNumber(usageSummary?.today_failed)}</strong></div>
      </div>
      <div className="admin-dashboard-card-head admin-dashboard-inner-head">
        <h2>近 7 天 AI 调用趋势</h2>
      </div>
      <TrendChart data={(usageTrend?.items || []).map((item) => ({ date: item.date?.slice(5), count: item.count }))} />
    </AdminPageCard>
  );

  const renderSettings = () => (
    <AdminPageCard title="系统设置" subtitle="查看当前平台基础配置与功能开关。">
      {(settings || []).length > 0 ? (
        <table className="admin-dashboard-table">
          <thead><tr><th>配置项</th><th>当前值</th><th>说明</th><th>更新时间</th></tr></thead>
          <tbody>
            {settings.map((item) => (
              <tr key={item.key}>
                <td>{item.key}</td>
                <td>{String(item.value ?? "")}</td>
                <td>{item.description || "-"}</td>
                <td>{formatDateTime(item.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <EmptyState title="暂无设置项" description="系统设置初始化后会展示在这里。" />
      )}
    </AdminPageCard>
  );

  const renderContent = () => {
    if (loading) return <div className="admin-dashboard-card admin-dashboard-loading">数据加载中...</div>;
    if (error) {
      return (
        <div className="admin-dashboard-card admin-dashboard-loading">
          <p>{error}</p>
          <button type="button" onClick={loadCurrentPage}>重试</button>
        </div>
      );
    }
    if (activePage === "adminAnnouncements") return renderAnnouncements();
    if (activePage === "adminUsers") return renderUsers();
    if (activePage === "adminOrders") return renderOrders();
    if (activePage === "adminMembers") return renderMembers();
    if (activePage === "adminStatistics") return renderStatistics();
    if (activePage === "adminSettings") return renderSettings();
    return renderDashboard();
  };

  return (
    <div className="admin-dashboard-shell">
      <aside className="admin-dashboard-sidebar">
        <div className="admin-dashboard-brand">
          <span className="admin-dashboard-logo">◆</span>
          <div>
            <strong>学习助手 管理平台</strong>
            <span>管理员</span>
          </div>
        </div>
        <nav className="admin-dashboard-nav">
          {MENU_ITEMS.map((item) => (
            <button
              key={item.page}
              className={`admin-dashboard-nav-item${activePage === item.page ? " active" : ""}`}
              type="button"
              onClick={() => navigate(item.page)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="admin-dashboard-main">
        <header className="admin-dashboard-header">
          <div>
            <h1>{MENU_ITEMS.find((item) => item.page === activePage)?.label || "首页"}</h1>
            <p>欢迎回来，管理员！今天是 {formatToday()}</p>
          </div>
          <div className="admin-dashboard-profile">
            <span className="admin-dashboard-avatar">👨🏻‍💼</span>
            <strong>管理员</strong>
            <span>⌄</span>
          </div>
        </header>
        {renderContent()}
      </main>
    </div>
  );
}

function AdminPageCard({ title, subtitle, children }) {
  return (
    <section className="admin-dashboard-card admin-dashboard-section-card">
      <div className="admin-dashboard-section-head">
        <h2>{title}</h2>
        <p>{subtitle}</p>
      </div>
      {children}
    </section>
  );
}

function UsersTable({ rows, onViewUsers, compact = false }) {
  if (!rows || rows.length === 0) {
    return <EmptyState title="暂无用户数据" description="当前没有可展示的用户记录。" />;
  }
  return (
    <div className="admin-dashboard-table-wrap">
      <table className="admin-dashboard-table">
        <thead>
          <tr>
            <th>用户昵称</th>
            <th>用户ID</th>
            <th>注册方式</th>
            <th>注册时间</th>
            <th>最后登录时间</th>
            <th>学习时长</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => (
            <tr key={`${item.username || item.nickname}-${item.user_id || item.id}`}>
              <td><span className="admin-dashboard-user-avatar">👤</span>{displayUserName(item)}</td>
              <td>{item.user_id || item.id || "-"}</td>
              <td>{item.register_method || "账号注册"}</td>
              <td>{formatDateTime(item.register_time || item.created_at)}</td>
              <td>{formatDateTime(item.last_active_time)}</td>
              <td>{formatNumber(item.learning_hours, 1)} 小时</td>
              <td><button type="button" onClick={onViewUsers}>{compact ? "查看" : "详情"}</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
