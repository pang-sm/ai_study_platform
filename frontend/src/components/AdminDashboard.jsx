import { useEffect, useMemo, useState } from "react";

const API_BASE = "/api";

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
      <polyline points={line} fill="none" stroke="#7c3aed" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      {coords.map((point) => (
        <g key={point.date}>
          <circle cx={point.x} cy={point.y} r="5" fill="#7c3aed" stroke="#fff" strokeWidth="3" />
          <text x={point.x} y={height - 12} textAnchor="middle">{point.date}</text>
        </g>
      ))}
    </svg>
  );
}

export default function AdminDashboard({ user }) {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchDashboard = async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/admin/dashboard?admin_username=${encodeURIComponent(user.username)}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "管理员首页数据加载失败");
      setDashboard(data);
    } catch (err) {
      setError(err.message || "管理员首页数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, [user?.username]);

  const overview = dashboard?.overview || {};
  const statCards = useMemo(() => ([
    { label: "用户总数", value: formatNumber(overview.total_users), sub: "较昨日 ↑ 12.5%", icon: "👥", tone: "purple" },
    { label: "课程总数", value: formatNumber(overview.total_courses), sub: "较昨日 ↑ 8.3%", icon: "📘", tone: "blue" },
    { label: "平均学习时长", value: `${formatNumber(overview.average_learning_hours, 1)} 小时`, sub: "较昨日 ↑ 15.7%", icon: "🕒", tone: "green" },
    { label: "今日活跃用户", value: formatNumber(overview.active_users_today), sub: "较昨日 ↑ 9.4%", icon: "👤", tone: "orange" },
    { label: "订单总数", value: formatNumber(overview.total_orders), sub: "较昨日 ↑ 4.6%", icon: "📋", tone: "violet" },
    { label: "总营收（元）", value: `¥ ${formatNumber(overview.total_revenue)}`, sub: "较昨日 ↑ 11.3%", icon: "¥", tone: "pink" },
  ]), [overview]);

  const menus = ["首页", "系统公告", "用户管理", "订单管理", "会员管理", "数据统计", "系统设置"];

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
          {menus.map((item, index) => (
            <button key={item} className={`admin-dashboard-nav-item${index === 0 ? " active" : ""}`} type="button">
              <span>{["⌂", "📣", "♙", "▣", "♡", "▥", "⚙"][index]}</span>
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="admin-dashboard-main">
        <header className="admin-dashboard-header">
          <div>
            <h1>首页</h1>
            <p>欢迎回来，管理员！今天是 {formatToday()}</p>
          </div>
          <div className="admin-dashboard-profile">
            <span className="admin-dashboard-avatar">👨🏻‍💼</span>
            <strong>管理员</strong>
            <span>⌄</span>
          </div>
        </header>

        {loading ? (
          <div className="admin-dashboard-card admin-dashboard-loading">管理员首页加载中...</div>
        ) : error ? (
          <div className="admin-dashboard-card admin-dashboard-loading">
            <p>{error}</p>
            <button type="button" onClick={fetchDashboard}>重试</button>
          </div>
        ) : (
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
                <div className="admin-dashboard-announcements">
                  {(dashboard?.announcements || []).map((item) => (
                    <div className="admin-dashboard-announcement" key={`${item.title}-${item.date}`}>
                      <span>•</span>
                      <strong>{item.title}</strong>
                      <time>{item.date}</time>
                    </div>
                  ))}
                </div>
                <button className="admin-dashboard-more" type="button">查看更多 〉</button>
              </div>
            </section>

            <section className="admin-dashboard-card admin-dashboard-users-card">
              <h2>最近用户</h2>
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
                    {(dashboard?.recent_users || []).map((item) => (
                      <tr key={`${item.username}-${item.user_id}`}>
                        <td><span className="admin-dashboard-user-avatar">👤</span>{item.username}</td>
                        <td>{item.user_id}</td>
                        <td>{item.register_method}</td>
                        <td>{item.register_time}</td>
                        <td>{item.last_active_time}</td>
                        <td>{formatNumber(item.learning_hours, 1)} 小时</td>
                        <td><button type="button">查看</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button className="admin-dashboard-more admin-dashboard-users-more" type="button">查看更多用户 〉</button>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
