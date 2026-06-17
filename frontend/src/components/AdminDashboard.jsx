import { useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "/api";

const MENU_GROUPS = [
  {
    title: "基础管理",
    items: [
      { page: "adminDashboard", label: "首页", icon: "⌂" },
      { page: "adminAnnouncements", label: "系统公告", icon: "!" },
      { page: "adminUsers", label: "用户管理", icon: "U" },
    ],
  },
  {
    title: "运营管理",
    items: [
      { page: "adminMembers", label: "会员管理", icon: "V" },
      { page: "adminOrders", label: "订单管理", icon: "O" },
      { page: "adminQuota", label: "额度管理", icon: "L" },
    ],
  },
  {
    title: "数据与系统",
    items: [
      { page: "adminStatistics", label: "数据统计", icon: "S" },
      { page: "adminUsage", label: "AI 用量统计", icon: "A" },
      { page: "adminSettings", label: "系统设置", icon: "G" },
      { page: "adminLogs", label: "操作日志", icon: "R" },
    ],
  },
];

const MENU_ITEMS = MENU_GROUPS.flatMap((group) => group.items);
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

function TrendChart({ data, emptyTitle = "暂无趋势数据", emptyDescription = "有数据后会展示趋势。" }) {
  const points = Array.isArray(data) && data.length > 0 ? data : [];
  const width = 560;
  const height = 220;
  const padding = { top: 20, right: 18, bottom: 36, left: 44 };
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
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <svg className="admin-dashboard-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="趋势图">
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
        <g key={`${point.date}-${point.x}`}>
          <circle cx={point.x} cy={point.y} r="5" fill="#7c3aed" stroke="#fff" strokeWidth="3" />
          <text x={point.x} y={height - 12} textAnchor="middle">{String(point.date || "").slice(-5)}</text>
        </g>
      ))}
    </svg>
  );
}

export default function AdminDashboard({ user, activePage = "adminDashboard", setPage, onLogout, onUserUpdate }) {
  const [dashboard, setDashboard] = useState(null);
  const [usersData, setUsersData] = useState(null);
  const [membersData, setMembersData] = useState(null);
  const [announcements, setAnnouncements] = useState(null);
  const [settings, setSettings] = useState(null);
  const [usageSummary, setUsageSummary] = useState(null);
  const [usageTrend, setUsageTrend] = useState(null);
  const [quota, setQuota] = useState(null);
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [userKeyword, setUserKeyword] = useState("");
  const [userStatus, setUserStatus] = useState("all");
  const [actionLoading, setActionLoading] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionSuccess, setActionSuccess] = useState("");
  const [editingMemberUser, setEditingMemberUser] = useState(null);
  const [membershipForm, setMembershipForm] = useState({});
  const [showAnnouncementForm, setShowAnnouncementForm] = useState(false);
  const [announcementFormError, setAnnouncementFormError] = useState("");
  const [editingAnnouncement, setEditingAnnouncement] = useState(null);
  const [announcementForm, setAnnouncementForm] = useState({ title: "", content: "", status: "published" });
  const [profileForm, setProfileForm] = useState({ nickname: user?.nickname || "", avatar: user?.avatar || "" });
  const [passwordForm, setPasswordForm] = useState({ old_password: "", new_password: "", confirm_password: "" });
  const [emailForm, setEmailForm] = useState({ email: user?.email || "", code: "" });
  const [showOldPwd, setShowOldPwd] = useState(false);
  const [showNewPwd, setShowNewPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [userAvatarUrl, setUserAvatarUrl] = useState(user?.avatar_url || null);
  const adminRoleLabel = user?.admin_role === "super_admin" ? "超级管理员" : user?.admin_role === "operator" ? "运营管理员" : "管理员";
  const adminRoleDesc = user?.admin_role === "super_admin" ? "负责平台整体运营与管理" : user?.admin_role === "operator" ? "负责日常运营与用户服务" : "负责平台管理与维护";

  const navigate = (pageName) => {
    if (setPage) setPage(pageName);
  };

  const adminParam = user?.username ? `admin_username=${encodeURIComponent(user.username)}` : "";

  const getJson = async (url, options) => {
    const res = await fetch(url, options);
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
        const params = new URLSearchParams({ admin_username: user.username, page_size: "16" });
        if (userKeyword.trim()) params.set("keyword", userKeyword.trim());
        if (userStatus !== "all") params.set("status", userStatus);
        setUsersData(await getJson(`${API_BASE}/admin/users?${params.toString()}`));
      } else if (activePage === "adminMembers") {
        setMembersData(await getJson(`${API_BASE}/admin/users?${adminParam}&page_size=16`));
      } else if (activePage === "adminQuota") {
        setQuota(await getJson(`${API_BASE}/admin/quota?${adminParam}&page_size=16`));
      } else if (activePage === "adminStatistics" || activePage === "adminUsage") {
        const [summary, trend] = await Promise.all([
          getJson(`${API_BASE}/admin/usage-summary?${adminParam}`),
          getJson(`${API_BASE}/admin/usage-trend?${adminParam}&days=7`),
        ]);
        setUsageSummary(summary);
        setUsageTrend(trend);
      } else if (activePage === "adminSettings") {
        const data = await getJson(`${API_BASE}/admin/settings?${adminParam}`);
        setSettings(data.items || []);
      } else if (activePage === "adminLogs") {
        setLogs(await getJson(`${API_BASE}/admin/logs?${adminParam}&page_size=16`));
      }
    } catch (err) {
      setError(err.message || "数据加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setActionError("");
    setActionSuccess("");
    setAnnouncementFormError("");
    loadCurrentPage();
  }, [activePage, user?.username, userStatus]);

  useEffect(() => {
    setProfileForm({ nickname: user?.nickname || "", avatar: user?.avatar || "" });
    setEmailForm((prev) => ({ ...prev, email: user?.email || "" }));
  }, [user?.nickname, user?.avatar, user?.email]);

  const overview = dashboard?.overview || {};
  const statCards = useMemo(() => ([
    { label: "用户总数", value: formatNumber(overview.total_users), sub: "较昨日 ↑ 12.5%", icon: "U", tone: "purple" },
    { label: "课程总数", value: formatNumber(overview.total_courses), sub: "较昨日 ↑ 8.3%", icon: "C", tone: "blue" },
    { label: "平均学习时长", value: `${formatNumber(overview.average_learning_hours, 1)} 小时`, sub: "较昨日 ↑ 15.7%", icon: "H", tone: "green" },
    { label: "今日活跃用户", value: formatNumber(overview.active_users_today), sub: "较昨日 ↑ 9.4%", icon: "A", tone: "orange" },
    { label: "订单总数", value: formatNumber(overview.total_orders), sub: "较昨日 ↑ 4.6%", icon: "O", tone: "violet" },
    { label: "总营收（元）", value: `¥ ${formatNumber(overview.total_revenue)}`, sub: "较昨日 ↑ 11.3%", icon: "¥", tone: "pink" },
  ]), [overview]);

  const memberRows = (membersData?.items || []).filter((item) => item.plan && item.plan !== "free");
  const activeLabel = activePage === "adminProfile" ? "个人资料" : (MENU_ITEMS.find((item) => item.page === activePage)?.label || "首页");

  const openAnnouncementForm = (item = null) => {
    setActionError("");
    setAnnouncementFormError("");
    setEditingAnnouncement(item);
    setAnnouncementForm({
      title: item?.title || "",
      content: item?.content || "",
      status: item?.status || (item?.is_active ? "published" : "draft"),
    });
    setShowAnnouncementForm(true);
  };

  const closeAnnouncementForm = () => {
    setShowAnnouncementForm(false);
    setAnnouncementFormError("");
    setEditingAnnouncement(null);
    setAnnouncementForm({ title: "", content: "", status: "published" });
  };

  const announcementStatusLabel = (item) => {
    if (item?.status === "withdrawn") return "已撤回";
    if (item?.status === "draft" || !item?.is_active) return "草稿";
    return "已发布";
  };

  const submitAnnouncement = async () => {
    setAnnouncementFormError("");
    const title = announcementForm.title.trim();
    const content = announcementForm.content.trim();
    if (!title || !content) {
      setAnnouncementFormError("请填写公告标题和内容");
      return;
    }
    setActionLoading("announcement");
    try {
      const isEditing = Boolean(editingAnnouncement?.id);
      await getJson(isEditing ? `${API_BASE}/admin/announcements/${editingAnnouncement.id}` : `${API_BASE}/admin/announcements`, {
        method: isEditing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          admin_username: user.username,
          title,
          content,
          status: announcementForm.status,
        }),
      });
      closeAnnouncementForm();
      setActionSuccess(isEditing ? "公告已修改" : "公告已发布");
      await loadCurrentPage();
    } catch (err) {
      setAnnouncementFormError(err.message || "公告保存失败");
    } finally {
      setActionLoading("");
    }
  };

  const withdrawAnnouncement = async (item) => {
    if (!window.confirm("确认撤回该公告吗？撤回后用户将不再看到该公告。")) return;
    setActionError("");
    setActionSuccess("");
    setActionLoading(`withdraw-${item.id}`);
    try {
      await getJson(`${API_BASE}/admin/announcements/${item.id}/withdraw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username }),
      });
      setActionSuccess("公告已撤回");
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "公告撤回失败");
    } finally {
      setActionLoading("");
    }
  };

  const saveProfile = async () => {
    setActionError("");
    setActionSuccess("");
    setActionLoading("profile");
    try {
      await getJson(`${API_BASE}/me/profile?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nickname: profileForm.nickname,
          grade: user?.grade || "",
          major: user?.major || "",
        }),
      });
      setActionSuccess("个人资料已保存");
    } catch (err) {
      setActionError(err.message || "个人资料保存失败");
    } finally {
      setActionLoading("");
    }
  };

  const changePassword = async () => {
    setActionError("");
    setActionSuccess("");
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setActionError("新密码和确认密码不一致");
      return;
    }
    setActionLoading("password");
    try {
      await getJson(`${API_BASE}/me/password?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(passwordForm),
      });
      setPasswordForm({ old_password: "", new_password: "", confirm_password: "" });
      setActionSuccess("密码已修改");
    } catch (err) {
      setActionError(err.message || "密码修改失败");
    } finally {
      setActionLoading("");
    }
  };

  const sendEmailCode = async () => {
    setActionError("");
    setActionSuccess("");
    const email = emailForm.email.trim();
    if (!email) {
      setActionError("请输入新邮箱");
      return;
    }
    setActionLoading("email-code");
    try {
      await getJson(`${API_BASE}/me/email/send-code?username=${encodeURIComponent(user.username)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      setActionSuccess("验证码已发送");
    } catch (err) {
      setActionError(err.message || "邮箱验证码发送失败");
    } finally {
      setActionLoading("");
    }
  };

  const bindEmail = async () => {
    setActionError("");
    setActionSuccess("");
    setActionLoading("email-bind");
    try {
      await getJson(`${API_BASE}/me/email/verify?username=${encodeURIComponent(user.username)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailForm.email.trim(), code: emailForm.code.trim() }),
      });
      setEmailForm((prev) => ({ ...prev, code: "" }));
      setActionSuccess("邮箱已绑定");
    } catch (err) {
      setActionError(err.message || "邮箱绑定失败");
    } finally {
      setActionLoading("");
    }
  };

  const banUser = async (item) => {
    const reason = window.prompt(`请输入封禁 ${displayUserName(item)} 的原因：`, item.banned_reason || "");
    if (reason === null) return;
    setActionError("");
    setActionLoading(`ban-${item.user_id}`);
    try {
      await getJson(`${API_BASE}/admin/users/${item.user_id}/ban`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username, reason }),
      });
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "封号失败");
    } finally {
      setActionLoading("");
    }
  };

  const unbanUser = async (item) => {
    if (!window.confirm(`确认解封 ${displayUserName(item)} 吗？`)) return;
    setActionError("");
    setActionLoading(`unban-${item.user_id}`);
    try {
      await getJson(`${API_BASE}/admin/users/${item.user_id}/unban`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username }),
      });
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "解封失败");
    } finally {
      setActionLoading("");
    }
  };

  const deleteUser = async (item) => {
    const message = `删除后该用户将无法登录，相关学习数据保留用于统计。\n\n确认删除 ${displayUserName(item)} 吗？`;
    if (!window.confirm(message)) return;
    setActionError("");
    setActionLoading(`delete-${item.user_id}`);
    try {
      await getJson(`${API_BASE}/admin/users/${item.user_id}?admin_username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
      });
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "删除用户失败");
    } finally {
      setActionLoading("");
    }
  };

  const openMembershipEditor = (item) => {
    const m = item.memberships || {};
    setMembershipForm({
      exam_11408: { is_enabled: m.exam_11408?.is_enabled ?? true, plan: m.exam_11408?.plan || "free" },
      course: { is_enabled: m.course?.is_enabled ?? false, plan: m.course?.plan || "free" },
      programming: { is_enabled: m.programming?.is_enabled ?? false, plan: m.programming?.plan || "free" },
    });
    setEditingMemberUser(item);
  };

  const saveMemberships = async () => {
    if (!editingMemberUser) return;
    setActionError("");
    setActionLoading("membership");
    try {
      await getJson(`${API_BASE}/admin/users/${editingMemberUser.user_id || editingMemberUser.id}/memberships`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username, memberships: membershipForm }),
      });
      setEditingMemberUser(null);
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "修改会员失败");
    } finally {
      setActionLoading("");
    }
  };

  const SERVICE_LABELS = {
    exam_11408: { name: "11408 考研", plans: { free: "普通用户", monthly: "月度冲刺包", quarterly: "季度强化包", full: "全程备考包" } },
    course: { name: "课程学习", plans: { free: "普通用户", monthly: "月度学习包", quarterly: "季度学习包", full: "全程学习包" } },
    programming: { name: "编程能力提升", plans: { free: "普通用户", monthly: "月度练习包", quarterly: "季度练习包", full: "年度提升包" } },
  };

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
            <span className="admin-dashboard-filter">近7天</span>
          </div>
          <TrendChart data={dashboard?.user_growth || []} emptyDescription="有用户注册数据后会展示近 7 天趋势。" />
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
            <EmptyState title="暂无公告" description="暂无公告，发布系统公告后会展示在这里。" />
          )}
        </div>
      </section>

      <section className="admin-dashboard-card admin-dashboard-users-card">
        <h2>最近用户</h2>
        <UsersTable rows={(dashboard?.recent_users || []).slice(0, 5)} hideActions />
      </section>
    </>
  );

  const renderAnnouncements = () => (
    <AdminPageCard
      title="系统公告"
      subtitle="管理平台公告与用户可见通知。"
      action={<button className="admin-dashboard-primary-action" type="button" onClick={() => openAnnouncementForm()}>发布公告</button>}
    >
      {actionError && <div className="admin-dashboard-error">{actionError}</div>}
      {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
      {(announcements || []).length > 0 ? (
        <DataTable
          columns={["标题", "内容摘要", "发布时间", "状态", "操作"]}
          rows={announcements.map((item) => [
            item.title,
            (item.content || "").slice(0, 48) || "-",
            formatDateTime(item.created_at),
            <StatusBadge tone={item.status === "withdrawn" ? "danger" : (item.is_active ? "ok" : "muted")}>{announcementStatusLabel(item)}</StatusBadge>,
            <div className="admin-dashboard-actions">
              <button type="button" onClick={() => openAnnouncementForm(item)}>编辑</button>
              <button
                type="button"
                className="warning"
                disabled={actionLoading === `withdraw-${item.id}` || item.status === "withdrawn"}
                onClick={() => withdrawAnnouncement(item)}
              >
                撤回
              </button>
            </div>,
          ])}
        />
      ) : (
        <EmptyState title="暂无公告" description="当前没有系统公告。" />
      )}
      {showAnnouncementForm && (
        <div className="admin-dashboard-modal-backdrop" role="presentation">
          <div className="admin-dashboard-modal" role="dialog" aria-modal="true" aria-labelledby="announcement-title">
            <div className="admin-dashboard-modal-head">
              <h3 id="announcement-title">{editingAnnouncement ? "编辑公告" : "发布公告"}</h3>
              <button type="button" onClick={closeAnnouncementForm}>×</button>
            </div>
            {announcementFormError && <div className="admin-dashboard-error admin-dashboard-modal-error">{announcementFormError}</div>}
            <label>
              公告标题
              <input value={announcementForm.title} onChange={(e) => setAnnouncementForm((prev) => ({ ...prev, title: e.target.value }))} />
            </label>
            <label>
              公告内容
              <textarea rows={6} value={announcementForm.content} onChange={(e) => setAnnouncementForm((prev) => ({ ...prev, content: e.target.value }))} />
            </label>
            <label>
              公告状态
              <select value={announcementForm.status} onChange={(e) => setAnnouncementForm((prev) => ({ ...prev, status: e.target.value }))}>
                <option value="published">发布</option>
                <option value="draft">草稿</option>
                {editingAnnouncement?.status === "withdrawn" && <option value="withdrawn">已撤回</option>}
              </select>
            </label>
            <div className="admin-dashboard-modal-actions">
              <button type="button" onClick={closeAnnouncementForm}>取消</button>
              <button type="button" className="admin-dashboard-primary-action" disabled={actionLoading === "announcement"} onClick={submitAnnouncement}>
                {actionLoading === "announcement" ? "保存中..." : (editingAnnouncement ? "保存修改" : "发布公告")}
              </button>
            </div>
          </div>
        </div>
      )}
    </AdminPageCard>
  );

  const renderUsers = () => (
    <AdminPageCard title="用户管理" subtitle="管理用户账号、状态和权限">
      <div className="admin-dashboard-toolbar">
        <input
          value={userKeyword}
          placeholder="按用户名 / 昵称 / 邮箱搜索"
          onChange={(e) => setUserKeyword(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") loadCurrentPage(); }}
        />
        <select value={userStatus} onChange={(e) => setUserStatus(e.target.value)}>
          <option value="all">全部</option>
          <option value="normal">正常</option>
          <option value="banned">已封禁</option>
        </select>
        <button type="button" onClick={loadCurrentPage}>刷新</button>
      </div>
      {actionError && <div className="admin-dashboard-error">{actionError}</div>}
      <UsersTable rows={usersData?.items || []} onBan={banUser} onUnban={unbanUser} onDelete={deleteUser} onEditMembership={openMembershipEditor} actionLoading={actionLoading} />
      {editingMemberUser && (
        <MembershipEditModal
          user={editingMemberUser}
          form={membershipForm}
          onChange={setMembershipForm}
          onSave={saveMemberships}
          onClose={() => setEditingMemberUser(null)}
          loading={actionLoading === "membership"}
        />
      )}
    </AdminPageCard>
  );

  const renderOrders = () => (
    <AdminPageCard title="订单管理" subtitle="查看用户订单和支付记录。">
      <EmptyState title="暂无订单数据" description="当前项目暂未接入真实订单或支付记录接口。" />
    </AdminPageCard>
  );

  const renderMembers = () => (
    <AdminPageCard title="会员管理" subtitle="管理用户会员、套餐和有效期。">
      {memberRows.length > 0 ? (
        <DataTable
          columns={["用户", "套餐", "到期时间", "管理员角色", "状态"]}
          rows={memberRows.map((item) => [
            displayUserName(item),
            item.plan || "free",
            formatDateTime(item.plan_expires_at),
            item.admin_role_label || item.admin_role || "-",
            item.is_active === 0 ? "已停用" : "正常",
          ])}
        />
      ) : (
        <EmptyState title="暂无会员数据" description="当前没有专业版或管理员套餐用户。" />
      )}
    </AdminPageCard>
  );

  const renderQuota = () => (
    <AdminPageCard title="额度管理" subtitle="查看用户套餐、AI 调用额度和累计使用情况。">
      {(quota?.items || []).length > 0 ? (
        <DataTable
          columns={["用户", "套餐", "日额度", "月额度", "累计调用", "到期时间"]}
          rows={quota.items.map((item) => [
            displayUserName(item),
            item.plan || "free",
            item.daily_ai_limit < 0 ? "不限" : formatNumber(item.daily_ai_limit),
            item.monthly_ai_limit < 0 ? "不限" : formatNumber(item.monthly_ai_limit),
            formatNumber(item.total_ai_calls),
            formatDateTime(item.plan_expires_at),
          ])}
        />
      ) : (
        <EmptyState title="暂无额度数据" description="用户数据初始化后会展示额度概况。" />
      )}
    </AdminPageCard>
  );

  const renderStatistics = () => (
    <AdminPageCard title="数据统计" subtitle="查看平台核心数据与近 7 天 AI 调用趋势。">
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

  const renderUsage = () => {
    const featureStats = usageSummary?.feature_stats || {};
    const ranking = Object.entries(featureStats)
      .map(([feature, count]) => ({ feature, count }))
      .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
    return (
      <AdminPageCard title="AI 用量统计" subtitle="查看模型调用总量、趋势和功能调用排行。">
        <div className="admin-dashboard-mini-stats">
          <div><span>总调用</span><strong>{formatNumber(usageSummary?.total_calls_all)}</strong></div>
          <div><span>成功调用</span><strong>{formatNumber(usageSummary?.total_success)}</strong></div>
          <div><span>失败调用</span><strong>{formatNumber(usageSummary?.total_failed)}</strong></div>
          <div><span>累计 Token</span><strong>{formatNumber(usageSummary?.total_tokens_all)}</strong></div>
        </div>
        <TrendChart data={(usageTrend?.items || []).map((item) => ({ date: item.date?.slice(5), count: item.count }))} />
        {ranking.length > 0 ? (
          <DataTable columns={["功能", "调用次数"]} rows={ranking.map((item) => [item.feature, formatNumber(item.count)])} />
        ) : (
          <EmptyState title="暂无 AI 用量排行" description="产生 AI 调用后会展示功能使用排行。" />
        )}
      </AdminPageCard>
    );
  };

  const renderSettings = () => (
    <AdminPageCard title="系统设置" subtitle="查看当前平台基础配置与功能开关。">
      {(settings || []).length > 0 ? (
        <DataTable
          columns={["配置项", "当前值", "说明", "更新时间"]}
          rows={settings.map((item) => [item.key, String(item.value ?? ""), item.description || "-", formatDateTime(item.updated_at)])}
        />
      ) : (
        <EmptyState title="暂无设置项" description="系统设置初始化后会展示在这里。" />
      )}
    </AdminPageCard>
  );

  const renderLogs = () => (
    <AdminPageCard title="操作日志" subtitle="查看管理员操作审计记录。">
      {(logs?.items || []).length > 0 ? (
        <DataTable
          columns={["管理员", "动作", "目标", "结果", "时间", "IP"]}
          rows={logs.items.map((item) => [
            item.admin_username || "-",
            item.action || "-",
            item.target_username || item.target_id || item.target_type || "-",
            item.result || "-",
            formatDateTime(item.created_at),
            item.ip || "-",
          ])}
        />
      ) : (
        <EmptyState title="暂无操作日志" description="产生管理员操作记录后会展示在这里。" />
      )}
    </AdminPageCard>
  );

  const avatarInputRef = useRef(null);

  const triggerAvatarUpload = () => {
    avatarInputRef.current?.click();
  };

  const uploadAvatar = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reset input so same file can be re-selected
    e.target.value = "";
    setAvatarUploading(true);
    setActionError("");
    setActionSuccess("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("username", user.username);
      const res = await fetch(`${API_BASE}/me/avatar`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "头像上传失败");
      const newAvatarUrl = data.avatar_url || data.profile?.avatar_url || null;
      setUserAvatarUrl(newAvatarUrl);
      if (onUserUpdate && data.profile) {
        onUserUpdate(data.profile);
      }
      setActionSuccess("头像已更新");
    } catch (err) {
      setActionError(err.message || "头像上传失败");
    } finally {
      setAvatarUploading(false);
    }
  };

  const removeAvatar = async () => {
    if (!window.confirm("确认删除当前头像吗？")) return;
    setAvatarUploading(true);
    setActionError("");
    setActionSuccess("");
    try {
      const res = await fetch(`${API_BASE}/me/avatar?username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "头像删除失败");
      setUserAvatarUrl(null);
      if (onUserUpdate && data.profile) {
        onUserUpdate(data.profile);
      }
      setActionSuccess("头像已删除");
    } catch (err) {
      setActionError(err.message || "头像删除失败");
    } finally {
      setAvatarUploading(false);
    }
  };

  // Sync avatar URL from user data on mount / user change
  useEffect(() => {
    if (user?.avatar_url) setUserAvatarUrl(user.avatar_url);
  }, [user?.avatar_url]);

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); setActionSuccess("已复制到剪贴板"); }
    catch { setActionError("复制失败"); }
  };

  const renderProfile = () => {
    const displayName = profileForm.nickname || user?.nickname || user?.username || "管理员";
    const initial = (displayName || "管").charAt(0);
    const currentEmail = user?.email || "";
    const emailVerified = Boolean(user?.email_verified);

    return (
      <div className="admin-profile-v2">
        {actionError && <div className="admin-dashboard-error">{actionError}</div>}
        {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
        <input ref={avatarInputRef} type="file" accept="image/jpeg,image/png,image/webp" className="apv2-avatar-input" onChange={uploadAvatar} />

        {/* ── Hero card ── */}
        <div className="apv2-hero">
          <div className="apv2-hero-left">
            <div className="apv2-avatar-wrap">
              {userAvatarUrl ? (
                <span className="apv2-avatar">
                  <img
                    src={userAvatarUrl}
                    alt={displayName}
                    className="apv2-avatar-img"
                    onError={() => setUserAvatarUrl(null)}
                  />
                </span>
              ) : (
                <span className="apv2-avatar apv2-avatar--text">{initial}</span>
              )}
              <button
                type="button"
                className={`apv2-avatar-cam${avatarUploading ? " apv2-avatar-cam--loading" : ""}`}
                title="更换头像"
                onClick={triggerAvatarUpload}
                disabled={avatarUploading}
              >
                {avatarUploading ? "⏳" : "📷"}
              </button>
              {userAvatarUrl && !avatarUploading && (
                <button type="button" className="apv2-avatar-del" title="删除头像" onClick={removeAvatar}>✕</button>
              )}
            </div>
            <div className="apv2-hero-info">
              <div className="apv2-hero-name-row">
                <strong className="apv2-hero-name">{displayName}</strong>
                <span className="apv2-hero-badge">{adminRoleLabel}</span>
              </div>
              <p className="apv2-hero-desc">{adminRoleDesc}</p>
            </div>
          </div>

          <div className="apv2-hero-divider" />

          <div className="apv2-hero-right">
            <div className="apv2-hero-mini-cards">
              <div className="apv2-hero-mini">
                <span className="apv2-hero-mini-label">账号 / 用户名</span>
                <strong>{user?.username || "-"}</strong>
              </div>
              <div className="apv2-hero-mini">
                <span className="apv2-hero-mini-label">管理身份</span>
                <strong>{user?.admin_role || "unknown"}</strong>
              </div>
              <div className="apv2-hero-mini">
                <span className="apv2-hero-mini-label">当前邮箱</span>
                <strong className="apv2-hero-mini-email">{currentEmail || "未绑定"}</strong>
              </div>
            </div>
            <button type="button" className="apv2-logout-btn" onClick={() => onLogout ? onLogout() : setPage("login")}>
              <span>退出登录</span>
            </button>
          </div>
        </div>

        {/* ── Three cards row ── */}
        <div className="apv2-cards">
          {/* Card 1: Basic Info */}
          <div className="apv2-card">
            <div className="apv2-card-head">
              <div>
                <h3>基本信息</h3>
                <p>管理您的基础账户信息</p>
              </div>
            </div>
            <div className="apv2-card-body">
              <div className="apv2-field">
                <label>昵称</label>
                <div className="apv2-field-row">
                  <input value={profileForm.nickname} onChange={(e) => setProfileForm((prev) => ({ ...prev, nickname: e.target.value }))} placeholder="请输入昵称" />
                  <button type="button" className="apv2-icon-btn" title="编辑" onClick={() => document.querySelector('.apv2-field-row input')?.focus()}>✎</button>
                </div>
              </div>
              <div className="apv2-field">
                <label>账号 / 用户名</label>
                <div className="apv2-field-row">
                  <input value={user?.username || ""} readOnly />
                  <button type="button" className="apv2-icon-btn" title="复制" onClick={() => copyToClipboard(user?.username || "")}>⧉</button>
                </div>
              </div>
              <div className="apv2-field">
                <label>管理身份</label>
                <div className="apv2-field-row">
                  <span className="apv2-role-tag">{adminRoleLabel}</span>
                </div>
              </div>
              <button type="button" className="apv2-purple-btn" disabled={actionLoading === "profile"} onClick={saveProfile}>
                {actionLoading === "profile" ? "保存中..." : "保存修改"}
              </button>
            </div>
          </div>

          {/* Card 2: Security Settings */}
          <div className="apv2-card">
            <div className="apv2-card-head">
              <div>
                <h3>安全设置</h3>
                <p>加强账户安全，保护账户安全</p>
              </div>
              <div className="apv2-shield-deco">🛡</div>
            </div>
            <div className="apv2-card-body">
              <div className="apv2-field">
                <label>当前密码</label>
                <div className="apv2-pwd-row">
                  <input type={showOldPwd ? "text" : "password"} value={passwordForm.old_password} onChange={(e) => setPasswordForm((prev) => ({ ...prev, old_password: e.target.value }))} placeholder="请输入当前密码" />
                  <button type="button" className="apv2-eye-btn" onClick={() => setShowOldPwd(!showOldPwd)}>{showOldPwd ? "👁" : "👁‍🗨"}</button>
                </div>
              </div>
              <div className="apv2-field">
                <label>新密码</label>
                <div className="apv2-pwd-row">
                  <input type={showNewPwd ? "text" : "password"} value={passwordForm.new_password} onChange={(e) => setPasswordForm((prev) => ({ ...prev, new_password: e.target.value }))} placeholder="请输入新密码" />
                  <button type="button" className="apv2-eye-btn" onClick={() => setShowNewPwd(!showNewPwd)}>{showNewPwd ? "👁" : "👁‍🗨"}</button>
                </div>
              </div>
              <div className="apv2-field">
                <label>确认新密码</label>
                <div className="apv2-pwd-row">
                  <input type={showConfirmPwd ? "text" : "password"} value={passwordForm.confirm_password} onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirm_password: e.target.value }))} placeholder="请再次输入新密码" />
                  <button type="button" className="apv2-eye-btn" onClick={() => setShowConfirmPwd(!showConfirmPwd)}>{showConfirmPwd ? "👁" : "👁‍🗨"}</button>
                </div>
              </div>
              <button type="button" className="apv2-purple-btn" disabled={actionLoading === "password"} onClick={changePassword}>
                {actionLoading === "password" ? "修改中..." : "修改密码"}
              </button>
              <p className="apv2-hint">密码长度需 8-20 位，且包含字母、数字和符号的任意两种</p>
            </div>
          </div>

          {/* Card 3: Email Binding */}
          <div className="apv2-card">
            <div className="apv2-card-head">
              <div>
                <h3>邮箱绑定</h3>
                <p>绑定邮箱用于接收重要通知与安全验证</p>
              </div>
            </div>
            <div className="apv2-card-body">
              <div className="apv2-field">
                <label>当前邮箱</label>
                <div className="apv2-field-row">
                  <span className="apv2-current-email">{currentEmail || "未绑定邮箱"}</span>
                  {emailVerified && currentEmail && <span className="apv2-verified-tag">✓ 已绑定</span>}
                </div>
              </div>
              <div className="apv2-field">
                <label>新邮箱</label>
                <input value={emailForm.email} onChange={(e) => setEmailForm((prev) => ({ ...prev, email: e.target.value }))} placeholder="请输入新邮箱地址" />
              </div>
              <div className="apv2-field">
                <label>验证码</label>
                <div className="apv2-code-row">
                  <input placeholder="请输入验证码" value={emailForm.code} onChange={(e) => setEmailForm((prev) => ({ ...prev, code: e.target.value }))} />
                  <button type="button" className="apv2-code-btn" onClick={sendEmailCode} disabled={actionLoading === "email-code"}>
                    {actionLoading === "email-code" ? "发送中..." : "发送验证码"}
                  </button>
                </div>
              </div>
              <button type="button" className="apv2-purple-btn" disabled={actionLoading === "email-bind"} onClick={bindEmail}>
                {actionLoading === "email-bind" ? "绑定中..." : "绑定邮箱"}
              </button>
              <p className="apv2-hint">验证码将发送至当前邮箱，请注意查收</p>
            </div>
          </div>
        </div>
      </div>
    );
  };

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
    if (activePage === "adminQuota") return renderQuota();
    if (activePage === "adminStatistics") return renderStatistics();
    if (activePage === "adminUsage") return renderUsage();
    if (activePage === "adminSettings") return renderSettings();
    if (activePage === "adminLogs") return renderLogs();
    if (activePage === "adminProfile") return renderProfile();
    return renderDashboard();
  };

  return (
    <div className="admin-dashboard-shell">
      <aside className="admin-dashboard-sidebar">
        <div className="admin-dashboard-brand">
          <span className="admin-dashboard-logo">AI</span>
          <div>
            <strong>学习助手 管理平台</strong>
            <span>管理员</span>
          </div>
        </div>
        <nav className="admin-dashboard-nav" aria-label="管理员功能导航">
          {MENU_GROUPS.map((group) => (
            <div className="admin-dashboard-nav-group" key={group.title}>
              <p>{group.title}</p>
              {group.items.map((item) => (
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
            </div>
          ))}
        </nav>
      </aside>

      <main className="admin-dashboard-main">
        <header className="admin-dashboard-header">
          <div>
            <h1>{activeLabel}</h1>
            <p>{activePage === "adminProfile" ? "管理您的个人信息、账号安全与绑定设置" : `欢迎回来，管理员！今天是 ${formatToday()}`}</p>
          </div>
          <button className="admin-dashboard-profile" type="button" onClick={() => navigate("adminProfile")}>
            <span className="admin-dashboard-avatar">管</span>
            <strong>管理员</strong>
            <span>⌄</span>
          </button>
        </header>
        {renderContent()}
      </main>
    </div>
  );
}

function AdminPageCard({ title, subtitle, action, children }) {
  return (
    <section className="admin-dashboard-card admin-dashboard-section-card">
      <div className="admin-dashboard-section-head admin-dashboard-section-head--row">
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function DataTable({ columns, rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="admin-dashboard-table-wrap">
      <table className="admin-dashboard-table">
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ tone = "ok", children }) {
  return <span className={`admin-dashboard-status admin-dashboard-status--${tone}`}>{children}</span>;
}

function UsersTable({ rows, hideActions = false, onBan, onUnban, onDelete, onEditMembership, actionLoading = "" }) {
  if (!rows || rows.length === 0) {
    return <EmptyState title="暂无用户数据" description="当前没有可展示的用户记录。" />;
  }
  const columns = ["用户昵称", "用户ID", "账号", "三方向会员", "注册时间", "学习时长", "状态"];
  if (!hideActions) columns.push("操作");

  const M_BADGE = (m, sk) => {
    const mb = (m && m[sk]) || {};
    const label = mb.plan_label || (mb.is_enabled ? mb.plan : "未开通");
    const enabled = mb.is_enabled;
    return (
      <span key={sk} className={`adm-membership-badge${enabled ? "" : " disabled"}`}
        title={sk === "exam_11408" ? "11408 考研" : sk === "course" ? "课程学习" : "编程能力提升"}>
        {sk === "exam_11408" ? "📘" : sk === "course" ? "📗" : "📙"} {label}
      </span>
    );
  };

  const tableRows = rows.map((item) => {
    const isBanned = Boolean(item.is_banned);
    const isAdmin = Boolean(item.is_admin) || (item.admin_role && item.admin_role !== "none");
    const m = item.memberships || {};
    const status = isBanned ? <StatusBadge tone="danger">已封禁</StatusBadge> : <StatusBadge tone="ok">正常</StatusBadge>;
    const membershipCell = (
      <div className="adm-membership-cell">
        {M_BADGE(m, "exam_11408")}
        {M_BADGE(m, "course")}
        {M_BADGE(m, "programming")}
      </div>
    );
    const actions = (
      <div className="admin-dashboard-actions">
        {!isAdmin && (
          <button type="button" disabled={!!actionLoading}
            onClick={() => onEditMembership?.(item)} style={{color:"#7c3aed",borderColor:"#c4b5fd"}}>
            会员
          </button>
        )}
        {isBanned ? (
          <button type="button" disabled={!!actionLoading || isAdmin} onClick={() => onUnban?.(item)}>解封</button>
        ) : (
          <button type="button" className="warning" disabled={!!actionLoading || isAdmin} onClick={() => onBan?.(item)}>封号</button>
        )}
        <button type="button" className="danger" disabled={!!actionLoading || isAdmin} onClick={() => onDelete?.(item)}>删除</button>
      </div>
    );
    const base = [
      <><span className="admin-dashboard-user-avatar">U</span>{displayUserName(item)}</>,
      item.user_id || item.id || "-",
      item.username || "-",
      membershipCell,
      formatDateTime(item.register_time || item.created_at),
      `${formatNumber(item.learning_hours, 1)} 小时`,
      status,
    ];
    if (!hideActions) base.push(actions);
    return base;
  });
  return <DataTable columns={columns} rows={tableRows} />;
}

function MembershipEditModal({ user: targetUser, form, onChange, onSave, onClose, loading }) {
  const SERVICE_KEYS = ["exam_11408", "course", "programming"];
  const SERVICE_INFO = {
    exam_11408: { name: "11408 考研", icon: "📘", plans: { free: "普通用户", monthly: "月度冲刺包", quarterly: "季度强化包", full: "全程备考包" }, disabledHint: "当前用户尚未开通 11408 考研服务" },
    course: { name: "课程学习", icon: "📗", plans: { free: "普通用户", monthly: "月度学习包", quarterly: "季度学习包", full: "全程学习包" }, disabledHint: "当前用户尚未开通课程学习服务" },
    programming: { name: "编程能力提升", icon: "📙", plans: { free: "普通用户", monthly: "月度练习包", quarterly: "季度练习包", full: "年度提升包" }, disabledHint: "当前用户尚未开通编程能力提升服务" },
  };
  const updateField = (sk, field, val) => {
    onChange((prev) => ({ ...prev, [sk]: { ...prev[sk], [field]: val } }));
  };

  return (
    <div className="esp-modal-overlay" onClick={loading ? undefined : onClose}>
      <div className="esp-modal" style={{maxWidth:560}} onClick={(e) => e.stopPropagation()}>
        <div className="esp-modal-header">
          <h2>三方向服务权限 / 会员设置 — {targetUser.nickname || targetUser.username}</h2>
          <button type="button" className="esp-modal-close" onClick={onClose} disabled={loading}>✕</button>
        </div>
        <div className="esp-modal-body">
          {SERVICE_KEYS.map((sk) => {
            const info = SERVICE_INFO[sk];
            const f = form[sk] || { is_enabled: false, plan: "free" };
            return (
              <div key={sk} className={`adm-membership-card${f.is_enabled ? "" : " disabled"}`}>
                <div className="adm-membership-card-head">
                  <span>{info.icon} <strong>{info.name}</strong></span>
                  <label className="adm-toggle">
                    <input type="checkbox" checked={f.is_enabled}
                      onChange={(e) => updateField(sk, "is_enabled", e.target.checked)} disabled={loading} />
                    <span className="adm-toggle-slider" />
                    <span className="adm-toggle-label">{f.is_enabled ? "已开通" : "未开通"}</span>
                  </label>
                </div>
                {f.is_enabled ? (
                  <div className="adm-membership-card-body">
                    <label>会员等级</label>
                    <select value={f.plan} onChange={(e) => updateField(sk, "plan", e.target.value)} disabled={loading}>
                      {Object.entries(info.plans).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <p className="adm-membership-hint">{info.disabledHint}</p>
                )}
              </div>
            );
          })}
        </div>
        <div className="esp-modal-footer">
          <button type="button" className="esp-modal-cancel" onClick={onClose} disabled={loading}>取消</button>
          <button type="button" className="esp-modal-save" onClick={onSave} disabled={loading}>
            {loading ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}
