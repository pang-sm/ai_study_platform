import { useEffect, useMemo, useRef, useState } from "react";
import { resolveMediaUrl } from "../utils/mediaUrl.js";
import AdminSupportCenter from "./AdminSupportCenter.jsx";

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
      { page: "adminFeedback", label: "用户反馈", icon: "F" },
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
      { page: "adminAdmins", label: "管理员管理", icon: "M" },
    ],
  },
];

const MENU_ITEMS = MENU_GROUPS.flatMap((group) => group.items);
MENU_GROUPS[1].items.push({ page: "adminRedemptionCodes", label: "兑换码", icon: "C" });
MENU_ITEMS.push(MENU_GROUPS[1].items[MENU_GROUPS[1].items.length - 1]);
const WEEKDAY_LABELS = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

// ── 用户可见 enum → 中文映射（仅改 UI 文案，不改后端内部 key）──
const FEATURE_LABELS = {
  chat: "AI 对话",
  question_generate: "AI 出题",
  code_analyze: "代码分析",
  challenge_generate: "挑战题生成",
  learning_diagnosis: "学习诊断",
  knowledge_generate: "知识内容生成",
  learning_plan_generate: "学习计划生成",
  material_link_recommend: "学习资料推荐",
  question_feedback: "题目反馈",
  learning_report_generate: "学习报告生成",
  challenge_explain: "挑战题讲解",
  challenge_test_gen: "挑战测试生成",
  material_summary: "资料摘要",
};

const SERVICE_KEY_LABELS = {
  exam_11408: "11408 考研",
  course_learning: "课程学习",
  programming: "编程学习",
};

const STATUS_LABELS = {
  active: "有效",
  disabled: "已停用",
  expired: "已过期",
  success: "成功",
  failed: "失败",
  pending: "待处理",
  revoked: "已撤销",
  exhausted: "已用完",
  inactive: "未生效",
  normal: "正常",
  banned: "已封禁",
};

const PLAN_LABELS = {
  free: "免费版",
  monthly: "月度学习包",
  quarterly: "季度学习包",
  full: "全程学习包",
  monthly_sprint: "月度冲刺包",
  quarterly_boost: "季度强化包",
  full_exam: "全程考包",
  exam_monthly: "月度冲刺包",
  exam_quarterly: "季度强化包",
  exam_yearly: "全程考包",
  pro: "专业版",
  admin: "管理员",
  gift_pro: "礼品卡权益",
};

const ROLE_LABELS = {
  super_admin: "超级管理员",
  operator: "普通管理员",
  auditor: "只读审计员",
  none: "非管理员",
};

const ACTION_LABELS = {
  update_admin_role: "修改管理员角色",
  update_plan: "修改用户套餐",
  admin_membership_update: "修改会员",
  audit_logs_export: "导出审计日志",
  backup_create: "创建数据备份",
  backup_download: "下载数据备份",
  backup_delete: "删除数据备份",
  model_config_update: "修改模型配置",
  quota_override_create: "新增额度覆盖",
  quota_override_update: "修改额度覆盖",
  quota_override_delete: "删除额度覆盖",
};

function zhFeature(feature) { return FEATURE_LABELS[feature] || feature || "-"; }
function zhServiceKey(key) { return SERVICE_KEY_LABELS[key] || key || "-"; }
function zhPlan(plan) { return PLAN_LABELS[plan] || plan || "免费版"; }
function zhRole(role) { return ROLE_LABELS[role] || role || "非管理员"; }
function zhStatus(status) { return STATUS_LABELS[status] || status || "-"; }
function zhAction(action) { return ACTION_LABELS[action] || action || "-"; }

const ORDER_STATUS_LABELS = {
  pending: "待支付",
  paid: "已支付",
  cancelled: "已取消",
  expired: "已过期",
  refund_pending: "退款中",
  partially_refunded: "部分退款",
  refunded: "已退款",
  failed: "支付失败",
};
const PAYMENT_PROVIDER_LABELS = { mock: "模拟支付" };
function zhOrderStatus(status) { return ORDER_STATUS_LABELS[status] || status || "-"; }
function zhProvider(provider) { return PAYMENT_PROVIDER_LABELS[provider] || provider || "-"; }

const QUOTA_KEY_LABELS = {
  ai_chat_daily_limit: "AI 对话",
  ai_question_daily_limit: "AI 出题",
  single_file_limit_mb: "单文件大小",
  material_upload_limit_mb: "资料总容量",
};
function zhQuotaKey(k) { return QUOTA_KEY_LABELS[k] || k; }

function logDetailRows(item) {
  const d = item.details || {};
  const rows = [];
  const add = (label, value) => { if (value !== undefined && value !== null && value !== "") rows.push([label, String(value)]); };
  if (d.service_key) add("业务方向", zhServiceKey(d.service_key));
  if (d.quota_key) add("额度项目", zhQuotaKey(d.quota_key));
  if (d.old_override !== undefined) add("修改前覆盖值", d.old_override);
  if (d.new_override !== undefined) add("修改后覆盖值", d.new_override);
  if (d.effective_before !== undefined) add("修改前生效额度", d.effective_before);
  if (d.effective_after !== undefined) add("修改后生效额度", d.effective_after);
  if (d.old_role) add("原角色", zhRole(d.old_role));
  if (d.new_role) add("新角色", zhRole(d.new_role));
  if (d.old && typeof d.old === "object") {
    if (d.old.plan) add("原套餐", zhPlan(d.old.plan));
    if (d.old.status) add("原状态", zhStatus(d.old.status));
    if (d.old.expires_at) add("原到期时间", formatDateTime(d.old.expires_at));
  }
  if (d.new && typeof d.new === "object") {
    if (d.new.plan) add("新套餐", zhPlan(d.new.plan));
    if (d.new.status) add("新状态", zhStatus(d.new.status));
    if (d.new.expires_at) add("新到期时间", formatDateTime(d.new.expires_at));
  }
  if (d.old_is_active !== undefined) add("原状态", d.old_is_active ? "启用" : "停用");
  if (d.new_is_active !== undefined) add("新状态", d.new_is_active ? "启用" : "停用");
  if (d.reason) add("原因", d.reason);
  if (d.username) add("账号", d.username);
  return rows;
}

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
  const [membershipCatalog, setMembershipCatalog] = useState([]);
  const [announcements, setAnnouncements] = useState(null);
  const [settings, setSettings] = useState(null);
  const [usageSummary, setUsageSummary] = useState(null);
  const [usageTrend, setUsageTrend] = useState(null);
  const [statisticsData, setStatisticsData] = useState(null);
  const [aiServiceFilter, setAiServiceFilter] = useState("");
  const [aiTrendDays, setAiTrendDays] = useState(7);
  const [growthDays, setGrowthDays] = useState(7);
  const [quota, setQuota] = useState(null);
  const [quotaKeyword, setQuotaKeyword] = useState("");
  const [quotaDetail, setQuotaDetail] = useState(null);
  const [quotaOverrideTarget, setQuotaOverrideTarget] = useState(null);
  const [quotaOverrideValue, setQuotaOverrideValue] = useState("");
  const [quotaOverrideError, setQuotaOverrideError] = useState("");
  const [logs, setLogs] = useState(null);
  const [redemptionCodes, setRedemptionCodes] = useState([]);
  const [redemptionStatus, setRedemptionStatus] = useState("all");
  const [redemptionForm, setRedemptionForm] = useState({ service_key: "course_learning", target_plan: "monthly", membership_duration_days: 30, code_expires_at: "", max_redemptions: 1, count: 1, note: "" });
  const [createdRedemptionCodes, setCreatedRedemptionCodes] = useState([]);
  const [redemptionDetail, setRedemptionDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [supportUnreadCount, setSupportUnreadCount] = useState(0);
  const [userKeyword, setUserKeyword] = useState("");
  const [userStatus, setUserStatus] = useState("all");
  const [memberKeyword, setMemberKeyword] = useState("");
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
  const [userAvatarUrl, setUserAvatarUrl] = useState(() => resolveMediaUrl(user?.avatar_url, API_BASE) || null);
  const [userPage, setUserPage] = useState(1);
  const [userPageSize, setUserPageSize] = useState(20);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [logPage, setLogPage] = useState(1);
  const [logPageSize, setLogPageSize] = useState(20);
  const [logActor, setLogActor] = useState("");
  const [logAction, setLogAction] = useState("");
  const [logDetail, setLogDetail] = useState(null);
  const [adminsData, setAdminsData] = useState(null);
  const [adminKeyword, setAdminKeyword] = useState("");
  const [showAdminCreate, setShowAdminCreate] = useState(false);
  const [adminCreateForm, setAdminCreateForm] = useState({ username: "", password: "", confirm_password: "", nickname: "" });
  const [adminCreateError, setAdminCreateError] = useState("");
  const [ordersData, setOrdersData] = useState(null);
  const [orderKeyword, setOrderKeyword] = useState("");
  const [orderService, setOrderService] = useState("");
  const [orderPlan, setOrderPlan] = useState("");
  const [orderStatusFilter, setOrderStatusFilter] = useState("");
  const [orderProvider, setOrderProvider] = useState("");
  const [orderPage, setOrderPage] = useState(1);
  const [orderPageSize, setOrderPageSize] = useState(20);
  const [orderDetail, setOrderDetail] = useState(null);
  const [settingsDraft, setSettingsDraft] = useState({});
  const [settingsSaving, setSettingsSaving] = useState(false);
  const isSuperAdmin = user?.admin_role === "super_admin" || user?.username === "admin";
  const adminRoleLabel = zhRole(user?.admin_role === "operator" ? "operator" : (user?.admin_role || (user?.is_admin ? "super_admin" : "none")));
  const adminRoleDesc = isSuperAdmin ? "负责平台整体运营与管理" : "负责日常运营与用户服务";

  const navigate = (pageName) => {
    if (setPage) setPage(pageName);
  };

  const getJson = async (url, options) => {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "数据加载失败");
    return data;
  };

  const loadCurrentPage = async () => {
    if (!user?.username) return;
    if (activePage === "adminFeedback") return;
    setLoading(true);
    setError("");
    try {
      if (activePage === "adminDashboard") {
        setDashboard(await getJson(`${API_BASE}/admin/dashboard`));
      } else if (activePage === "adminAnnouncements") {
        const data = await getJson(`${API_BASE}/admin/announcements`);
        setAnnouncements(data.items || []);
      } else if (activePage === "adminUsers") {
        const params = new URLSearchParams({ page: String(userPage), page_size: String(userPageSize) });
        if (userKeyword.trim()) params.set("keyword", userKeyword.trim());
        if (userStatus !== "all") params.set("status", userStatus);
        const [users, catalog] = await Promise.all([
          getJson(`${API_BASE}/admin/users?${params.toString()}`),
          getJson(`${API_BASE}/admin/memberships/catalog`),
        ]);
        setUsersData(users);
        setMembershipCatalog(catalog.services || []);
        setSelectedUsers([]);
      } else if (activePage === "adminMembers") {
        const params = new URLSearchParams({ page_size: "100" });
        if (memberKeyword.trim()) params.set("keyword", memberKeyword.trim());
        const [memberships, catalog] = await Promise.all([
          getJson(`${API_BASE}/admin/memberships?${params.toString()}`),
          getJson(`${API_BASE}/admin/memberships/catalog`),
        ]);
        setMembersData(memberships);
        setMembershipCatalog(catalog.services || []);
      } else if (activePage === "adminQuota") {
        const params = new URLSearchParams({ page_size: "100" });
        if (quotaKeyword.trim()) params.set("keyword", quotaKeyword.trim());
        setQuota(await getJson(`${API_BASE}/admin/quota?${params.toString()}`));
      } else if (activePage === "adminStatistics") {
        setStatisticsData(await getJson(`${API_BASE}/admin/statistics`));
      } else if (activePage === "adminUsage") {
        const params = new URLSearchParams({ days: String(aiTrendDays) });
        if (aiServiceFilter) params.set("service_key", aiServiceFilter);
        const [summary, trend] = await Promise.all([
          getJson(`${API_BASE}/admin/usage-summary`),
          getJson(`${API_BASE}/admin/usage-trend?${params.toString()}`),
        ]);
        setUsageSummary(summary);
        setUsageTrend(trend);
      } else if (activePage === "adminSettings") {
        const data = await getJson(`${API_BASE}/admin/settings`);
        setSettings(data.items || []);
      } else if (activePage === "adminLogs") {
        const params = new URLSearchParams({ page: String(logPage), page_size: String(logPageSize) });
        if (logActor.trim()) params.set("actor", logActor.trim());
        if (logAction.trim()) params.set("action", logAction.trim());
        setLogs(await getJson(`${API_BASE}/admin/logs?${params.toString()}`));
      } else if (activePage === "adminAdmins") {
        const params = new URLSearchParams();
        if (adminKeyword.trim()) params.set("keyword", adminKeyword.trim());
        setAdminsData(await getJson(`${API_BASE}/admin/admins?${params.toString()}`));
      } else if (activePage === "adminOrders") {
        const params = new URLSearchParams({ page: String(orderPage), page_size: String(orderPageSize) });
        if (orderKeyword.trim()) params.set("keyword", orderKeyword.trim());
        if (orderService) params.set("service_key", orderService);
        if (orderPlan) params.set("plan", orderPlan);
        if (orderStatusFilter) params.set("status", orderStatusFilter);
        if (orderProvider) params.set("provider", orderProvider);
        setOrdersData(await getJson(`${API_BASE}/admin/orders?${params.toString()}`));
      } else if (activePage === "adminRedemptionCodes") {
        const params = new URLSearchParams({ status: redemptionStatus });
        setRedemptionCodes((await getJson(`${API_BASE}/admin/membership/redemption-codes?${params.toString()}`)).items || []);
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
  }, [activePage, user?.username, userStatus, redemptionStatus, userPage, userPageSize, logPage, logPageSize, orderPage, orderPageSize, aiServiceFilter, aiTrendDays]);

  useEffect(() => {
    fetch(`${API_BASE}/admin/support/unread-count`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setSupportUnreadCount(Number(d.count || 0)))
      .catch(() => {});
  }, [activePage, user?.username]);

  useEffect(() => {
    setProfileForm({ nickname: user?.nickname || "", avatar: user?.avatar || "" });
    setEmailForm((prev) => ({ ...prev, email: user?.email || "" }));
  }, [user?.nickname, user?.avatar, user?.email]);

  const overview = dashboard?.overview || {};
  const statCards = useMemo(() => ([
    { label: "普通用户", value: formatNumber(overview.total_users), sub: "不含管理员账号", icon: "U", tone: "purple" },
    { label: "今日新增", value: formatNumber(overview.new_users_today), sub: "今日新增用户", icon: "＋", tone: "blue" },
    { label: "有效付费用户", value: formatNumber(overview.paid_users), sub: "去重后的付费用户", icon: "V", tone: "green" },
    { label: "今日 AI 调用", value: formatNumber(overview.today_ai_calls), sub: "今日成功 AI 调用", icon: "⚡", tone: "orange" },
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
        body: JSON.stringify({}),
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
        body: JSON.stringify({ reason }),
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
        body: JSON.stringify({}),
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
      await getJson(`${API_BASE}/admin/users/${item.user_id}`, {
        method: "DELETE",
      });
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "删除用户失败");
    } finally {
      setActionLoading("");
    }
  };

  const toggleSelectUser = (id) => {
    setSelectedUsers((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleSelectAll = () => {
    const ids = (usersData?.items || []).map((u) => u.user_id).filter(Boolean);
    if (ids.length && ids.every((id) => selectedUsers.includes(id))) setSelectedUsers([]);
    else setSelectedUsers(ids);
  };

  const batchAction = async (action) => {
    if (!selectedUsers.length) return;
    const label = { ban: "封禁", unban: "解封", delete: "删除" }[action];
    const msg = action === "delete"
      ? `确认删除选中的 ${selectedUsers.length} 个用户吗？删除后该用户将无法登录。`
      : `确认批量${label}选中的 ${selectedUsers.length} 个用户吗？`;
    if (!window.confirm(msg)) return;
    setActionError("");
    setActionSuccess("");
    setActionLoading(`batch-${action}`);
    try {
      const data = await getJson(`${API_BASE}/admin/users/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_ids: selectedUsers, action }),
      });
      setSelectedUsers([]);
      setActionSuccess(`批量${label}完成：${data.succeeded?.length || 0} 个成功${data.skipped?.length ? `，${data.skipped.length} 个跳过` : ""}`);
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || `批量${label}失败`);
    } finally {
      setActionLoading("");
    }
  };

  const createAdmin = async () => {
    setAdminCreateError("");
    if (!adminCreateForm.username.trim()) { setAdminCreateError("请输入管理员账号"); return; }
    if (adminCreateForm.password !== adminCreateForm.confirm_password) { setAdminCreateError("两次输入的密码不一致"); return; }
    setActionLoading("admin-create");
    try {
      await getJson(`${API_BASE}/admin/admins`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(adminCreateForm),
      });
      setShowAdminCreate(false);
      setAdminCreateForm({ username: "", password: "", confirm_password: "", nickname: "" });
      setActionSuccess("普通管理员创建成功");
      await loadCurrentPage();
    } catch (err) {
      setAdminCreateError(err.message || "创建失败");
    } finally {
      setActionLoading("");
    }
  };

  const toggleAdminStatus = async (adminItem) => {
    const toActive = !adminItem.is_active;
    if (!window.confirm(`确认${toActive ? "启用" : "停用"}管理员 ${adminItem.username} 吗？`)) return;
    setActionLoading(`admin-status-${adminItem.user_id}`);
    try {
      await getJson(`${API_BASE}/admin/admins/${adminItem.id || adminItem.user_id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: toActive }),
      });
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "操作失败");
    } finally {
      setActionLoading("");
    }
  };

  const openMembershipEditor = (item) => {
    const m = item.memberships || {};
    setMembershipForm({
      exam_11408: { is_enabled: m.exam_11408?.is_enabled ?? false, plan: m.exam_11408?.plan || "free", status: m.exam_11408?.status || "disabled", expires_at: m.exam_11408?.expires_at || "" },
      course_learning: { is_enabled: m.course_learning?.is_enabled ?? false, plan: m.course_learning?.plan || "free", status: m.course_learning?.status || "disabled", expires_at: m.course_learning?.expires_at || "" },
      programming: { is_enabled: m.programming?.is_enabled ?? false, plan: m.programming?.plan || "free", status: m.programming?.status || "disabled", expires_at: m.programming?.expires_at || "" },
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
        body: JSON.stringify({ memberships: membershipForm }),
      });
      setEditingMemberUser(null);
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "修改会员失败");
    } finally {
      setActionLoading("");
    }
  };

  const loadQuotaDetail = async (user) => {
    setActionError("");
    setActionSuccess("");
    setQuotaOverrideError("");
    setQuotaDetail(await getJson(`${API_BASE}/admin/quota/${user.user_id || user.id}`));
  };

  const openQuotaOverride = (serviceKey, quota) => {
    setQuotaOverrideError("");
    setQuotaOverrideTarget({ service_key: serviceKey, quota_key: quota.quota_key, label: quota.label, current: quota.override_limit });
    setQuotaOverrideValue(quota.override_limit == null ? String(quota.effective_limit) : String(quota.override_limit));
  };

  const saveQuotaOverride = async () => {
    if (!quotaDetail || !quotaOverrideTarget) return;
    const limit = Number(quotaOverrideValue);
    if (!Number.isInteger(limit) || limit < 0) {
      setQuotaOverrideError("请输入非负整数");
      return;
    }
    setActionLoading("quota-override");
    setQuotaOverrideError("");
    try {
      await getJson(`${API_BASE}/admin/quota/${quotaDetail.user_id}/override`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          service_key: quotaOverrideTarget.service_key,
          quota_key: quotaOverrideTarget.quota_key,
          limit,
        }),
      });
      setQuotaOverrideTarget(null);
      setActionSuccess("额度覆盖已保存");
      await loadQuotaDetail({ user_id: quotaDetail.user_id });
    } catch (err) {
      setQuotaOverrideError(err.message || "保存失败");
    } finally {
      setActionLoading("");
    }
  };

  const deleteQuotaOverride = async (serviceKey, quotaKey) => {
    if (!quotaDetail) return;
    setActionError("");
    setActionSuccess("");
    setActionLoading(`del-${serviceKey}-${quotaKey}`);
    try {
      await getJson(
        `${API_BASE}/admin/quota/${quotaDetail.user_id}/override?service_key=${encodeURIComponent(serviceKey)}&quota_key=${encodeURIComponent(quotaKey)}`,
        { method: "DELETE" },
      );
      setActionSuccess("已删除覆盖，恢复套餐默认值");
      await loadQuotaDetail({ user_id: quotaDetail.user_id });
    } catch (err) {
      setActionError(err.message || "删除失败");
    } finally {
      setActionLoading("");
    }
  };

  const SERVICE_LABELS = {
    exam_11408: { name: "11408 考研" }, course_learning: { name: "课程学习" }, programming: { name: "编程能力提升" },
  };
  const memberUsers = useMemo(() => {
    const grouped = new Map();
    (membersData?.items || []).forEach((item) => {
      const key = String(item.user_id);
      const user = grouped.get(key) || { user_id: item.user_id, username: item.username, nickname: item.nickname, memberships: {} };
      user.memberships[item.service_key] = item;
      grouped.set(key, user);
    });
    return [...grouped.values()];
  }, [membersData]);

  const membershipState = (membership) => {
    if (!membership || membership.plan === "free") return { label: "免费", tone: "muted" };
    if (membership.is_expired) return { label: "已过期", tone: "danger" };
    if (!membership.is_enabled || membership.status === "disabled") return { label: "已停用", tone: "muted" };
    if (membership.current_is_effective) return { label: "有效会员", tone: "ok" };
    return { label: "未生效", tone: "warning" };
  };

  const membershipCell = (membership) => {
    const state = membershipState(membership);
    return <><span>{zhPlan(membership?.plan)}</span><StatusBadge tone={state.tone}>{state.label}</StatusBadge></>;
  };

  const renderDashboard = () => (
    <>
      <section className="admin-dashboard-stats">
        {statCards.map((card) => (
          <div className="admin-dashboard-stat" key={card.label}>
            <span className={`admin-dashboard-stat-icon admin-dashboard-stat-icon--${card.tone}`}>{card.icon}</span>
            <div className="admin-dashboard-stat-body">
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
            <div style={{ display: "flex", gap: 6 }}>
              <button type="button" className={growthDays === 7 ? "admin-dashboard-primary-action" : ""} onClick={() => setGrowthDays(7)}>近7天</button>
              <button type="button" className={growthDays === 30 ? "admin-dashboard-primary-action" : ""} onClick={() => setGrowthDays(30)}>近30天</button>
            </div>
          </div>
          <TrendChart data={(dashboard?.user_growth || []).slice(-growthDays)} emptyDescription="该时间范围暂无数据" />
        </div>

        <div className="admin-dashboard-card admin-dashboard-chart-card">
          <div className="admin-dashboard-card-head">
            <h2>AI 使用趋势</h2>
            <span className="admin-dashboard-filter">近7天</span>
          </div>
          <TrendChart data={dashboard?.ai_usage_trend || []} emptyDescription="该时间范围暂无数据" />
        </div>
      </section>

      <section className="admin-dashboard-card">
        <div className="admin-dashboard-card-head">
          <h2>待处理事项</h2>
        </div>
        <div className="admin-dashboard-todo-grid">
          <button type="button" className="admin-dashboard-todo" onClick={() => navigate("adminFeedback")}>
            <strong>{formatNumber(dashboard?.support_summary?.unread)}</strong>
            <span>用户反馈未读</span>
          </button>
          <button type="button" className="admin-dashboard-todo" onClick={() => navigate("adminFeedback")}>
            <strong>{formatNumber(dashboard?.support_summary?.pending)}</strong>
            <span>待处理工单</span>
          </button>
          <button type="button" className="admin-dashboard-todo" onClick={() => navigate("adminFeedback")}>
            <strong>{formatNumber(dashboard?.support_summary?.waiting_confirmation)}</strong>
            <span>等待用户确认</span>
          </button>
        </div>
      </section>

      <section className="admin-dashboard-card">
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

  const renderUsers = () => {
    const total = usersData?.total || 0;
    const totalPages = usersData?.total_pages || Math.max(1, Math.ceil(total / userPageSize));
    const pageIds = (usersData?.items || []).map((u) => u.user_id).filter(Boolean);
    const allSelected = pageIds.length > 0 && pageIds.every((id) => selectedUsers.includes(id));
    return (
      <AdminPageCard title="用户管理" subtitle="管理用户账号、状态和权限">
        <div className="admin-dashboard-toolbar">
          <input
            value={userKeyword}
            placeholder="按用户名 / 昵称 / 邮箱搜索"
            onChange={(e) => setUserKeyword(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { setUserPage(1); loadCurrentPage(); } }}
          />
          <select value={userStatus} onChange={(e) => { setUserStatus(e.target.value); setUserPage(1); }}>
            <option value="all">全部</option>
            <option value="normal">正常</option>
            <option value="banned">已封禁</option>
          </select>
          <button type="button" onClick={() => { setUserPage(1); loadCurrentPage(); }}>搜索</button>
        </div>
        {actionError && <div className="admin-dashboard-error">{actionError}</div>}
        {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
        {selectedUsers.length > 0 && (
          <div className="admin-dashboard-toolbar" style={{ background: "#f5f3ff", borderRadius: 8, padding: 8 }}>
            <span>已选 {selectedUsers.length} 个用户</span>
            <button type="button" onClick={() => batchAction("ban")} disabled={!!actionLoading}>批量封禁</button>
            <button type="button" onClick={() => batchAction("unban")} disabled={!!actionLoading}>批量解封</button>
            {isSuperAdmin && <button type="button" className="danger" onClick={() => batchAction("delete")} disabled={!!actionLoading}>批量删除</button>}
          </div>
        )}
        <UsersTable
          rows={usersData?.items || []}
          onBan={banUser} onUnban={unbanUser} onDelete={isSuperAdmin ? deleteUser : null}
          onEditMembership={openMembershipEditor}
          actionLoading={actionLoading}
          selectable
          selectedUsers={selectedUsers}
          allSelected={allSelected}
          onToggleSelect={toggleSelectUser}
          onToggleSelectAll={toggleSelectAll}
        />
        <div className="admin-dashboard-toolbar" style={{ justifyContent: "space-between" }}>
          <span style={{ color: "#64748b" }}>共 {total} 个用户 · 第 {userPage} / {totalPages} 页</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select value={userPageSize} onChange={(e) => { setUserPageSize(Number(e.target.value)); setUserPage(1); }}>
              <option value={20}>每页 20</option>
              <option value={50}>每页 50</option>
              <option value={100}>每页 100</option>
            </select>
            <button type="button" disabled={userPage <= 1} onClick={() => setUserPage((p) => p - 1)}>上一页</button>
            <button type="button" disabled={userPage >= totalPages} onClick={() => setUserPage((p) => p + 1)}>下一页</button>
          </div>
        </div>
        {editingMemberUser && (
          <MembershipEditModal
            user={editingMemberUser}
            form={membershipForm}
            onChange={setMembershipForm}
            onSave={saveMemberships}
            onClose={() => setEditingMemberUser(null)}
            loading={actionLoading === "membership"}
            catalog={membershipCatalog}
          />
        )}
      </AdminPageCard>
    );
  };

  const viewOrder = (item) => setOrderDetail(item);

  const cancelOrder = async (item) => {
    if (!window.confirm(`确认取消订单 #${item.id}（${zhServiceKey(item.service_key)} / ${zhPlan(item.target_plan)}）吗？`)) return;
    setActionError("");
    setActionLoading(`cancel-order-${item.id}`);
    try {
      await getJson(`${API_BASE}/admin/orders/${item.id}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "取消失败");
    } finally {
      setActionLoading("");
    }
  };

  const refundOrder = async (item) => {
    if (!window.confirm(`确认退款订单 #${item.id}（${zhServiceKey(item.service_key)} / ${zhPlan(item.target_plan)}，金额 ¥${item.amount_yuan}）吗？退款后用户会员将按剩余订单重新计算。`)) return;
    setActionError("");
    setActionSuccess("");
    setActionLoading(`refund-order-${item.id}`);
    try {
      await getJson(`${API_BASE}/admin/orders/${item.id}/refund`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "管理员退款" }),
      });
      setActionSuccess("订单已退款");
      await loadCurrentPage();
    } catch (err) {
      setActionError(err.message || "退款失败");
    } finally {
      setActionLoading("");
    }
  };

  const renderOrders = () => {
    const total = ordersData?.total || 0;
    const totalPages = ordersData?.total_pages || Math.max(1, Math.ceil(total / orderPageSize));
    const orders = ordersData?.items || [];
    return (
      <AdminPageCard title="订单管理" subtitle="查看会员订单、支付与权益授予情况。">
        <div className="admin-dashboard-toolbar">
          <input value={orderKeyword} placeholder="按用户名 / 昵称 / 订单号 / ID 搜索" onChange={(e) => setOrderKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { setOrderPage(1); loadCurrentPage(); } }} />
          <select value={orderService} onChange={(e) => { setOrderService(e.target.value); setOrderPage(1); }}>
            <option value="">全部方向</option>
            <option value="exam_11408">11408 考研</option>
            <option value="course_learning">课程学习</option>
            <option value="programming">编程学习</option>
          </select>
          <select value={orderStatusFilter} onChange={(e) => { setOrderStatusFilter(e.target.value); setOrderPage(1); }}>
            <option value="">全部状态</option>
            <option value="pending">待支付</option>
            <option value="paid">已支付</option>
            <option value="cancelled">已取消</option>
            <option value="expired">已过期</option>
          </select>
          <button type="button" onClick={() => { setOrderPage(1); loadCurrentPage(); }}>查询</button>
          <button type="button" onClick={() => { setOrderKeyword(""); setOrderService(""); setOrderStatusFilter(""); setOrderPage(1); setTimeout(loadCurrentPage, 0); }}>重置</button>
        </div>
        {actionError && <div className="admin-dashboard-error">{actionError}</div>}
        {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
        {orders.length > 0 ? (
          <DataTable
            columns={["订单", "用户", "业务方向", "套餐", "金额", "支付方式", "状态", "创建时间", "操作"]}
            rows={orders.map((item) => [
              <><strong>#{item.id}</strong>{item.order_no ? <small style={{ display: "block", color: "#64748b" }}>{item.order_no}</small> : <small style={{ display: "block", color: "#94a3b8" }}>（历史订单无编号）</small>}</>,
              <>{item.nickname || item.username}<small style={{ display: "block", color: "#64748b" }}>ID {item.user_id}</small></>,
              zhServiceKey(item.service_key),
              zhPlan(item.target_plan),
              `¥${formatNumber(item.amount_yuan, 2)}`,
              item.is_mock ? <StatusBadge tone="muted">模拟支付</StatusBadge> : zhProvider(item.payment_provider),
              <StatusBadge tone={item.status === "paid" ? "ok" : item.status === "cancelled" ? "muted" : "warning"}>{zhOrderStatus(item.refund_status === "refunded" ? "refunded" : item.status)}</StatusBadge>,
              formatDateTime(item.created_at),
              <div className="admin-dashboard-actions">
                <button type="button" onClick={() => viewOrder(item)}>详情</button>
                {item.status === "pending" && <button type="button" className="warning" disabled={actionLoading === `cancel-order-${item.id}`} onClick={() => cancelOrder(item)}>取消</button>}
                {item.status === "paid" && item.refund_status !== "refunded" && <button type="button" className="danger" disabled={actionLoading === `refund-order-${item.id}`} onClick={() => refundOrder(item)}>退款</button>}
              </div>,
            ])}
          />
        ) : (
          <EmptyState title="暂无订单记录" description="当前没有符合条件的订单。" />
        )}
        <div className="admin-dashboard-toolbar" style={{ justifyContent: "space-between" }}>
          <span style={{ color: "#64748b" }}>共 {total} 笔订单 · 第 {orderPage} / {totalPages} 页</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select value={orderPageSize} onChange={(e) => { setOrderPageSize(Number(e.target.value)); setOrderPage(1); }}>
              <option value={20}>每页 20</option>
              <option value={50}>每页 50</option>
              <option value={100}>每页 100</option>
            </select>
            <button type="button" disabled={orderPage <= 1} onClick={() => setOrderPage((p) => p - 1)}>上一页</button>
            <button type="button" disabled={orderPage >= totalPages} onClick={() => setOrderPage((p) => p + 1)}>下一页</button>
          </div>
        </div>
        {orderDetail && (
          <div className="admin-dashboard-modal-backdrop" role="presentation" onClick={() => setOrderDetail(null)}>
            <div className="admin-dashboard-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
              <div className="admin-dashboard-modal-head">
                <h3>订单详情 #{orderDetail.id}</h3>
                <button type="button" onClick={() => setOrderDetail(null)}>×</button>
              </div>
              {orderDetail.is_mock && <div className="admin-dashboard-error" style={{ margin: "8px 0" }}>模拟支付订单，仅用于当前测试流程，不代表真实商业收款。</div>}
              <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>订单信息</h2></div>
              <DataTable columns={["字段", "值"]} rows={[
                ["订单号", orderDetail.order_no || "（历史订单无编号）"],
                ["用户", `${orderDetail.nickname || orderDetail.username}（ID ${orderDetail.user_id}）`],
                ["业务方向", zhServiceKey(orderDetail.service_key)],
                ["套餐", zhPlan(orderDetail.target_plan)],
                ["创建时间", formatDateTime(orderDetail.created_at)],
                ["订单状态", zhOrderStatus(orderDetail.status)],
              ]} />
              <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>支付信息</h2></div>
              <DataTable columns={["字段", "值"]} rows={[
                ["支付方式", orderDetail.is_mock ? "模拟支付" : zhProvider(orderDetail.payment_provider)],
                ["标价", orderDetail.list_price_yuan != null ? `¥${formatNumber(orderDetail.list_price_yuan, 2)}` : "—"],
                ["实付金额", orderDetail.paid_amount_yuan != null ? `¥${formatNumber(orderDetail.paid_amount_yuan, 2)}` : "—"],
                ["支付时间", formatDateTime(orderDetail.paid_at)],
                ["退款状态", orderDetail.refund_status ? zhOrderStatus(orderDetail.refund_status) : "—"],
              ]} />
              <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>权益授予</h2></div>
              <DataTable columns={["字段", "值"]} rows={[
                ["是否生成 MembershipGrant", orderDetail.grant?.granted ? "已授予" : "未生成"],
                ["授予方向", orderDetail.grant?.granted ? zhServiceKey(orderDetail.service_key) : "—"],
                ["授予套餐", orderDetail.grant?.granted ? zhPlan(orderDetail.grant.new_plan) : "—"],
                ["权益有效期", orderDetail.grant?.granted ? formatDateTime(orderDetail.grant.new_expiry) : formatDateTime(orderDetail.membership_expires_at)],
              ]} />
            </div>
          </div>
        )}
      </AdminPageCard>
    );
  };

  const renderRedemptionCodes = () => {
    const planOptions = redemptionForm.service_key === "exam_11408"
      ? [["monthly_sprint", "月度冲刺包"], ["quarterly_boost", "季度强化包"], ["full_exam", "全程备考包"]]
      : redemptionForm.service_key === "programming"
        ? [["monthly", "编程进阶月卡"], ["quarterly", "实验与算法强化季卡"], ["full", "编程全能年卡"]]
        : [["monthly", "月度学习包"], ["quarterly", "季度学习包"], ["full", "全程学习包"]];
    const updateForm = (key, value) => setRedemptionForm((prev) => ({ ...prev, [key]: value }));
    const createCodes = async () => {
      setActionError("");
      setActionSuccess("");
      try {
        const data = await getJson(`${API_BASE}/admin/membership/redemption-codes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...redemptionForm, membership_duration_days: Number(redemptionForm.membership_duration_days), max_redemptions: Number(redemptionForm.max_redemptions), count: Number(redemptionForm.count), code_expires_at: new Date(redemptionForm.code_expires_at).toISOString() }),
        });
        setCreatedRedemptionCodes(data.codes || []);
        setActionSuccess("兑换码创建成功；明文仅在本次显示，请立即保存。");
        await loadCurrentPage();
      } catch (err) {
        setActionError(err.message || "创建兑换码失败");
      }
    };
    const revokeCode = async (id) => {
      if (!window.confirm("确认撤销该兑换码吗？已使用的码不能撤销。")) return;
      try {
        await getJson(`${API_BASE}/admin/membership/redemption-codes/${id}/revoke`, { method: "POST" });
        await loadCurrentPage();
      } catch (err) {
        setActionError(err.message || "撤销兑换码失败");
      }
    };
    const viewCode = async (id) => {
      try {
        setRedemptionDetail(await getJson(`${API_BASE}/admin/membership/redemption-codes/${id}`));
      } catch (err) {
        setActionError(err.message || "加载兑换码明细失败");
      }
    };
    return (
      <AdminPageCard title="兑换码管理" subtitle="创建方向绑定的会员兑换码；兑换码不产生订单或收入记录。">
        {actionError && <div className="admin-dashboard-error">{actionError}</div>}
        {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
        <div className="admin-dashboard-toolbar">
          <select value={redemptionStatus} onChange={(e) => setRedemptionStatus(e.target.value)}>
            <option value="all">全部</option><option value="active">有效</option><option value="exhausted">已用完</option><option value="expired">已过期</option><option value="revoked">已撤销</option>
          </select>
        </div>
        {isSuperAdmin && (
          <div className="admin-dashboard-form-grid">
            <label>服务方向<select value={redemptionForm.service_key} onChange={(e) => { updateForm("service_key", e.target.value); updateForm("target_plan", e.target.value === "exam_11408" ? "monthly_sprint" : "monthly"); }}><option value="exam_11408">11408 考研</option><option value="course_learning">课程学习</option><option value="programming">编程学习</option></select></label>
            <label>目标套餐<select value={redemptionForm.target_plan} onChange={(e) => updateForm("target_plan", e.target.value)}>{planOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label>会员时长（天）<input type="number" min="1" max="3650" value={redemptionForm.membership_duration_days} onChange={(e) => updateForm("membership_duration_days", e.target.value)} /></label>
            <label>兑换码有效期<input type="datetime-local" value={redemptionForm.code_expires_at} onChange={(e) => updateForm("code_expires_at", e.target.value)} /></label>
            <label>每码最大兑换次数<input type="number" min="1" max="100000" value={redemptionForm.max_redemptions} onChange={(e) => updateForm("max_redemptions", e.target.value)} /></label>
            <label>创建数量<input type="number" min="1" max="100" value={redemptionForm.count} onChange={(e) => updateForm("count", e.target.value)} /></label>
            <label>备注<input value={redemptionForm.note} onChange={(e) => updateForm("note", e.target.value)} /></label>
            <button type="button" className="admin-dashboard-primary-action" onClick={createCodes}>创建兑换码</button>
          </div>
        )}
        {createdRedemptionCodes.length > 0 && <div className="admin-dashboard-success" style={{ marginTop: 16 }}><strong>本次新建明文（离开页面后不再展示）：</strong>{createdRedemptionCodes.map((item) => <div key={item.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 6 }}><code>{item.code}</code><button type="button" onClick={() => navigator.clipboard?.writeText(item.code)}>复制</button></div>)}</div>}
        {redemptionDetail && <div className="admin-dashboard-card" style={{ margin: "16px 0" }}><div className="admin-dashboard-card-head"><h2>兑换码使用明细</h2><button type="button" onClick={() => setRedemptionDetail(null)}>关闭</button></div><p>{redemptionDetail.code?.service_key} / {redemptionDetail.code?.target_plan} · {redemptionDetail.code?.redeemed_count}/{redemptionDetail.code?.max_redemptions}</p>{(redemptionDetail.usage || []).length ? <DataTable columns={["用户", "兑换时间"]} rows={redemptionDetail.usage.map((row) => [row.username || row.user_id, formatDateTime(row.redeemed_at)])} /> : <EmptyState title="暂无兑换记录" description="该兑换码尚未被使用。" />}</div>}
        <DataTable columns={["服务方向", "目标套餐", "会员时长", "有效期", "使用情况", "状态", "操作"]} rows={redemptionCodes.map((item) => [
          zhServiceKey(item.service_key), zhPlan(item.target_plan), `${item.membership_duration_days || 0} 天`, formatDateTime(item.code_expires_at), `${item.redeemed_count}/${item.max_redemptions}`, zhStatus(item.status),
          <div className="admin-dashboard-actions"><button type="button" onClick={() => viewCode(item.id)}>查看</button><button type="button" className="warning" disabled={item.status !== "active"} onClick={() => revokeCode(item.id)}>撤销</button></div>,
        ])} />
      </AdminPageCard>
    );
  };

  const renderMembers = () => (
    <AdminPageCard title="会员管理" subtitle="管理用户会员、套餐和有效期。">
      <div className="admin-dashboard-toolbar">
        <input
          value={memberKeyword}
          placeholder="按用户 ID / 用户名 / 昵称搜索"
          onChange={(e) => setMemberKeyword(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") loadCurrentPage(); }}
        />
        <button type="button" onClick={loadCurrentPage}>搜索</button>
        <button type="button" onClick={() => { setMemberKeyword(""); setTimeout(loadCurrentPage, 0); }}>重置</button>
      </div>
      {memberUsers.length > 0 ? (
        <DataTable
          columns={["用户", "11408", "课程学习", "编程", "操作"]}
          rows={memberUsers.map((item) => [
            <>{item.nickname || item.username}<small style={{ display: "block", color: "#64748b" }}>ID {item.user_id}</small></>,
            membershipCell(item.memberships.exam_11408),
            membershipCell(item.memberships.course_learning),
            membershipCell(item.memberships.programming),
            <button type="button" onClick={() => openMembershipEditor(item)}>管理</button>,
          ])}
        />
      ) : (
        <EmptyState title="暂无会员数据" description="调整筛选条件后重试。" />
      )}
      {editingMemberUser && <MembershipEditModal user={editingMemberUser} form={membershipForm} onChange={setMembershipForm} onSave={saveMemberships} onClose={() => setEditingMemberUser(null)} loading={actionLoading === "membership"} catalog={membershipCatalog} />}
    </AdminPageCard>
  );

  const quotaUnitLabel = (q) => {
    if (q.period === "每天") return `${q.unit} / 每天`;
    if (q.period === "单文件") return `${q.unit} / 单文件`;
    if (q.period === "总容量") return `${q.unit} / 总容量`;
    return q.unit || "";
  };

  const quotaValueLabel = (value, unit, digits = 0) => {
    if (value == null) return "—";
    const suffix = unit === "次" ? " 次" : ` ${unit}`;
    return `${formatNumber(value, digits)}${suffix}`;
  };

  const quotaPlanBadge = (sk, plan) => {
    const labels = { exam_11408: "11408", course_learning: "课程学习", programming: "编程" };
    const planLabels = { free: "免费", monthly: "月度", quarterly: "季度", full: "全程", monthly_sprint: "月度冲刺", quarterly_boost: "季度强化", full_exam: "全程考包" };
    return (
      <span className="adm-membership-badge" title={labels[sk] || sk}>
        {planLabels[plan] || plan || "free"}
      </span>
    );
  };

  const quotaOverrideModal = quotaOverrideTarget ? (
    <div className="admin-dashboard-modal-backdrop" role="presentation">
      <div className="admin-dashboard-modal" role="dialog" aria-modal="true">
        <div className="admin-dashboard-modal-head">
          <h3>设置额度覆盖</h3>
          <button type="button" onClick={() => setQuotaOverrideTarget(null)}>×</button>
        </div>
        {quotaOverrideError && <div className="admin-dashboard-error admin-dashboard-modal-error">{quotaOverrideError}</div>}
        <label>
          覆盖对象
          <input value={`${quotaOverrideTarget.service_key} · ${quotaOverrideTarget.label}`} disabled />
        </label>
        <label>
          覆盖额度（0 表示该额度归零）
          <input type="number" min="0" step="1" value={quotaOverrideValue}
            onChange={(e) => setQuotaOverrideValue(e.target.value)} />
        </label>
        <div className="admin-dashboard-modal-actions">
          <button type="button" onClick={() => setQuotaOverrideTarget(null)}>取消</button>
          <button type="button" className="admin-dashboard-primary-action"
            disabled={actionLoading === "quota-override"} onClick={saveQuotaOverride}>
            {actionLoading === "quota-override" ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  ) : null;

  const renderQuota = () => {
    if (quotaDetail) {
      return (
        <AdminPageCard
          title="额度管理"
          subtitle={`${quotaDetail.nickname || quotaDetail.username}（ID ${quotaDetail.user_id}）的三方向额度明细`}
          action={<button type="button" onClick={() => { setQuotaDetail(null); setQuotaOverrideTarget(null); }}>← 返回用户列表</button>}
        >
          {actionError && <div className="admin-dashboard-error">{actionError}</div>}
          {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
          {(quotaDetail.services || []).map((svc) => (
            <div key={svc.service_key} className="admin-dashboard-card-head admin-dashboard-inner-head">
              <h2>{svc.service_label} · 当前套餐：{svc.plan_label || svc.plan}</h2>
              <div className="admin-dashboard-table-wrap" style={{ marginTop: 8 }}>
                <table className="admin-dashboard-table">
                  <thead>
                    <tr>{["额度项", "套餐默认", "用户覆盖", "生效额度", "已用", "剩余", "单位 / 周期", "操作"].map((c) => <th key={c}>{c}</th>)}</tr>
                  </thead>
                  <tbody>
                    {(svc.quotas || []).map((q) => {
                      const isMb = q.unit === "MB";
                      const digits = isMb ? 2 : 0;
                      return (
                        <tr key={q.quota_key}>
                          <td>
                            <strong>{q.label}</strong>
                            <small style={{ display: "block", color: "#64748b" }}>{q.quota_key}</small>
                          </td>
                          <td>{quotaValueLabel(q.default_limit, q.unit, digits)}</td>
                          <td>
                            {q.has_override ? (
                              <><StatusBadge tone="ok">覆盖中</StatusBadge><small style={{ display: "block" }}>{quotaValueLabel(q.override_limit, q.unit, digits)}</small></>
                            ) : "—"}
                          </td>
                          <td><strong>{quotaValueLabel(q.effective_limit, q.unit, digits)}</strong></td>
                          <td>{quotaValueLabel(q.used, q.unit, digits)}</td>
                          <td>{quotaValueLabel(q.remaining, q.unit, digits)}</td>
                          <td>{quotaUnitLabel(q)}</td>
                          <td>
                            <div className="admin-dashboard-actions">
                              <button type="button" disabled={!!actionLoading}
                                onClick={() => openQuotaOverride(svc.service_key, q)}>
                                {q.has_override ? "修改" : "设置"}
                              </button>
                              {q.has_override && (
                                <button type="button" className="danger"
                                  disabled={actionLoading === `del-${svc.service_key}-${q.quota_key}`}
                                  onClick={() => deleteQuotaOverride(svc.service_key, q.quota_key)}>
                                  删除
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {quotaOverrideModal}
        </AdminPageCard>
      );
    }

    return (
      <AdminPageCard title="额度管理" subtitle="按用户 → 业务方向 → 额度 查看并设置个性化覆盖。">
        <div className="admin-dashboard-toolbar">
          <input
            value={quotaKeyword}
            placeholder="按用户 ID / 用户名 / 昵称搜索"
            onChange={(e) => setQuotaKeyword(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") loadCurrentPage(); }}
          />
          <button type="button" onClick={loadCurrentPage}>搜索</button>
          <button type="button" onClick={() => { setQuotaKeyword(""); setTimeout(loadCurrentPage, 0); }}>重置</button>
        </div>
        {actionError && <div className="admin-dashboard-error">{actionError}</div>}
        {(quota?.items || []).length > 0 ? (
          <DataTable
            columns={["用户", "11408", "课程学习", "编程", "操作"]}
            rows={quota.items.map((item) => [
              <>{item.nickname || item.username}<small style={{ display: "block", color: "#64748b" }}>ID {item.user_id}</small></>,
              quotaPlanBadge("exam_11408", item.memberships?.exam_11408),
              quotaPlanBadge("course_learning", item.memberships?.course_learning),
              quotaPlanBadge("programming", item.memberships?.programming),
              <button type="button" onClick={() => loadQuotaDetail(item)}>查看额度</button>,
            ])}
          />
        ) : (
          <EmptyState title="暂无额度数据" description="调整筛选条件后重试。" />
        )}
        {quotaOverrideModal}
      </AdminPageCard>
    );
  };

  const fmtBytes = (bytes) => {
    const b = Number(bytes || 0);
    if (b < 1024 * 1024) return `${formatNumber(b / 1024, 1)} KB`;
    if (b < 1024 * 1024 * 1024) return `${formatNumber(b / 1024 / 1024, 1)} MB`;
    return `${formatNumber(b / 1024 / 1024 / 1024, 2)} GB`;
  };
  const DOMAIN_LABELS = { exam_11408: "11408 考研", course_learning: "课程学习", programming: "编程学习", legacy: "历史未归属" };
  const TICKET_LABELS = { pending: "待处理", in_progress: "处理中", waiting_confirmation: "等待用户确认", resolved: "已解决", closed: "已关闭" };

  const renderStatistics = () => {
    const s = statisticsData || {};
    const users = s.users || {};
    const memberships = s.memberships || {};
    const materials = s.materials || {};
    const tickets = s.tickets || {};
    const orders = s.orders || {};
    return (
      <AdminPageCard title="数据统计" subtitle="平台业务运营数据（用户 / 会员 / 资料 / 客服 / 模拟订单）。">
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>用户</h2></div>
        <div className="admin-dashboard-mini-stats">
          <div><span>普通用户总数</span><strong>{formatNumber(users.total)}</strong></div>
          <div><span>正常用户</span><strong>{formatNumber(users.active)}</strong></div>
          <div><span>封禁用户</span><strong>{formatNumber(users.banned)}</strong></div>
          <div><span>近 7 天新增</span><strong>{formatNumber(users.new_7_days)}</strong></div>
          <div><span>近 30 天新增</span><strong>{formatNumber(users.new_30_days)}</strong></div>
        </div>
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>有效付费会员</h2></div>
        <div className="admin-dashboard-mini-stats">
          <div><span>去重付费用户</span><strong>{formatNumber(memberships.paid_users)}</strong></div>
          <div><span>11408 会员</span><strong>{formatNumber(memberships.directions?.exam_11408)}</strong></div>
          <div><span>课程学习会员</span><strong>{formatNumber(memberships.directions?.course_learning)}</strong></div>
          <div><span>编程学习会员</span><strong>{formatNumber(memberships.directions?.programming)}</strong></div>
        </div>
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>资料</h2></div>
        <DataTable
          columns={["业务方向", "文件数量", "总容量"]}
          rows={["exam_11408", "course_learning", "programming", "legacy"].map((d) => [DOMAIN_LABELS[d] || d, formatNumber(materials[d]?.count), fmtBytes(materials[d]?.bytes)])}
        />
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>客服工单</h2></div>
        <div className="admin-dashboard-mini-stats">
          {["pending", "in_progress", "waiting_confirmation", "resolved", "closed"].map((st) => (
            <div key={st}><span>{TICKET_LABELS[st] || st}</span><strong>{formatNumber(tickets[st])}</strong></div>
          ))}
        </div>
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>模拟订单</h2></div>
        <div className="admin-dashboard-mini-stats">
          <div><span>订单总数</span><strong>{formatNumber(orders.total)}</strong></div>
          <div><span>已支付</span><strong>{formatNumber(orders.paid)}</strong></div>
          <div><span>已取消</span><strong>{formatNumber(orders.cancelled)}</strong></div>
          <div><span>已退款</span><strong>{formatNumber(orders.refunded)}</strong></div>
        </div>
        <p style={{ color: "#64748b", fontSize: 13, marginTop: 8 }}>当前全部为模拟支付订单，不代表真实商业收款。</p>
      </AdminPageCard>
    );
  };

  const renderUsage = () => {
    const featureStats = usageSummary?.feature_stats || {};
    const ranking = Object.entries(featureStats)
      .map(([feature, count]) => ({ feature, count }))
      .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
    const serviceStats = usageSummary?.service_stats || {};
    const SERVICE_OPTIONS = [
      ["", "全部"],
      ["exam_11408", "11408 考研"],
      ["course_learning", "课程学习"],
      ["programming", "编程学习"],
      ["unknown", "历史未归属"],
    ];
    const SERVICE_DIRECTIONS = ["exam_11408", "course_learning", "programming", "unknown"];
    const SERVICE_DIRECTION_LABELS = { exam_11408: "11408 考研", course_learning: "课程学习", programming: "编程学习", unknown: "历史未归属" };
    return (
      <AdminPageCard title="AI 用量统计" subtitle="按业务方向与功能统计 AI 调用（成功 / 失败 / 趋势）。">
        <div className="admin-dashboard-toolbar">
          <select value={aiServiceFilter} onChange={(e) => setAiServiceFilter(e.target.value)}>
            {SERVICE_OPTIONS.map(([v, l]) => <option key={v || "all"} value={v}>{l}</option>)}
          </select>
          <select value={aiTrendDays} onChange={(e) => setAiTrendDays(Number(e.target.value))}>
            <option value={7}>近 7 天</option>
            <option value={30}>近 30 天</option>
          </select>
        </div>
        <div className="admin-dashboard-mini-stats">
          <div><span>总调用</span><strong>{formatNumber(usageSummary?.total_calls_all)}</strong></div>
          <div><span>成功调用</span><strong>{formatNumber(usageSummary?.total_success)}</strong></div>
          <div><span>失败调用</span><strong>{formatNumber(usageSummary?.total_failed)}</strong></div>
          <div><span>累计 Token</span><strong>{formatNumber(usageSummary?.total_tokens_all)}</strong></div>
        </div>
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>业务方向统计</h2></div>
        <DataTable
          columns={["业务方向", "成功", "失败"]}
          rows={SERVICE_DIRECTIONS.map((d) => [SERVICE_DIRECTION_LABELS[d] || d, formatNumber(serviceStats[d]?.success), formatNumber(serviceStats[d]?.failed)])}
        />
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>调用趋势</h2></div>
        <TrendChart data={(usageTrend?.items || []).map((item) => ({ date: item.date?.slice(5), count: item.count }))} emptyDescription="该时间范围暂无数据" />
        <div className="admin-dashboard-card-head admin-dashboard-inner-head"><h2>功能排行</h2></div>
        {ranking.length > 0 ? (
          <DataTable columns={["功能", "调用次数"]} rows={ranking.map((item) => [zhFeature(item.feature), formatNumber(item.count)])} />
        ) : (
          <EmptyState title="暂无 AI 用量排行" description="产生 AI 调用后会展示功能使用排行。" />
        )}
      </AdminPageCard>
    );
  };

  const renderSettings = () => {
    const items = settings || [];
    const categories = [...new Set(items.map((i) => i.category || "其他"))];
    const isDirty = Object.keys(settingsDraft).length > 0;
    const toggleSetting = (key, currentValue) => {
      setSettingsDraft((prev) => ({ ...prev, [key]: currentValue === "true" ? "false" : "true" }));
    };
    const saveSettings = async () => {
      setSettingsSaving(true);
      setActionError("");
      setActionSuccess("");
      try {
        await getJson(`${API_BASE}/admin/settings`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ updates: settingsDraft }),
        });
        setSettingsDraft({});
        setActionSuccess("保存成功");
        await loadCurrentPage();
      } catch (err) {
        setActionError(err.message || "保存失败");
      } finally {
        setSettingsSaving(false);
      }
    };
    return (
      <AdminPageCard title="系统设置" subtitle="管理平台功能开关，保存后立即生效。">
        {actionError && <div className="admin-dashboard-error">{actionError}</div>}
        {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
        {isDirty && (
          <div className="admin-dashboard-toolbar" style={{ background: "#f5f3ff", borderRadius: 8, padding: 8 }}>
            <span>有未保存的修改</span>
            <button type="button" disabled={settingsSaving} onClick={saveSettings}>{settingsSaving ? "保存中..." : "保存修改"}</button>
            <button type="button" onClick={() => { setSettingsDraft({}); loadCurrentPage(); }}>取消</button>
          </div>
        )}
        {items.length > 0 ? (
          categories.map((cat) => (
            <div key={cat} className="admin-dashboard-card-head admin-dashboard-inner-head">
              <h2>{cat}</h2>
              <div className="admin-dashboard-table-wrap" style={{ marginTop: 8 }}>
                <table className="admin-dashboard-table">
                  <thead><tr>{["配置项", "说明", "当前状态", "更新时间"].map((c) => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {items.filter((i) => (i.category || "其他") === cat).map((item) => {
                      const val = settingsDraft[item.key] ?? item.value;
                      const enabled = val === "true";
                      return (
                        <tr key={item.key}>
                          <td><strong>{item.label || item.key}</strong><small style={{ display: "block", color: "#64748b" }}>{item.key}</small></td>
                          <td>{item.description || "-"}</td>
                          <td>
                            <label className="adm-toggle">
                              <input type="checkbox" checked={enabled} onChange={() => toggleSetting(item.key, val)} />
                              <span className="adm-toggle-slider" />
                              <span className="adm-toggle-label">{enabled ? "已开启" : "已关闭"}</span>
                            </label>
                          </td>
                          <td>{formatDateTime(item.updated_at)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        ) : (
          <EmptyState title="暂无设置项" description="系统设置初始化后会展示在这里。" />
        )}
      </AdminPageCard>
    );
  };

  const renderLogs = () => {
    const total = logs?.total || 0;
    const totalPages = logs?.total_pages || Math.max(1, Math.ceil(total / logPageSize));
    return (
      <AdminPageCard title="操作日志" subtitle="查看管理员操作审计记录。">
        <div className="admin-dashboard-toolbar">
          {isSuperAdmin && (
            <input value={logActor} placeholder="按管理员用户名筛选" onChange={(e) => setLogActor(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { setLogPage(1); loadCurrentPage(); } }} />
          )}
          <input value={logAction} placeholder="按动作类型筛选" onChange={(e) => setLogAction(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { setLogPage(1); loadCurrentPage(); } }} />
          <button type="button" onClick={() => { setLogPage(1); loadCurrentPage(); }}>查询</button>
          <button type="button" onClick={() => { setLogActor(""); setLogAction(""); setLogPage(1); setTimeout(loadCurrentPage, 0); }}>重置</button>
        </div>
        {(logs?.items || []).length > 0 ? (
          <DataTable
            columns={["管理员", "动作", "目标", "结果", "时间", "IP", "操作"]}
            rows={logs.items.map((item) => [
              item.admin_username || "-",
              zhAction(item.action),
              item.target_username || item.target_id || item.target_type || "-",
              <StatusBadge tone={item.result === "success" ? "ok" : "danger"}>{zhStatus(item.result) || item.result || "-"}</StatusBadge>,
              formatDateTime(item.created_at),
              item.ip || "-",
              <button type="button" onClick={() => setLogDetail(item)}>详情</button>,
            ])}
          />
        ) : (
          <EmptyState title="暂无操作日志" description="产生管理员操作记录后会展示在这里。" />
        )}
        <div className="admin-dashboard-toolbar" style={{ justifyContent: "space-between" }}>
          <span style={{ color: "#64748b" }}>共 {total} 条 · 第 {logPage} / {totalPages} 页</span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select value={logPageSize} onChange={(e) => { setLogPageSize(Number(e.target.value)); setLogPage(1); }}>
              <option value={20}>每页 20</option>
              <option value={50}>每页 50</option>
              <option value={100}>每页 100</option>
            </select>
            <button type="button" disabled={logPage <= 1} onClick={() => setLogPage((p) => p - 1)}>上一页</button>
            <button type="button" disabled={logPage >= totalPages} onClick={() => setLogPage((p) => p + 1)}>下一页</button>
          </div>
        </div>
        {logDetail && (
          <div className="admin-dashboard-modal-backdrop" role="presentation" onClick={() => setLogDetail(null)}>
            <div className="admin-dashboard-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
              <div className="admin-dashboard-modal-head">
                <h3>操作日志详情</h3>
                <button type="button" onClick={() => setLogDetail(null)}>×</button>
              </div>
              <DataTable
                columns={["字段", "值"]}
                rows={[
                  ["管理员", logDetail.admin_username || "-"],
                  ["操作", zhAction(logDetail.action)],
                  ["目标", logDetail.target_username || logDetail.target_id || logDetail.target_type || "-"],
                  ["结果", zhStatus(logDetail.result) || logDetail.result || "-"],
                  ["时间", formatDateTime(logDetail.created_at)],
                  ["IP", logDetail.ip || "-"],
                  ...logDetailRows(logDetail),
                ]}
              />
            </div>
          </div>
        )}
      </AdminPageCard>
    );
  };

  const renderAdmins = () => (
    <AdminPageCard title="管理员管理" subtitle="管理管理员账号（仅超级管理员可见）。">
      <div className="admin-dashboard-toolbar">
        <input value={adminKeyword} placeholder="按用户名 / 昵称搜索" onChange={(e) => setAdminKeyword(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") loadCurrentPage(); }} />
        <button type="button" onClick={loadCurrentPage}>搜索</button>
        <button type="button" onClick={() => { setAdminKeyword(""); setTimeout(loadCurrentPage, 0); }}>重置</button>
        <button type="button" className="admin-dashboard-primary-action" style={{ marginLeft: "auto" }} onClick={() => { setAdminCreateError(""); setShowAdminCreate(true); }}>新增普通管理员</button>
      </div>
      {actionError && <div className="admin-dashboard-error">{actionError}</div>}
      {actionSuccess && <div className="admin-dashboard-success">{actionSuccess}</div>}
      {(adminsData?.items || []).length > 0 ? (
        <DataTable
          columns={["用户名", "昵称", "角色", "状态", "最近登录", "创建时间", "操作"]}
          rows={adminsData.items.map((item) => [
            item.username,
            item.nickname || "-",
            <StatusBadge tone={item.admin_role === "super_admin" ? "ok" : "muted"}>{item.admin_role_label || zhRole(item.admin_role)}</StatusBadge>,
            item.is_active ? <StatusBadge tone="ok">正常</StatusBadge> : <StatusBadge tone="danger">已停用</StatusBadge>,
            formatDateTime(item.last_login_at),
            formatDateTime(item.created_at),
            item.is_builtin_admin ? <span style={{ color: "#94a3b8" }}>内置</span> : (
              <button type="button" disabled={actionLoading === `admin-status-${item.user_id}`} onClick={() => toggleAdminStatus(item)}>{item.is_active ? "停用" : "启用"}</button>
            ),
          ])}
        />
      ) : (
        <EmptyState title="暂无管理员数据" description="暂无其他管理员账号。" />
      )}
      {showAdminCreate && (
        <div className="admin-dashboard-modal-backdrop" role="presentation" onClick={() => setShowAdminCreate(false)}>
          <div className="admin-dashboard-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <div className="admin-dashboard-modal-head">
              <h3>新增普通管理员</h3>
              <button type="button" onClick={() => setShowAdminCreate(false)}>×</button>
            </div>
            {adminCreateError && <div className="admin-dashboard-error admin-dashboard-modal-error">{adminCreateError}</div>}
            <label>管理员用户名<input value={adminCreateForm.username} onChange={(e) => setAdminCreateForm((p) => ({ ...p, username: e.target.value }))} /></label>
            <label>初始密码<input type="password" value={adminCreateForm.password} onChange={(e) => setAdminCreateForm((p) => ({ ...p, password: e.target.value }))} /></label>
            <label>确认密码<input type="password" value={adminCreateForm.confirm_password} onChange={(e) => setAdminCreateForm((p) => ({ ...p, confirm_password: e.target.value }))} /></label>
            <label>昵称（可选）<input value={adminCreateForm.nickname} onChange={(e) => setAdminCreateForm((p) => ({ ...p, nickname: e.target.value }))} /></label>
            <div className="admin-dashboard-modal-actions">
              <button type="button" onClick={() => setShowAdminCreate(false)}>取消</button>
              <button type="button" className="admin-dashboard-primary-action" disabled={actionLoading === "admin-create"} onClick={createAdmin}>
                {actionLoading === "admin-create" ? "创建中..." : "创建"}
              </button>
            </div>
          </div>
        </div>
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
      const newAvatarUrl = data.profile?.avatar_url || data.avatar_url || null;
      setUserAvatarUrl(resolveMediaUrl(newAvatarUrl, API_BASE) || null);
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
    setUserAvatarUrl(resolveMediaUrl(user?.avatar_url, API_BASE) || null);
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
    if (activePage === "adminFeedback") {
      return <AdminSupportCenter user={user} onUnreadCountChange={setSupportUnreadCount} />;
    }
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
    if (activePage === "adminRedemptionCodes") return renderRedemptionCodes();
    if (activePage === "adminMembers") return renderMembers();
    if (activePage === "adminQuota") return renderQuota();
    if (activePage === "adminStatistics") return renderStatistics();
    if (activePage === "adminUsage") return renderUsage();
    if (activePage === "adminSettings") return renderSettings();
    if (activePage === "adminLogs") return renderLogs();
    if (activePage === "adminAdmins") return renderAdmins();
    if (activePage === "adminProfile") return renderProfile();
    return renderDashboard();
  };

  return (
    <div className="admin-dashboard-shell">
      <aside className="admin-dashboard-sidebar">
        <div className="admin-dashboard-brand">
          <span className="admin-dashboard-logo">AI</span>
          <div>
            <strong>智学AI 管理平台</strong>
            <span>管理员</span>
          </div>
        </div>
        <nav className="admin-dashboard-nav" aria-label="管理员功能导航">
          {MENU_GROUPS.map((group) => (
            <div className="admin-dashboard-nav-group" key={group.title}>
              <p>{group.title}</p>
              {group.items.filter((item) => item.page !== "adminAdmins" || isSuperAdmin).map((item) => (
                <button
                  key={item.page}
                  className={`admin-dashboard-nav-item${activePage === item.page ? " active" : ""}`}
                  type="button"
                  onClick={() => navigate(item.page)}
                >
                  <span>{item.icon}</span>
                  {item.label}
                  {item.page === "adminFeedback" && supportUnreadCount > 0 && (
                    <span style={{ marginLeft: "auto", background: "#ef4444", color: "#fff", borderRadius: 999, fontSize: 11, padding: "1px 7px", fontWeight: 700 }}>
                      {supportUnreadCount}
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>

      <main className="admin-dashboard-main">
        <header className="admin-dashboard-header">
          <button className="admin-dashboard-profile" type="button" onClick={() => navigate("adminProfile")} style={{ marginLeft: "auto" }}>
            <span className="admin-dashboard-avatar">管</span>
            <strong>{adminRoleLabel}</strong>
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

function UsersTable({ rows, hideActions = false, onBan, onUnban, onDelete, onEditMembership, actionLoading = "", selectable = false, selectedUsers = [], allSelected = false, onToggleSelect, onToggleSelectAll }) {
  if (!rows || rows.length === 0) {
    return <EmptyState title="暂无用户数据" description="当前没有可展示的用户记录。" />;
  }
  const columns = [];
  if (selectable) columns.push(<input type="checkbox" checked={allSelected} onChange={onToggleSelectAll} aria-label="全选当前页" />);
  columns.push("用户昵称", "用户ID", "账号", "三方向会员", "注册时间", "学习时长", "状态");
  if (!hideActions) columns.push("操作");

  const M_BADGE = (m, sk) => {
    const mb = (m && m[sk]) || {};
    const enabled = Boolean(mb.current_is_effective);
    const label = enabled ? (mb.plan_label || zhPlan(mb.plan)) : (mb.plan === "free" ? "免费" : (mb.is_expired ? "已过期" : "未开通"));
    return (
      <span key={sk} className={`adm-membership-badge${enabled ? "" : " disabled"}`}
        title={zhServiceKey(sk)}>
        {sk === "exam_11408" ? "📘" : sk === "course_learning" ? "📗" : "📙"} {label}
      </span>
    );
  };

  const tableRows = rows.map((item) => {
    const isBanned = Boolean(item.is_banned);
    const isAdmin = Boolean(item.is_admin) || (item.admin_role && item.admin_role !== "none");
    const uid = item.user_id || item.id;
    const m = item.memberships || {};
    const status = isBanned ? <StatusBadge tone="danger">已封禁</StatusBadge> : <StatusBadge tone="ok">正常</StatusBadge>;
    const membershipCell = (
      <div className="adm-membership-cell">
        {M_BADGE(m, "exam_11408")}
        {M_BADGE(m, "course_learning")}
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
        {onDelete && <button type="button" className="danger" disabled={!!actionLoading || isAdmin} onClick={() => onDelete(item)}>删除</button>}
      </div>
    );
    const base = [];
    if (selectable) base.push(<input type="checkbox" checked={selectedUsers.includes(uid)} onChange={() => onToggleSelect(uid)} aria-label={`选择用户 ${uid}`} />);
    base.push(
      <><span className="admin-dashboard-user-avatar">U</span>{displayUserName(item)}</>,
      uid || "-",
      item.username || "-",
      membershipCell,
      formatDateTime(item.register_time || item.created_at),
      `${formatNumber(item.learning_hours, 1)} 小时`,
      status,
    );
    if (!hideActions) base.push(actions);
    return base;
  });
  return <DataTable columns={columns} rows={tableRows} />;
}

function MembershipEditModal({ user: targetUser, form, onChange, onSave, onClose, loading, catalog = [] }) {
  const SERVICE_KEYS = ["exam_11408", "course_learning", "programming"];
  const SERVICE_INFO = {
    exam_11408: { name: "11408 考研", icon: "📘" }, course_learning: { name: "课程学习", icon: "📗" }, programming: { name: "编程能力提升", icon: "📙" },
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
            const plans = catalog.find((item) => item.service_key === sk)?.plans || [];
            return (
              <div key={sk} className={`adm-membership-card${f.is_enabled ? "" : " disabled"}`}>
                <div className="adm-membership-card-head">
                  <span>{info.icon} <strong>{info.name}</strong></span>
                  <label className="adm-toggle">
                    <input type="checkbox" checked={f.is_enabled}
                      onChange={(e) => onChange((prev) => ({ ...prev, [sk]: { ...prev[sk], is_enabled: e.target.checked, status: e.target.checked ? "active" : "disabled" } }))} disabled={loading} />
                    <span className="adm-toggle-slider" />
                    <span className="adm-toggle-label">{f.is_enabled ? "已开通" : "未开通"}</span>
                  </label>
                </div>
                {f.is_enabled ? (
                  <div className="adm-membership-card-body">
                    <label>会员等级</label>
                    <select value={f.plan} onChange={(e) => updateField(sk, "plan", e.target.value)} disabled={loading}>
                      {plans.map((item) => (
                        <option key={item.plan_code} value={item.plan_code}>{item.name}</option>
                      ))}
                    </select>
                    <label>到期时间<input type="datetime-local" value={String(f.expires_at || "").slice(0, 16)} onChange={(e) => updateField(sk, "expires_at", e.target.value)} disabled={loading} /></label>
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
