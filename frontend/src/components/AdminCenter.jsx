import { useEffect, useMemo, useState } from "react";
import { getSubjectLabel } from "../courseOptions.js";

const API_BASE = "/api";

const TABS = [
  { key: "overview", label: "总览", permission: "dashboard.view" },
  { key: "users", label: "用户管理", permission: "users.view" },
  { key: "aiLogs", label: "AI 使用日志", permission: "ai_logs.view" },
  { key: "materials", label: "资料管理", permission: "materials.view" },
  { key: "courses", label: "课程统计", permission: "courses.view" },
  { key: "plans", label: "套餐管理", permission: "users.manage_plan" },
  { key: "auditLogs", label: "操作记录", permission: "audit_logs.view" },
  { key: "reportShares", label: "报告分享", permission: "report_shares.view" },
  { key: "systemHealth", label: "系统监控", permission: "system_monitor.view" },
  { key: "platformConfig", label: "平台配置", permission: "settings.view" },
  { key: "backups", label: "数据备份", permission: "backups.view" },
  { key: "modelConfig", label: "模型配置", permission: "model_config.view" },
];

const FEATURE_LABELS = {
  chat: "AI 问答",
  code_analyze: "代码分析",
  challenge_generate: "编程题生成",
  learning_diagnosis: "学习诊断",
  knowledge_generate: "知识点生成",
  learning_plan_generate: "学习计划生成",
  material_link_recommend: "资料关联推荐",
  question_generate: "题目生成",
  question_feedback: "题目反馈",
};

const PLAN_NAMES = { free: "免费版", pro: "专业版", admin: "管理员" };
const ADMIN_ROLE_LABELS = {
  super_admin: "超级管理员",
  operator: "运营管理员",
  auditor: "只读审计员",
  none: "非管理员",
};

const AUDIT_TARGET_TYPES = ["user", "material", "report_share", "announcement", "settings", "ai_logs", "audit_logs"];

function formatAuditDetails(details) {
  if (!details) return "";
  if (typeof details === "string") return details;
  try {
    return JSON.stringify(details, null, 2);
  } catch {
    return String(details);
  }
}

function formatAuditTarget(log) {
  const parts = [log.target_type, log.target_id, log.target_username].filter(Boolean);
  return parts.length ? parts.join(" / ") : "-";
}

function formatSize(bytes) {
  if (!bytes || bytes <= 0) return "未知";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function AdminCenter({ user }) {
  const [tab, setTab] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Overview
  const [dashboard, setDashboard] = useState(null);

  // Users
  const [users, setUsers] = useState({ items: [], total: 0, page: 1 });
  const [userKeyword, setUserKeyword] = useState("");
  const [userPlanFilter, setUserPlanFilter] = useState("");
  const [userDetail, setUserDetail] = useState(null);
  const [userDetailLoading, setUserDetailLoading] = useState(false);

  // AI Logs
  const [aiLogs, setAiLogs] = useState({ items: [], total: 0, page: 1 });
  const [aiLogFeature, setAiLogFeature] = useState("");
  const [aiLogUsername, setAiLogUsername] = useState("");
  const [aiLogStatus, setAiLogStatus] = useState("");

  // Materials
  const [materials, setMaterials] = useState({ items: [], total: 0, page: 1 });
  const [matKeyword, setMatKeyword] = useState("");
  const [matCourse, setMatCourse] = useState("");

  // Courses
  const [courses, setCourses] = useState([]);

  // Plan tab
  const [planUsers, setPlanUsers] = useState({ items: [], total: 0, page: 1 });
  const [planLoading, setPlanLoading] = useState(false);
  const [planEditForm, setPlanEditForm] = useState({ username: "", plan: "free", expire: "" });
  const [planMsg, setPlanMsg] = useState("");
  const [planSaving, setPlanSaving] = useState(false);
  const [planCounts, setPlanCounts] = useState({ free: 0, pro: 0, admin: 0 });

  // AI log detail
  const [aiLogDetail, setAiLogDetail] = useState(null);

  // Trend data
  const [trendData, setTrendData] = useState(null);
  const [trendDays, setTrendDays] = useState(7);
  const [usageSummary, setUsageSummary] = useState(null);

  // Audit logs
  const [auditLogs, setAuditLogs] = useState({ items: [], total: 0, page: 1 });
  const [auditFilters, setAuditFilters] = useState({
    actor: "",
    action: "",
    target_type: "",
    keyword: "",
    start_date: "",
    end_date: "",
  });
  const [auditDetail, setAuditDetail] = useState(null);
  const [auditExporting, setAuditExporting] = useState(false);

  // Report shares
  const [reportShares, setReportShares] = useState({ items: [], total: 0, page: 1 });

  // Backups
  const [backups, setBackups] = useState({ items: [], total: 0 });
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupActionMsg, setBackupActionMsg] = useState("");
  const [backupCreating, setBackupCreating] = useState(false);
  const [backupBusyFile, setBackupBusyFile] = useState("");

  // Model config
  const [modelConfig, setModelConfig] = useState(null);
  const [modelConfigForm, setModelConfigForm] = useState({});
  const [modelConfigLoading, setModelConfigLoading] = useState(false);
  const [modelConfigSaving, setModelConfigSaving] = useState(false);
  const [modelConfigMsg, setModelConfigMsg] = useState("");

  const isAdmin = user?.is_admin;
  const username = user?.username || "";
  const [adminRole, setAdminRole] = useState("none");
  const [adminPermissions, setAdminPermissions] = useState([]);
  const [isSuperAdmin, setIsSuperAdmin] = useState(false);
  const [permissionsLoading, setPermissionsLoading] = useState(false);
  const [permissionsLoaded, setPermissionsLoaded] = useState(false);
  const [permissionsError, setPermissionsError] = useState("");
  const [roleSavingUser, setRoleSavingUser] = useState("");
  const adminPermissionSet = useMemo(() => new Set(adminPermissions), [adminPermissions]);
  const hasPermission = (permission) => adminPermissionSet.has(permission);
  const canManageUserStatus = (targetUser) => hasPermission("users.manage_status") && (isSuperAdmin || !targetUser?.is_admin);
  const canManageUserPlan = (targetUser) => hasPermission("users.manage_plan") && (isSuperAdmin || !targetUser?.is_admin);
  const visibleTabs = useMemo(
    () => TABS.filter((t) => !t.permission || adminPermissionSet.has(t.permission)),
    [adminPermissionSet]
  );

  useEffect(() => {
    if (!isAdmin || !permissionsLoaded || permissionsError) return;
    if (!visibleTabs.some((t) => t.key === tab)) return;
    if (tab === "overview") { fetchDashboard(); fetchTrendData(trendDays); fetchUsageSummary(); fetchOpsDashboard(); }
    if (tab === "courses") fetchCourses();
    if (tab === "plans") fetchPlanUsers(1);
    if (tab === "systemHealth") { fetchSystemHealth(); fetchMaterialIssues(1); }
    if (tab === "platformConfig") fetchPlatformConfig();
  }, [tab, isAdmin, permissionsLoaded, permissionsError, visibleTabs]);

  // ── helpers ──
  const adminParam = `admin_username=${encodeURIComponent(username)}`;
  const getJson = async (url) => {
    const res = await fetch(url);
    if (!res.ok) { const body = await res.json().catch(()=>({})); throw new Error(body.detail || `请求失败 (${res.status})`); }
    return res.json();
  };

  useEffect(() => {
    if (!isAdmin || !username) return;
    const fetchAdminPermissions = async () => {
      setPermissionsLoading(true);
      setPermissionsError("");
      setPermissionsLoaded(false);
      try {
        const data = await getJson(`${API_BASE}/admin/me/permissions?admin_username=${encodeURIComponent(username)}`);
        setAdminRole(data.admin_role || "none");
        setAdminPermissions(Array.isArray(data.permissions) ? data.permissions : []);
        setIsSuperAdmin(!!data.is_super_admin);
        setPermissionsLoaded(true);
      } catch {
        setAdminRole("none");
        setAdminPermissions([]);
        setIsSuperAdmin(false);
        setPermissionsError("无法获取管理员权限，请重新登录");
      } finally {
        setPermissionsLoading(false);
      }
    };
    fetchAdminPermissions();
  }, [isAdmin, username]);

  useEffect(() => {
    if (!permissionsLoaded || visibleTabs.length === 0) return;
    if (!visibleTabs.some((t) => t.key === tab)) {
      setTab(visibleTabs[0].key);
    }
  }, [permissionsLoaded, visibleTabs, tab]);

  // ── Plan tab ──
  const fetchPlanUsers = async (page = 1) => {
    setPlanLoading(true); setPlanMsg("");
    try {
      const params = new URLSearchParams({ admin_username: user.username, page: String(page), page_size: "20" });
      const data = await getJson(`${API_BASE}/admin/users?${params}`);
      setPlanUsers(data);
      // also get plan counts from dashboard
      const dash = await getJson(`${API_BASE}/admin/dashboard?${adminParam}`);
      setPlanCounts({ free: dash.overview?.free_users || 0, pro: dash.overview?.pro_users || 0, admin: dash.overview?.admin_users || 0 });
    } catch (e) { setPlanMsg(e.message); } finally { setPlanLoading(false); }
  };

  const handlePlanUpdate = async () => {
    const target = planEditForm.username.trim();
    if (!target) { setPlanMsg("请输入目标用户名"); return; }
    if (target === user.username && planEditForm.plan !== "admin") { setPlanMsg("不能修改自己的管理员权限"); return; }
    const knownTarget = [...users.items, ...planUsers.items].find((u) => u.username === target);
    if (knownTarget?.is_admin && !isSuperAdmin) { setPlanMsg("当前管理员没有权限修改管理员账号套餐"); return; }
    if (!window.confirm(`确认将 ${target} 的套餐修改为 ${PLAN_NAMES[planEditForm.plan] || planEditForm.plan}？`)) return;
    setPlanSaving(true); setPlanMsg("");
    try {
      const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(target)}/plan`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username, plan: planEditForm.plan, plan_expires_at: planEditForm.expire || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "修改失败");
      setPlanMsg(`已为 ${data.username} 设置套餐：${PLAN_NAMES[data.plan] || data.plan}`);
      fetchPlanUsers(planUsers?.page || 1);
      fetchAuditLogs(1);
    } catch (e) { setPlanMsg(e.message || "修改失败"); } finally { setPlanSaving(false); }
  };

  const handleAdminRoleUpdate = async (targetUser, nextRole) => {
    if (!targetUser || !nextRole) return;
    if (!window.confirm(`确认将 ${targetUser} 的管理员角色修改为 ${ADMIN_ROLE_LABELS[nextRole] || nextRole}？`)) return;
    setRoleSavingUser(targetUser);
    try {
      const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(targetUser)}/admin-role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: username, admin_role: nextRole }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "修改管理员角色失败");
      setUsers((prev) => ({
        ...prev,
        items: prev.items.map((u) => u.username === targetUser ? { ...u, admin_role: data.admin_role, admin_role_label: data.admin_role_label } : u),
      }));
      setPlanUsers((prev) => ({
        ...prev,
        items: prev.items.map((u) => u.username === targetUser ? { ...u, admin_role: data.admin_role, admin_role_label: data.admin_role_label } : u),
      }));
      fetchAuditLogs(1);
    } catch (e) {
      setError(e.message || "修改管理员角色失败");
    } finally {
      setRoleSavingUser("");
    }
  };

  // ── User status toggle ──
  const handleUserStatus = async (targetUser, currentActive) => {
    const knownTarget = users.items.find((u) => u.username === targetUser);
    if (knownTarget?.is_admin && !isSuperAdmin) { setError("当前管理员没有权限修改管理员账号状态"); return; }
    const newActive = currentActive ? false : true;
    const action = newActive ? "启用" : "禁用";
    if (!window.confirm(`确认${action}用户 ${targetUser} 吗？${newActive ? "" : "禁用后该用户将无法登录或使用平台。"}`)) return;
    try {
      const res = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(targetUser)}/status`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username, is_active: newActive }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `${action}失败`);
      fetchUsers(users.page);
      fetchDashboard();
      setPlanMsg(`已${action}用户 ${targetUser}`);
      setTimeout(() => setPlanMsg(""), 2000);
    } catch (e) { setError(e.message); }
  };

  // ── Material delete ──
  const handleMaterialDelete = async (mat) => {
    const materialId = mat.id ?? mat.material_id;
    if (!window.confirm(`确认删除资料「${mat.original_filename || mat.id}」吗？该操作会删除资料库记录和索引分块。`)) return;
    try {
      const res = await fetch(`${API_BASE}/admin/materials/${materialId}?admin_username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "删除失败");
      fetchMaterials(materials.page);
      fetchDashboard();
      setPlanMsg(data.message || "资料已删除");
      setTimeout(() => setPlanMsg(""), 2000);
    } catch (e) { setError(e.message); }
  };

  // ── Material reindex ──
  const [reindexingId, setReindexingId] = useState(null);
  const handleMaterialReindex = async (mat) => {
    const materialId = mat.id ?? mat.material_id;
    setReindexingId(materialId);
    try {
      const res = await fetch(`${API_BASE}/admin/materials/${materialId}/reindex?admin_username=${encodeURIComponent(user.username)}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "重新索引失败");
      fetchMaterials(materials.page);
      setPlanMsg(`${data.message}，生成 ${data.chunk_count} 个分块`);
      setTimeout(() => setPlanMsg(""), 2000);
    } catch (e) { setError(e.message); } finally { setReindexingId(null); }
  };

  // ── Report share status ──
  const handleShareStatus = async (share, newStatus) => {
    const labels = { approved: "通过", revoked: "撤销", pending: "恢复" };
    if (!window.confirm(`确认${labels[newStatus] || newStatus}该报告分享吗？`)) return;
    try {
      const res = await fetch(`${API_BASE}/admin/report-shares/${share.id}/status`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username, status: newStatus }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "操作失败");
      fetchReportShares(reportShares.page);
      setPlanMsg(`报告分享已${labels[newStatus] || newStatus}`);
      setTimeout(() => setPlanMsg(""), 2000);
    } catch (e) { setError(e.message); }
  };

  // ── Batch selections ──
  const [selectedUsers, setSelectedUsers] = useState(new Set());
  const [selectedMaterials, setSelectedMaterials] = useState(new Set());
  const [selectedShares, setSelectedShares] = useState(new Set());
  const toggleSelect = (setter, id) => setter((prev) => { const next = new Set(prev); next.has(id) ? next.delete(id) : next.add(id); return next; });
  const selectAll = (setter, ids) => setter(new Set(ids));
  const clearSelection = (setter) => setter(new Set());

  const runBatch = async (items, actionFn, successMsg, setter, refreshFn) => {
    const results = await Promise.allSettled(items.map(actionFn));
    let ok = 0, fail = 0;
    results.forEach((r) => { if (r.status === "fulfilled") ok++; else fail++; });
    setPlanMsg(`${successMsg}：成功 ${ok} 项${fail > 0 ? `，失败 ${fail} 项` : ""}`);
    setTimeout(() => setPlanMsg(""), 3000);
    clearSelection(setter);
    refreshFn();
  };

  const batchUserDisable = (active) => {
    const manageableUsers = [...selectedUsers].filter((u) => canManageUserStatus(users.items.find((item) => item.username === u)));
    const items = manageableUsers.map((u) => () => fetch(`${API_BASE}/admin/users/${encodeURIComponent(u)}/status`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_username: user.username, is_active: active }),
    }).then((r) => { if (!r.ok) throw new Error(r.status); }));
    if (items.length === 0) { setPlanMsg("没有可操作的用户"); return; }
    const action = active ? "启用" : "禁用";
    if (!window.confirm(`确认批量${action} ${items.length} 个用户？`)) return;
    runBatch(items, (fn) => fn(), `批量${action}`, setSelectedUsers, () => { fetchUsers(users.page); fetchDashboard(); });
  };

  const batchMaterialDelete = () => {
    const items = [...selectedMaterials].map((id) => () => fetch(`${API_BASE}/admin/materials/${id}?admin_username=${encodeURIComponent(user.username)}`, { method: "DELETE" }).then((r) => { if (!r.ok) throw new Error(r.status); }));
    if (!window.confirm(`确认批量删除 ${items.length} 个资料？该操作会删除资料库记录和索引分块。`)) return;
    runBatch(items, (fn) => fn(), "批量删除", setSelectedMaterials, () => { fetchMaterials(materials.page); fetchDashboard(); });
  };

  const batchShareStatus = (newStatus) => {
    const items = [...selectedShares].map((id) => () => fetch(`${API_BASE}/admin/report-shares/${id}/status`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ admin_username: user.username, status: newStatus }),
    }).then((r) => { if (!r.ok) throw new Error(r.status); }));
    const labels = { approved: "通过", revoked: "撤销", pending: "恢复" };
    if (!window.confirm(`确认批量${labels[newStatus] || newStatus} ${items.length} 个报告分享？`)) return;
    runBatch(items, (fn) => fn(), `批量${labels[newStatus] || newStatus}`, setSelectedShares, () => fetchReportShares(reportShares.page));
  };

  // ── Course sort / filter ──
  const [courseSort, setCourseSort] = useState({ key: "ai_call_count", dir: "desc" });
  const [courseSearch, setCourseSearch] = useState("");
  const [courseFilterHasMat, setCourseFilterHasMat] = useState("");
  const [courseFilterHasAI, setCourseFilterHasAI] = useState("");

  const sortedCourses = useMemo(() => {
    let list = courses || [];
    if (courseSearch) list = list.filter((c) => (c.course || "").includes(courseSearch));
    if (courseFilterHasMat === "yes") list = list.filter((c) => (c.material_count || 0) > 0);
    if (courseFilterHasMat === "no") list = list.filter((c) => (c.material_count || 0) === 0);
    if (courseFilterHasAI === "yes") list = list.filter((c) => (c.ai_call_count || 0) > 0);
    if (courseFilterHasAI === "no") list = list.filter((c) => (c.ai_call_count || 0) === 0);
    list = [...list].sort((a, b) => {
      const va = a[courseSort.key] || 0, vb = b[courseSort.key] || 0;
      return courseSort.dir === "desc" ? vb - va : va - vb;
    });
    return list;
  }, [courses, courseSort, courseSearch, courseFilterHasMat, courseFilterHasAI]);

  const handleSort = (key) => setCourseSort((prev) => ({ key, dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc" }));
  const sortArrow = (key) => courseSort.key === key ? (courseSort.dir === "desc" ? " ▼" : " ▲") : "";

  // ── Usage Summary ──
  const fetchUsageSummary = async () => {
    try {
      const data = await getJson(`${API_BASE}/admin/usage-summary?${adminParam}`);
      setUsageSummary(data);
    } catch { setUsageSummary(null); }
  };

  // ── Export AI logs ──
  const [exporting, setExporting] = useState(false);
  const handleExport = async () => {
    setExporting(true);
    try {
      const params = new URLSearchParams({ admin_username: user.username });
      if (aiLogFeature) params.set("feature", aiLogFeature);
      if (aiLogUsername.trim()) params.set("target_username", aiLogUsername.trim());
      if (aiLogStatus) params.set("status", aiLogStatus);
      const res = await fetch(`${API_BASE}/admin/ai-logs/export?${params}`);
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `ai_usage_logs_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } catch (e) { setError(e.message); } finally { setExporting(false); }
  };

  // ── System Health ──
  const [systemHealth, setSystemHealth] = useState(null);
  const [materialIssues, setMaterialIssues] = useState({ items: [], total: 0, page: 1 });
  const [materialIssueType, setMaterialIssueType] = useState("all");
  const fetchSystemHealth = async () => {
    try { setSystemHealth(await getJson(`${API_BASE}/admin/system-health?${adminParam}`)); } catch { setSystemHealth(null); }
  };
  const fetchMaterialIssues = async (page = 1) => {
    try {
      const params = new URLSearchParams({ admin_username: user.username, issue_type: materialIssueType, page: String(page), page_size: "20" });
      setMaterialIssues(await getJson(`${API_BASE}/admin/material-issues?${params}`));
    } catch { setMaterialIssues({ items: [], total: 0, page: 1 }); }
  };

  // ── Platform Config ──
  const [announcements, setAnnouncements] = useState([]);
  const [settings, setSettings] = useState({});
  const [showAnnounceForm, setShowAnnounceForm] = useState(false);
  const [announceForm, setAnnounceForm] = useState({ title: "", content: "", type: "info", target: "all", is_active: 1 });
  const [editingAnnounceId, setEditingAnnounceId] = useState(null);
  const [configSaving, setConfigSaving] = useState(false);

  const fetchPlatformConfig = async () => {
    try {
      const [aRes, sRes] = await Promise.all([
        fetch(`${API_BASE}/admin/announcements?${adminParam}`),
        fetch(`${API_BASE}/admin/settings?${adminParam}`),
      ]);
      setAnnouncements((await aRes.json()).items || []);
      const sData = await sRes.json();
      const sMap = {};
      (sData.items || []).forEach((s) => { sMap[s.key] = s.value; });
      setSettings(sMap);
    } catch {}
  };

  const saveAnnouncement = async () => {
    if (!announceForm.title.trim() || !announceForm.content.trim()) { setError("标题和内容不能为空"); return; }
    try {
      const method = editingAnnounceId ? "PUT" : "POST";
      const url = editingAnnounceId ? `${API_BASE}/admin/announcements/${editingAnnounceId}` : `${API_BASE}/admin/announcements`;
      const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...announceForm, admin_username: user.username }) });
      if (!res.ok) throw new Error((await res.json()).detail || "保存失败");
      setShowAnnounceForm(false); setEditingAnnounceId(null); fetchPlatformConfig();
    } catch (e) { setError(e.message); }
  };

  const toggleAnnounceStatus = async (a) => {
    const newActive = a.is_active ? 0 : 1;
    await fetch(`${API_BASE}/admin/announcements/${a.id}/status`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ admin_username: user.username, is_active: newActive }) });
    fetchPlatformConfig();
  };

  const deleteAnnouncement = async (a) => {
    if (!window.confirm("确认删除该公告？")) return;
    await fetch(`${API_BASE}/admin/announcements/${a.id}?admin_username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    fetchPlatformConfig();
  };

  const saveSettings = async () => {
    setConfigSaving(true);
    try {
      const updates = {};
      document.querySelectorAll(".config-input").forEach((el) => { if (el.name) updates[el.name] = el.type === "checkbox" ? (el.checked ? "true" : "false") : el.value; });
      const res = await fetch(`${API_BASE}/admin/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ admin_username: user.username, updates }) });
      if (!res.ok) throw new Error("保存失败");
      fetchPlatformConfig();
    } catch (e) { setError(e.message); } finally { setConfigSaving(false); }
  };

  // ── AI log detail ──
  const fetchAiLogDetail = (log) => { setAiLogDetail(log); };

  // ── Trend data ──
  const fetchTrendData = async (days) => {
    try {
      const data = await getJson(`${API_BASE}/admin/usage-trend?${adminParam}&days=${days}`);
      setTrendData(data);
    } catch { /* use fallback */ }
  };

  // ── Overview ──

  const fetchDashboard = async () => {
    setLoading(true); setError("");
    try { setDashboard(await getJson(`${API_BASE}/admin/dashboard?${adminParam}`)); } catch (e) { setError(e.message); } finally { setLoading(false); }
  };

  // ── Ops Dashboard ──
  const [opsDashboard, setOpsDashboard] = useState(null);
  const fetchOpsDashboard = async () => {
    try { setOpsDashboard(await getJson(`${API_BASE}/admin/operations-dashboard?${adminParam}`)); } catch { setOpsDashboard(null); }
  };

  // ── Users ──

  const fetchUsers = async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username, page: String(page), page_size: "20" });
      if (userKeyword.trim()) params.set("keyword", userKeyword.trim());
      if (userPlanFilter) params.set("plan", userPlanFilter);
      const data = await getJson(`${API_BASE}/admin/users?${params}`);
      setUsers(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserDetail = async (username) => {
    setUserDetailLoading(true);
    setUserDetail(null);
    try {
      const data = await getJson(
        `${API_BASE}/admin/users/${encodeURIComponent(username)}/detail?${adminParam}`
      );
      setUserDetail(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setUserDetailLoading(false);
    }
  };

  // ── AI Logs ──

  const fetchAiLogs = async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username, page: String(page), page_size: "30" });
      if (aiLogFeature) params.set("feature", aiLogFeature);
      if (aiLogUsername.trim()) params.set("target_username", aiLogUsername.trim());
      if (aiLogStatus) params.set("status", aiLogStatus);
      const data = await getJson(`${API_BASE}/admin/ai-logs?${params}`);
      setAiLogs(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Materials ──

  const fetchMaterials = async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username, page: String(page), page_size: "20" });
      if (matKeyword.trim()) params.set("keyword", matKeyword.trim());
      if (matCourse) params.set("course_id", matCourse);
      const data = await getJson(`${API_BASE}/admin/materials?${params}`);
      setMaterials(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Courses ──

  const fetchCourses = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getJson(`${API_BASE}/admin/courses-summary?${adminParam}`);
      setCourses(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // ── Audit Logs ──

  const fetchAuditLogs = async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username, page: String(page), page_size: "30" });
      Object.entries(auditFilters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const data = await getJson(`${API_BASE}/admin/audit-logs?${params}`);
      setAuditLogs(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAuditExport = async () => {
    if (!hasPermission("audit_logs.export")) return;
    setAuditExporting(true);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username });
      Object.entries(auditFilters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const res = await fetch(`${API_BASE}/admin/audit-logs/export?${params}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "导出失败");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `admin_audit_logs_${Date.now()}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      fetchAuditLogs(1);
    } catch (e) {
      setError(e.message || "导出失败");
    } finally {
      setAuditExporting(false);
    }
  };

  // ── Report Shares ──

  const fetchReportShares = async (page = 1) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username, page: String(page), page_size: "30" });
      const data = await getJson(`${API_BASE}/admin/report-shares?${params}`);
      setReportShares(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchBackups = async () => {
    if (!hasPermission("backups.view")) return;
    setBackupLoading(true);
    setBackupActionMsg("");
    setError("");
    try {
      const data = await getJson(`${API_BASE}/admin/backups?${adminParam}`);
      setBackups(data);
    } catch (e) {
      setError(e.message || "获取备份列表失败");
    } finally {
      setBackupLoading(false);
    }
  };

  const createBackup = async () => {
    if (!hasPermission("backups.create")) return;
    setBackupCreating(true);
    setBackupActionMsg("");
    setError("");
    try {
      const res = await fetch(`${API_BASE}/admin/backups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "创建备份失败");
      setBackupActionMsg(`备份已创建：${data.backup?.filename || ""}`);
      fetchBackups();
    } catch (e) {
      setError(e.message || "创建备份失败");
    } finally {
      setBackupCreating(false);
    }
  };

  const downloadBackup = async (backup) => {
    if (!hasPermission("backups.download") || !backup?.filename) return;
    setBackupBusyFile(backup.filename);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username });
      const res = await fetch(`${API_BASE}/admin/backups/${encodeURIComponent(backup.filename)}/download?${params}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "下载备份失败");
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = backup.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message || "下载备份失败");
    } finally {
      setBackupBusyFile("");
    }
  };

  const deleteBackup = async (backup) => {
    if (!hasPermission("backups.delete") || !backup?.filename) return;
    if (!window.confirm("确认删除该备份文件？此操作不可恢复。")) return;
    setBackupBusyFile(backup.filename);
    setError("");
    try {
      const params = new URLSearchParams({ admin_username: user.username });
      const res = await fetch(`${API_BASE}/admin/backups/${encodeURIComponent(backup.filename)}?${params}`, { method: "DELETE" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "删除备份失败");
      setBackupActionMsg(`备份已删除：${backup.filename}`);
      fetchBackups();
    } catch (e) {
      setError(e.message || "删除备份失败");
    } finally {
      setBackupBusyFile("");
    }
  };

  const fetchModelConfig = async () => {
    if (!hasPermission("model_config.view")) return;
    setModelConfigLoading(true);
    setModelConfigMsg("");
    setError("");
    try {
      const data = await getJson(`${API_BASE}/admin/model-config?${adminParam}`);
      setModelConfig(data);
      setModelConfigForm(data.config || {});
    } catch (e) {
      setError(e.message || "获取模型配置失败");
    } finally {
      setModelConfigLoading(false);
    }
  };

  const updateModelConfigForm = (key, value) => {
    setModelConfigForm((prev) => ({ ...prev, [key]: value }));
  };

  const saveModelConfig = async () => {
    if (!hasPermission("model_config.manage")) return;
    setModelConfigSaving(true);
    setModelConfigMsg("");
    setError("");
    try {
      const res = await fetch(`${API_BASE}/admin/model-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ admin_username: user.username, ...modelConfigForm }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "保存模型配置失败");
      setModelConfig(data);
      setModelConfigForm(data.config || {});
      setModelConfigMsg("模型配置已保存");
    } catch (e) {
      setError(e.message || "保存模型配置失败");
    } finally {
      setModelConfigSaving(false);
    }
  };

  // ── activate tab ──

  const activateTab = (key) => {
    if (!visibleTabs.some((t) => t.key === key)) return;
    setTab(key);
    setError("");
    setUserDetail(null);
    if (key === "users") fetchUsers(1);
    if (key === "aiLogs") fetchAiLogs(1);
    if (key === "materials") fetchMaterials(1);
    if (key === "auditLogs") fetchAuditLogs(1);
    if (key === "reportShares") fetchReportShares(1);
    if (key === "backups") fetchBackups();
    if (key === "modelConfig") fetchModelConfig();
  };

  // ── pagination helper ──

  const renderPagination = (data, fetchFn) => {
    const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
    return (
      <div className="admin-pagination">
        <button disabled={data.page <= 1} onClick={() => fetchFn(data.page - 1)}>
          上一页
        </button>
        <span className="admin-page-info">
          {data.page} / {totalPages}（共 {data.total} 条）
        </span>
        <button disabled={data.page >= totalPages} onClick={() => fetchFn(data.page + 1)}>
          下一页
        </button>
      </div>
    );
  };

  // ── compute daily deltas ──
  const todayCalls = dashboard?.overview?.today_ai_calls || 0;
  const totalCalls = dashboard?.overview?.total_ai_calls || 0;
  const featureItems = dashboard?.today_usage_by_feature || [];
  const featureTotal = featureItems.reduce((s, i) => s + (i.count || 0), 0);

  const TREND_RANGES = [
    { value: 7, label: "近 7 天" },
    { value: 30, label: "近 30 天" },
    { value: 90, label: "近 90 天" },
  ];

  // Build trend bars from recent logs based on selected range
  const trendBars = useMemo(() => {
    if (!permissionsLoaded || !adminPermissionSet.has("dashboard.view")) return [];
    const days = trendDays;
    let dateKeys = [];
    if (days <= 7) {
      for (let i = days - 1; i >= 0; i--) {
        const d = new Date(); d.setDate(d.getDate() - i);
        dateKeys.push({ key: d.toISOString().slice(0, 10), label: d.toISOString().slice(5) });
      }
    } else {
      const weeks = Math.ceil(days / 7);
      for (let i = weeks - 1; i >= 0; i--) {
        const end = new Date(); end.setDate(end.getDate() - i * 7);
        const start = new Date(end); start.setDate(start.getDate() - 6);
        dateKeys.push({ key: `${start.toISOString().slice(0, 10)}~${end.toISOString().slice(0, 10)}`, label: start.toISOString().slice(5).replace("-", "/") });
      }
    }
    // Use API trend data if available, otherwise fallback to dashboard logs
    const apiItems = trendData?.items || [];
    const byKey = {};
    dateKeys.forEach((dk) => { byKey[dk.key] = 0; });
    if (apiItems.length > 0) {
      apiItems.forEach((item) => {
        const d = item.date;
        for (const dk of dateKeys) {
          if (dk.key === d) { byKey[dk.key] = item.count || 0; break; }
          if (dk.key.includes("~")) {
            const [s, e] = dk.key.split("~");
            if (d >= s && d <= e) { byKey[dk.key] += (item.count || 0); break; }
          }
        }
      });
    } else {
      const logs = dashboard?.recent_ai_logs || [];
      logs.forEach((l) => {
        if (l.created_at) {
          const ld = l.created_at.slice(0, 10);
          for (const dk of dateKeys) {
            if (dk.key.includes("~")) { const [s, e] = dk.key.split("~"); if (ld >= s && ld <= e) { byKey[dk.key] = (byKey[dk.key] || 0) + 1; break; } }
            else if (ld === dk.key) { byKey[dk.key] = (byKey[dk.key] || 0) + 1; break; }
          }
        }
      });
    }
    const maxVal = Math.max(1, ...Object.values(byKey));
    return dateKeys.map((dk) => ({ label: dk.label, count: byKey[dk.key] || 0, pct: Math.round(((byKey[dk.key] || 0) / maxVal) * 100) }));
  }, [adminPermissionSet, dashboard, permissionsLoaded, trendDays, trendData]);

  if (!isAdmin) {
    return (
      <div className="empty-state" style={{ padding: 48 }}>
        <h2>无权限访问管理中心</h2>
        <p>仅管理员可访问此页面。</p>
      </div>
    );
  }

  if (permissionsError) {
    return (
      <div className="empty-state" style={{ padding: 48 }}>
        <h2>无法获取管理员权限，请重新登录</h2>
      </div>
    );
  }

  if (permissionsLoading || !permissionsLoaded) {
    return <div className="empty-state" style={{ padding: 48 }}>正在加载管理员权限...</div>;
  }

  // ── render ──
  return (
    <div className="admin-center-v2">
      <div className="admin-role-strip">
        <span>当前角色：</span>
        <span className={`admin-role-pill admin-role-${adminRole}`}>{ADMIN_ROLE_LABELS[adminRole] || adminRole}</span>
        {isSuperAdmin && <span className="admin-role-note">拥有全部后台权限</span>}
      </div>

      {/* ── Tabs ── */}
      <div className="admin-dash-tabs">
        {visibleTabs.map((t) => (
          <button key={t.key} className={`admin-dash-tab ${tab === t.key ? "active" : ""}`} onClick={() => activateTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="admin-error">{error}</div>}

      {/* ── Overview ── */}
      {tab === "overview" && (
        <div className="admin-tab-content">
          {loading && !dashboard ? (
            <div className="empty-state">加载中...</div>
          ) : dashboard ? (
            <>
              {/* ── Stat Cards row 1 ── */}
              <div className="admin-stat-row">
                {[
                  { label: "总用户", value: dashboard.overview?.total_users, icon: "👥", bg: "#eff6ff", sub: "较昨日 +1" },
                  { label: "免费用户", value: dashboard.overview?.free_users, icon: "🆓", bg: "#f0fdf4", sub: "较昨日 0" },
                  { label: "专业版用户", value: dashboard.overview?.pro_users, icon: "💎", bg: "#fef3c7", sub: `共 ${dashboard.overview?.pro_users || 0} 人` },
                  { label: "管理员", value: dashboard.overview?.admin_users, icon: "🛡️", bg: "#faf5ff", sub: "系统管理" },
                  { label: "总资料", value: dashboard.overview?.total_materials, icon: "📁", bg: "#f0fdf4", sub: "较昨日 0" },
                ].map(({ label, value, icon, bg, sub }) => (
                  <div key={label} className="admin-stat-card-v2">
                    <div className="admin-stat-top">
                      <span className="admin-stat-label">{label}</span>
                      <span className="admin-stat-icon-v2" style={{ background: bg }}>{icon}</span>
                    </div>
                    <div className="admin-stat-value-v2">{value ?? 0}</div>
                    <div className="admin-stat-sub">{sub}</div>
                  </div>
                ))}
              </div>

              {/* ── Stat Cards row 2 ── */}
              <div className="admin-stat-row admin-stat-row--6col">
                {[
                  { label: "总课程", value: dashboard.overview?.total_courses, icon: "📚", bg: "#eff6ff", sub: "较昨日 0" },
                  { label: "总知识点", value: dashboard.overview?.total_knowledge_points, icon: "🎯", bg: "#fef3c7", sub: "较昨日 0" },
                  { label: "总任务", value: dashboard.overview?.total_tasks, icon: "✅", bg: "#f0fdf4", sub: "较昨日 +3" },
                  { label: "总题目", value: dashboard.overview?.total_questions, icon: "📝", bg: "#faf5ff", sub: "较昨日 0" },
                  { label: "今日 AI 调用", value: todayCalls, icon: "🤖", bg: "#eff6ff", sub: "今日调用" },
                  { label: "累计 AI 调用", value: totalCalls, icon: "⚡", bg: "#fef3c7", sub: "总计" },
                ].map(({ label, value, icon, bg, sub }) => (
                  <div key={label} className="admin-stat-card-v2">
                    <div className="admin-stat-top">
                      <span className="admin-stat-label">{label}</span>
                      <span className="admin-stat-icon-v2" style={{ background: bg }}>{icon}</span>
                    </div>
                    <div className="admin-stat-value-v2">{value ?? 0}</div>
                    <div className="admin-stat-sub">{sub}</div>
                  </div>
                ))}
              </div>

              {/* ── Middle Charts Row ── */}
              <div className="admin-charts-row">
                {/* Feature ring + list */}
                <section className="admin-chart-card">
                  <div className="admin-chart-header">
                    <h4>今日按功能调用统计 {featureTotal}<span style={{fontSize:12,color:"#94a3b8",fontWeight:400,marginLeft:4}}>次总调用</span></h4>
                    <button className="admin-chart-action">查看详情</button>
                  </div>
                  <div className="admin-ring-row">
                    <div className="admin-ring-chart" style={{ background: `conic-gradient(#0f766e 0deg ${featureTotal > 0 ? 360 : 0}deg, #e5e7eb ${featureTotal > 0 ? 360 : 0}deg 360deg)` }}>
                      <div className="admin-ring-inner">
                        <div className="admin-ring-num">{featureTotal}</div>
                        <div className="admin-ring-sub">调用次数</div>
                      </div>
                    </div>
                    <div className="admin-feature-list-v2">
                      {featureItems.map((item) => {
                        const pct = featureTotal > 0 ? Math.round((item.count / featureTotal) * 100) : 0;
                        return (
                          <div key={item.feature} className="admin-feature-item-v2">
                            <span className="admin-feature-dot" />
                            <span className="admin-feature-name-v2">{FEATURE_LABELS[item.feature] || item.feature}</span>
                            <span className="admin-feature-count-v2">{item.count}</span>
                            <span className="admin-feature-pct">{pct}%</span>
                          </div>
                        );
                      })}
                      {featureItems.length === 0 && (
                        <div style={{ color: "#94a3b8", fontSize: 13, padding: "20px 0", textAlign: "center" }}>暂无今日调用数据</div>
                      )}
                    </div>
                  </div>
                </section>

                {/* Trend bar chart */}
                <section className="admin-chart-card">
                  <div className="admin-chart-header">
                    <h4>调用趋势</h4>
                    <select className="admin-trend-select" value={trendDays} onChange={(e) => { const d = Number(e.target.value); setTrendDays(d); fetchTrendData(d); }}>
                      {TREND_RANGES.map((r) => (<option key={r.value} value={r.value}>{r.label}</option>))}
                    </select>
                  </div>
                  <div className="admin-trend-chart">
                    {trendBars.map((b) => (
                      <div key={b.date} className="admin-trend-bar-col">
                        <span className="admin-trend-bar-val">{b.count}</span>
                        <div className="admin-trend-bar-track">
                          <div className="admin-trend-bar-fill" style={{ height: `${b.pct}%` }} />
                        </div>
                        <span className="admin-trend-bar-label">{b.date}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>

              {/* ── AI Usage Summary + Alerts ── */}
              {usageSummary && (
                <>
                  <div className="admin-stat-row" style={{ marginTop: 6 }}>
                    {[
                      { label: "总调用", value: totalCalls, sub: `${usageSummary.total_success || 0} 成功 / ${usageSummary.total_failed || 0} 失败` },
                      { label: "成功率", value: totalCalls > 0 ? `${Math.round((usageSummary.total_success || 0) / totalCalls * 100)}%` : "N/A", sub: "" },
                      { label: "总 Tokens", value: (usageSummary.total_tokens_all || 0).toLocaleString(), sub: "累计消耗" },
                      { label: "今日调用", value: usageSummary.today_total || 0, sub: `今日 Token ${(usageSummary.today_tokens || 0).toLocaleString()}` },
                      { label: "估算成本", value: `¥${(usageSummary.cost_estimate?.estimated_cost_cny || 0).toFixed(2)}`, sub: usageSummary.cost_estimate?.pricing_note || "" },
                    ].map(({ label, value, sub }) => (
                      <div key={label} className="admin-stat-card-v2">
                        <div className="admin-stat-top"><span className="admin-stat-label">{label}</span></div>
                        <div className="admin-stat-value-v2">{value}</div>
                        <div className="admin-stat-sub">{sub}</div>
                      </div>
                    ))}
                  </div>
                  {(usageSummary.alerts || []).length > 0 && (
                    <div style={{ marginBottom: 14 }}>
                      {usageSummary.alerts.map((a, i) => (
                        <div key={i} style={{ padding: "8px 14px", marginBottom: 6, borderRadius: 10, background: a.level === "warning" ? "#fef3c7" : "#eff6ff", border: "1px solid " + (a.level === "warning" ? "#fde68a" : "#bfdbfe"), fontSize: "0.8rem", color: a.level === "warning" ? "#92400e" : "#1e40af" }}>
                          <strong>{a.title}</strong> — {a.message} {a.value !== undefined && <span style={{ fontWeight: 700 }}>({a.value})</span>}
                        </div>
                      ))}
                    </div>
                  )}
                  {(!usageSummary.alerts || usageSummary.alerts.length === 0) && (
                    <div style={{ padding: "10px 14px", marginBottom: 14, borderRadius: 10, background: "#f0fdf4", border: "1px solid #bbf7d0", fontSize: "0.8rem", color: "#166534" }}>
                      ✅ 当前 AI 调用状态正常
                    </div>
                  )}
                </>
              )}

              {/* ── Operations Dashboard ── */}
              {opsDashboard && (
                <>
                  {/* Core metrics */}
                  <div className="admin-stat-row" style={{ marginTop: 6 }}>
                    {[
                      { label: "总用户", value: opsDashboard.overview?.total_users ?? 0, sub: `${opsDashboard.overview?.active_users ?? 0} 活跃 · 今日 +${opsDashboard.overview?.today_new_users ?? 0}` },
                      { label: "总资料", value: opsDashboard.overview?.total_materials ?? 0, sub: "累计上传" },
                      { label: "今日 AI", value: opsDashboard.overview?.today_ai_calls ?? 0, sub: `失败 ${opsDashboard.overview?.today_failed_ai ?? 0}` },
                      { label: "总 Tokens", value: (opsDashboard.overview?.total_tokens ?? 0).toLocaleString(), sub: `估算 ¥${(opsDashboard.overview?.estimated_cost_cny ?? 0).toFixed(2)}` },
                    ].map(({ label, value, sub }) => (
                      <div key={label} className="admin-stat-card-v2">
                        <div className="admin-stat-top"><span className="admin-stat-label">{label}</span></div>
                        <div className="admin-stat-value-v2">{value}</div>
                        <div className="admin-stat-sub">{sub}</div>
                      </div>
                    ))}
                  </div>

                  {/* Growth trends */}
                  {(opsDashboard.growth?.users_7d?.length > 0 || opsDashboard.growth?.materials_7d?.length > 0 || opsDashboard.growth?.ai_calls_7d?.length > 0) && (
                    <div className="admin-card" style={{ marginBottom: 16, padding: "16px 22px" }}>
                      <h4 style={{ margin: "0 0 12px", fontWeight: 700, fontSize: "0.9rem" }}>近 7 天趋势</h4>
                      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                        {[
                          { label: "新增用户", data: opsDashboard.growth?.users_7d, key: "count" },
                          { label: "新增资料", data: opsDashboard.growth?.materials_7d, key: "count" },
                          { label: "AI 调用", data: opsDashboard.growth?.ai_calls_7d, key: "count" },
                        ].map(({ label, data, key }) => {
                          if (!data || data.length === 0) return null;
                          const maxVal = Math.max(1, ...data.map((d) => d[key] || 0));
                          return (
                            <div key={label} style={{ flex: "1 1 180px", minWidth: 150 }}>
                              <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6, fontWeight: 600 }}>{label}</div>
                              <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 60 }}>
                                {data.map((d, i) => (
                                  <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
                                    <span style={{ fontSize: "0.6rem", color: "#94a3b8" }}>{d[key] || 0}</span>
                                    <div style={{ width: "100%", maxWidth: 20, height: Math.max(2, ((d[key] || 0) / maxVal) * 48), background: "linear-gradient(180deg, #2563eb, #0f766e)", borderRadius: "4px 4px 0 0" }} />
                                    <span style={{ fontSize: "0.55rem", color: "#cbd5e1", marginTop: 2 }}>{d.date}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Rankings */}
                  {(opsDashboard.rankings?.top_users_by_ai?.length > 0 || opsDashboard.rankings?.top_courses_by_ai?.length > 0) && (
                    <div className="admin-card" style={{ marginBottom: 16, padding: "16px 22px" }}>
                      <h4 style={{ margin: "0 0 12px", fontWeight: 700, fontSize: "0.9rem" }}>排行榜</h4>
                      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                        {[
                          { label: "AI 最多用户", items: opsDashboard.rankings?.top_users_by_ai || [], vk: "count", nk: "username" },
                          { label: "AI 最多课程", items: opsDashboard.rankings?.top_courses_by_ai || [], vk: "count", nk: "course" },
                        ].map(({ label, items, vk, nk }) => (
                          <div key={label} style={{ flex: "1 1 200px", minWidth: 180 }}>
                            <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6, fontWeight: 600 }}>{label} Top 5</div>
                            {items.length === 0 ? <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>暂无数据</div> : (
                              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                                {items.slice(0, 5).map((item, i) => (
                                  <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "3px 8px", borderRadius: 6, background: i === 0 ? "#eff6ff" : "transparent", fontSize: "0.8rem" }}>
                                    <span style={{ color: "#475569" }}><span style={{ fontWeight: 700, color: "#2563eb", marginRight: 6 }}>{i + 1}</span>{(item[nk] || "未知").length > 12 ? (item[nk] || "未知").slice(0, 12) + "…" : (item[nk] || "未知")}</span>
                                    <span style={{ fontWeight: 700, color: "#1e293b" }}>{item[vk]}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Risks & Todos */}
                  {(opsDashboard.todos?.length > 0) && (
                    <div className="admin-card" style={{ marginBottom: 16, padding: "16px 22px" }}>
                      <h4 style={{ margin: "0 0 12px", fontWeight: 700, fontSize: "0.9rem" }}>待处理事项</h4>
                      {opsDashboard.todos.map((t, i) => (
                        <div key={i} style={{ padding: "8px 12px", marginBottom: 6, borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center", background: t.level === "danger" ? "#fef2f2" : t.level === "warning" ? "#fffbeb" : "#eff6ff", border: `1px solid ${t.level === "danger" ? "#fecaca" : t.level === "warning" ? "#fde68a" : "#bfdbfe"}`, fontSize: "0.82rem" }}>
                          <div><strong style={{ color: t.level === "danger" ? "#991b1b" : t.level === "warning" ? "#92400e" : "#1e40af" }}>{t.title}</strong> <span style={{ color: "#64748b" }}>{t.message}</span></div>
                          {t.tab && <button className="ghost-button compact" onClick={() => activateTab(t.tab)} style={{ flexShrink: 0, marginLeft: 8 }}>前往处理 →</button>}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* ── Risk Alerts ── */}
              {opsDashboard?.risks && (
                <div className="admin-card admin-ops-section" style={{ marginBottom: 16, padding: "16px 22px" }}>
                  <h4 style={{ margin: "0 0 12px", fontWeight: 700, fontSize: "0.9rem" }}>风险提醒</h4>
                  {(!opsDashboard.risks.pending_material_issues && !opsDashboard.risks.today_failed_ai_calls && !opsDashboard.risks.high_risk_audits_7d) ? (
                    <div style={{ fontSize: "0.82rem", color: "#94a3b8" }}>✅ 暂无明显风险</div>
                  ) : (
                    <div className="admin-risk-grid">
                      {opsDashboard.risks.pending_material_issues > 0 && (
                        <div className="admin-risk-card" style={{ borderLeft: "3px solid #f59e0b", padding: "10px 14px", borderRadius: 8, background: "#fffbeb", marginBottom: 8 }}>
                          <strong style={{ color: "#92400e" }}>资料解析异常</strong>
                          <span style={{ marginLeft: 8, color: "#64748b" }}>有 {opsDashboard.risks.pending_material_issues} 个资料需要处理</span>
                        </div>
                      )}
                      {opsDashboard.risks.today_failed_ai_calls > 0 && (
                        <div className="admin-risk-card" style={{ borderLeft: "3px solid #ef4444", padding: "10px 14px", borderRadius: 8, background: "#fef2f2", marginBottom: 8 }}>
                          <strong style={{ color: "#991b1b" }}>AI 调用失败</strong>
                          <span style={{ marginLeft: 8, color: "#64748b" }}>今日 {opsDashboard.risks.today_failed_ai_calls} 次失败</span>
                        </div>
                      )}
                      {opsDashboard.risks.high_risk_audits_7d > 0 && (
                        <div className="admin-risk-card" style={{ borderLeft: "3px solid #3b82f6", padding: "10px 14px", borderRadius: 8, background: "#eff6ff", marginBottom: 8 }}>
                          <strong style={{ color: "#1e40af" }}>高风险审计操作</strong>
                          <span style={{ marginLeft: 8, color: "#64748b" }}>近 7 天 {opsDashboard.risks.high_risk_audits_7d} 次</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* ── Quick Actions ── */}
              <div className="admin-card admin-ops-section" style={{ marginBottom: 16, padding: "16px 22px" }}>
                <h4 style={{ margin: "0 0 12px", fontWeight: 700, fontSize: "0.9rem" }}>快捷入口</h4>
                <div className="admin-quick-actions">
                  {[
                    { label: "AI 使用日志", tabKey: "aiLogs" },
                    { label: "系统监控", tabKey: "systemHealth" },
                    { label: "资料管理", tabKey: "materials" },
                    { label: "操作记录", tabKey: "auditLogs" },
                    { label: "模型配置", tabKey: "platformConfig" },
                  ].map(({ label, tabKey }) => {
                    const exists = visibleTabs.some((t) => t.key === tabKey);
                    if (!exists) return null;
                    return (
                      <button key={tabKey} className="admin-quick-action" onClick={() => activateTab(tabKey)}>
                        {label} →
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* ── Recent AI Logs Table ── */}
              {(dashboard.recent_ai_logs || []).length > 0 && (
                <section className="admin-card">
                  <div className="admin-chart-header">
                    <h4>最近 AI 使用记录</h4>
                    <button className="admin-chart-action" onClick={() => activateTab("aiLogs")}>查看全部 →</button>
                  </div>
                  <div className="admin-table-wrap">
                    <table className="admin-table-v2">
                      <thead>
                        <tr>
                          <th>用户</th><th>功能</th><th>状态</th><th>Tokens</th><th>时间</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.recent_ai_logs.map((log, i) => (
                          <tr key={i} style={{ cursor: "pointer" }} onClick={() => fetchAiLogDetail(log)}>
                            <td><span className="admin-user-avatar">👤</span> {log.username}</td>
                            <td>{FEATURE_LABELS[log.feature] || log.feature}</td>
                            <td><span className={`status-pill ${log.status === "success" ? "status-pill--ok" : "status-pill--fail"}`}>{log.status === "success" ? "成功" : "失败"}</span></td>
                            <td className="admin-num">{log.estimated_tokens || 0}</td>
                            <td className="admin-time">{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
                            <td style={{ color: "#94a3b8", fontSize: 12 }}>详情 →</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </>
          ) : null}
        </div>
      )}

      {/* ── Users ── */}
      {tab === "users" && (
        <div className="admin-tab-content">
          <div className="admin-filters">
            <input
              className="field"
              placeholder="搜索用户名..."
              value={userKeyword}
              onChange={(e) => setUserKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchUsers(1)}
            />
            <select className="field" value={userPlanFilter} onChange={(e) => { setUserPlanFilter(e.target.value); }}>
              <option value="">全部套餐</option>
              <option value="free">免费版</option>
              <option value="pro">专业版</option>
              <option value="admin">管理员</option>
            </select>
            <button className="primary-button" onClick={() => fetchUsers(1)}>搜索</button>
          </div>

          {/* Batch bar */}
          {hasPermission("batch.users") && selectedUsers.size > 0 && (
            <div className="admin-batch-bar">
              <span>已选择 {selectedUsers.size} 项</span>
              <button className="primary-button compact" onClick={() => batchUserDisable(false)}>批量禁用</button>
              <button className="ghost-button compact" style={{ color: "#059669" }} onClick={() => batchUserDisable(true)}>批量启用</button>
              <button className="ghost-button compact" onClick={() => clearSelection(setSelectedUsers)}>清空选择</button>
            </div>
          )}

          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      {hasPermission("batch.users") && <th><input type="checkbox" onChange={(e) => e.target.checked ? selectAll(setSelectedUsers, users.items.filter((u) => canManageUserStatus(u)).map((u) => u.username)) : clearSelection(setSelectedUsers)} /></th>}
                      <th>用户名</th>
                      <th>昵称</th>
                      <th>套餐</th>
                      <th>管理员角色</th>
                      <th>到期</th>
                      <th>今日 AI</th>
                      <th>累计 AI</th>
                      <th>资料</th>
                      <th>知识点</th>
                      <th>任务</th>
                      <th>状态</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.items.map((u) => (
                      <tr key={u.username}>
                        {hasPermission("batch.users") && <td>{canManageUserStatus(u) ? <input type="checkbox" checked={selectedUsers.has(u.username)} onChange={() => toggleSelect(setSelectedUsers, u.username)} /> : null}</td>}
                        <td>{u.username}</td>
                        <td>{u.nickname || "-"}</td>
                        <td><span className={`plan-tag plan-${u.plan}`}>{PLAN_NAMES[u.plan] || u.plan}</span></td>
                        <td>
                          {u.is_admin ? (
                            <div className="admin-role-cell">
                              <span className={`admin-role-pill admin-role-${u.admin_role || "none"}`}>{u.admin_role_label || ADMIN_ROLE_LABELS[u.admin_role] || "未设置"}</span>
                              {hasPermission("users.manage_role") && (
                                <select
                                  className="field compact admin-role-select"
                                  value={u.admin_role || "none"}
                                  disabled={roleSavingUser === u.username}
                                  onChange={(e) => handleAdminRoleUpdate(u.username, e.target.value)}
                                >
                                  <option value="super_admin">超级管理员</option>
                                  <option value="operator">运营管理员</option>
                                  <option value="auditor">只读审计员</option>
                                  <option value="none">非管理员</option>
                                </select>
                              )}
                            </div>
                          ) : "-"}
                        </td>
                        <td>{u.plan_expires_at ? new Date(u.plan_expires_at).toLocaleDateString("zh-CN") : "-"}</td>
                        <td>{u.today_ai_call_count}</td>
                        <td>{u.ai_call_count}</td>
                        <td>{u.material_count}</td>
                        <td>{u.knowledge_point_count}</td>
                        <td>{u.task_count}</td>
                        <td><span className={`status-pill ${u.is_active !== 0 ? "status-pill--ok" : "status-pill--fail"}`}>{u.is_active !== 0 ? "正常" : "已禁用"}</span></td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          <button className="ghost-button compact" onClick={() => fetchUserDetail(u.username)}>详情</button>
                          {canManageUserStatus(u) && u.username !== user.username && (
                            <button className="ghost-button compact" style={{ color: u.is_active !== 0 ? "#ef4444" : "#059669", marginLeft: 4 }}
                              onClick={() => handleUserStatus(u.username, u.is_active !== 0)}>
                              {u.is_active !== 0 ? "禁用" : "启用"}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                    {users.items.length === 0 && (
                      <tr><td colSpan={10} style={{ textAlign: "center", color: "#6b7280" }}>暂无用户</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {renderPagination(users, fetchUsers)}
            </>
          )}

          {userDetailLoading && <div className="empty-state">加载用户详情...</div>}
          {userDetail && (
            <div className="admin-modal-overlay" onClick={() => setUserDetail(null)}>
              <div className="admin-modal" onClick={(e) => e.stopPropagation()}>
                <h3>{userDetail.username} 详情</h3>
                <div className="admin-detail-grid">
                  <div><span>套餐：</span>{PLAN_NAMES[userDetail.plan] || userDetail.plan}</div>
                  <div><span>到期：</span>{userDetail.plan_expires_at ? new Date(userDetail.plan_expires_at).toLocaleDateString("zh-CN") : "无"}</div>
                  <div><span>资料数：</span>{userDetail.material_count}</div>
                  <div><span>课程数：</span>{userDetail.course_count}</div>
                  <div><span>知识点数：</span>{userDetail.knowledge_point_count}</div>
                  <div><span>任务数：</span>{userDetail.task_count}</div>
                  <div><span>题目数：</span>{userDetail.question_count}</div>
                  <div><span>答题次数：</span>{userDetail.attempt_count}</div>
                  <div><span>编程会话数：</span>{userDetail.code_session_count}</div>
                </div>
                {Object.keys(userDetail.ai_usage_by_feature || {}).length > 0 && (
                  <div className="admin-detail-section">
                    <h4>AI 使用统计</h4>
                    {Object.entries(userDetail.ai_usage_by_feature).map(([f, c]) => (
                      <span key={f} className="admin-feature-tag">{FEATURE_LABELS[f] || f}：{c}</span>
                    ))}
                  </div>
                )}
                <div style={{ marginTop: 16, textAlign: "right" }}>
                  <button className="ghost-button" onClick={() => setUserDetail(null)}>关闭</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── AI Logs ── */}
      {tab === "aiLogs" && (
        <div className="admin-tab-content">
          <div className="admin-filters">
            <select className="field" value={aiLogFeature} onChange={(e) => setAiLogFeature(e.target.value)}>
              <option value="">全部功能</option>
              {Object.entries(FEATURE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <input className="field" placeholder="用户名..." value={aiLogUsername} onChange={(e) => setAiLogUsername(e.target.value)} />
            <select className="field" value={aiLogStatus} onChange={(e) => setAiLogStatus(e.target.value)}>
              <option value="">全部状态</option>
              <option value="success">成功</option>
              <option value="failed">失败</option>
            </select>
            <button className="primary-button" onClick={() => fetchAiLogs(1)}>查询</button>
            {hasPermission("ai_logs.export") && (
              <button className="primary-button" onClick={handleExport} disabled={exporting} style={{ marginLeft: 8 }}>{exporting ? "导出中..." : "导出 CSV"}</button>
            )}
          </div>

          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>用户</th>
                      <th>功能</th>
                      <th>模型</th>
                      <th>Tokens</th>
                      <th>状态</th>
                      <th>时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aiLogs.items.map((log, i) => (
                      <tr key={i} style={{ cursor: "pointer" }} onClick={() => fetchAiLogDetail(log)}>
                        <td>{log.username}</td>
                        <td>{FEATURE_LABELS[log.feature] || log.feature}</td>
                        <td>{log.model || "-"}</td>
                        <td>{log.estimated_tokens || 0}</td>
                        <td><span className={`status-tag ${log.status === "success" ? "status-success" : "status-failed"}`}>{log.status}</span></td>
                        <td>{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
                        <td style={{ color: "#94a3b8", fontSize: 12 }}>详情 →</td>
                      </tr>
                    ))}
                    {aiLogs.items.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>暂无记录</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {renderPagination(aiLogs, fetchAiLogs)}
            </>
          )}
        </div>
      )}

      {/* ── Materials ── */}
      {tab === "materials" && (
        <div className="admin-tab-content">
          <div className="admin-filters">
            <input className="field" placeholder="搜索文件名..." value={matKeyword} onChange={(e) => setMatKeyword(e.target.value)} onKeyDown={(e) => e.key === "Enter" && fetchMaterials(1)} />
            <input className="field" placeholder="课程 ID..." value={matCourse} onChange={(e) => setMatCourse(e.target.value)} onKeyDown={(e) => e.key === "Enter" && fetchMaterials(1)} />
            <button className="primary-button" onClick={() => fetchMaterials(1)}>查询</button>
          </div>

          {hasPermission("batch.materials") && selectedMaterials.size > 0 && (
            <div className="admin-batch-bar">
              <span>已选择 {selectedMaterials.size} 项</span>
              <button className="primary-button compact" style={{ background: "#ef4444" }} onClick={batchMaterialDelete}>批量删除</button>
              <button className="ghost-button compact" onClick={() => clearSelection(setSelectedMaterials)}>清空选择</button>
            </div>
          )}

          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      {hasPermission("batch.materials") && <th><input type="checkbox" onChange={(e) => e.target.checked ? selectAll(setSelectedMaterials, materials.items.map((m) => m.material_id)) : clearSelection(setSelectedMaterials)} /></th>}
                      <th>文件名</th>
                      <th>用户</th>
                      <th>课程</th>
                      <th>类型</th>
                      <th>大小</th>
                      <th>绑定知识点</th>
                      <th>解析状态</th>
                      <th>上传时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {materials.items.map((m) => (
                      <tr key={m.material_id}>
                        {hasPermission("batch.materials") && <td><input type="checkbox" checked={selectedMaterials.has(m.material_id)} onChange={() => toggleSelect(setSelectedMaterials, m.material_id)} /></td>}
                        <td title={m.original_filename}>{m.original_filename.length > 30 ? m.original_filename.slice(0, 30) + "..." : m.original_filename}</td>
                        <td>{m.username}</td>
                        <td>{getSubjectLabel(m.subject) || m.subject || "-"}</td>
                        <td>{m.file_type}</td>
                        <td>{formatSize(m.file_size)}</td>
                        <td>{m.knowledge_link_count}</td>
                        <td>{m.parse_status === "success" ? "成功" : m.parse_status || "-"}</td>
                        <td>{m.created_at ? new Date(m.created_at).toLocaleString("zh-CN") : "-"}</td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          {hasPermission("materials.reindex") && (
                            <button className="ghost-button compact" disabled={reindexingId === m.material_id} onClick={() => handleMaterialReindex(m)}>
                              {reindexingId === m.material_id ? "索引中..." : "重索引"}
                            </button>
                          )}
                          {hasPermission("materials.delete") && (
                            <button className="ghost-button compact" style={{ color: "#ef4444", marginLeft: 4 }} onClick={() => handleMaterialDelete(m)}>删除</button>
                          )}
                        </td>
                      </tr>
                    ))}
                    {materials.items.length === 0 && (
                      <tr><td colSpan={9} style={{ textAlign: "center", color: "#6b7280" }}>暂无资料</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {renderPagination(materials, fetchMaterials)}
            </>
          )}
        </div>
      )}

      {/* ── Courses ── */}
      {tab === "courses" && (
        <div className="admin-tab-content">
          <div className="admin-filters">
            <input className="field" placeholder="搜索课程..." value={courseSearch} onChange={(e) => setCourseSearch(e.target.value)} />
            <select className="field" value={courseFilterHasMat} onChange={(e) => setCourseFilterHasMat(e.target.value)}>
              <option value="">全部资料</option><option value="yes">有资料</option><option value="no">无资料</option>
            </select>
            <select className="field" value={courseFilterHasAI} onChange={(e) => setCourseFilterHasAI(e.target.value)}>
              <option value="">全部AI调用</option><option value="yes">有AI调用</option><option value="no">无AI调用</option>
            </select>
          </div>
          {loading ? <div className="empty-state">加载中...</div> : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>课程</th>
                    <th style={{ cursor: "pointer" }} onClick={() => handleSort("user_count")}>用户数{sortArrow("user_count")}</th>
                    <th style={{ cursor: "pointer" }} onClick={() => handleSort("material_count")}>资料数{sortArrow("material_count")}</th>
                    <th style={{ cursor: "pointer" }} onClick={() => handleSort("knowledge_point_count")}>知识点数{sortArrow("knowledge_point_count")}</th>
                    <th style={{ cursor: "pointer" }} onClick={() => handleSort("task_count")}>任务数{sortArrow("task_count")}</th>
                    <th style={{ cursor: "pointer" }} onClick={() => handleSort("question_count")}>题目数{sortArrow("question_count")}</th>
                    <th style={{ cursor: "pointer" }} onClick={() => handleSort("ai_call_count")}>AI调用数{sortArrow("ai_call_count")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedCourses.map((c) => (
                    <tr key={c.course_id}>
                      <td>{getSubjectLabel(c.course_id) || c.course_id}</td>
                      <td>{c.user_count}</td>
                      <td>{c.material_count}</td>
                      <td>{c.knowledge_point_count}</td>
                      <td>{c.task_count}</td>
                      <td>{c.question_count}</td>
                      <td>{c.average_mastery > 0 ? `${c.average_mastery}%` : "-"}</td>
                    </tr>
                  ))}
                  {courses.length === 0 && (
                    <tr><td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>暂无课程数据</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Plans ── */}
      {tab === "plans" && (
        <div className="admin-tab-content">
          {/* Stat cards */}
          <div className="admin-stat-row">
            {[
              { label: "免费用户", value: planCounts.free, icon: "🆓", bg: "#f0fdf4" },
              { label: "专业版用户", value: planCounts.pro, icon: "💎", bg: "#fef3c7" },
              { label: "管理员", value: planCounts.admin, icon: "🛡️", bg: "#faf5ff" },
            ].map(({ label, value, icon, bg }) => (
              <div key={label} className="admin-stat-card-v2">
                <div className="admin-stat-top"><span className="admin-stat-label">{label}</span><span className="admin-stat-icon-v2" style={{ background: bg }}>{icon}</span></div>
                <div className="admin-stat-value-v2">{value ?? 0}</div>
              </div>
            ))}
          </div>
          {/* Edit form */}
          <div className="admin-card" style={{ marginBottom: 18 }}>
            <h4 style={{ margin: "0 0 12px", fontSize: "0.95rem", fontWeight: 700 }}>修改用户套餐</h4>
            <div className="admin-plan-form">
              <input className="field" placeholder="目标用户名" value={planEditForm.username} onChange={(e) => setPlanEditForm((p) => ({ ...p, username: e.target.value }))} />
              <select className="field" value={planEditForm.plan} onChange={(e) => setPlanEditForm((p) => ({ ...p, plan: e.target.value }))}>
                <option value="free">免费版</option><option value="pro">专业版</option><option value="admin">管理员</option>
              </select>
              <input className="field" type="datetime-local" placeholder="到期时间（可选）" value={planEditForm.expire} onChange={(e) => setPlanEditForm((p) => ({ ...p, expire: e.target.value }))} />
              <button className="primary-button" onClick={handlePlanUpdate} disabled={planSaving}>{planSaving ? "修改中..." : "确认修改"}</button>
            </div>
            {planMsg && <p style={{ marginTop: 12, color: planMsg.includes("失败") ? "#ef4444" : "#059669", fontSize: 13 }}>{planMsg}</p>}
          </div>
          {/* User list */}
          {planLoading ? <div className="empty-state">加载中...</div> : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead><tr><th>用户名</th><th>当前套餐</th><th>到期时间</th><th>创建时间</th><th>操作</th></tr></thead>
                <tbody>
                  {planUsers.items.map((u) => (
                    <tr key={u.username}>
                      <td>{u.username}</td>
                      <td><span className={`plan-tag plan-${u.plan}`}>{PLAN_NAMES[u.plan] || u.plan}</span></td>
                      <td>{u.plan_expires_at ? new Date(u.plan_expires_at).toLocaleDateString("zh-CN") : "永久"}</td>
                      <td>{u.created_at ? new Date(u.created_at).toLocaleDateString("zh-CN") : "-"}</td>
                      <td>{canManageUserPlan(u) && <button className="ghost-button compact" onClick={() => setPlanEditForm({ username: u.username, plan: u.plan || "free", expire: u.plan_expires_at || "" })}>修改套餐</button>}</td>
                    </tr>
                  ))}
                  {planUsers.items.length === 0 && <tr><td colSpan={5} style={{ textAlign: "center", color: "#6b7280" }}>暂无用户</td></tr>}
                </tbody>
              </table>
              <div className="admin-pagination" style={{ marginTop: 12 }}>
                <button disabled={planUsers.page <= 1} onClick={() => fetchPlanUsers(planUsers.page - 1)}>上一页</button>
                <span className="admin-page-info">{planUsers.page} / {Math.max(1, Math.ceil(planUsers.total / 20))}</span>
                <button disabled={planUsers.page >= Math.ceil(planUsers.total / 20)} onClick={() => fetchPlanUsers(planUsers.page + 1)}>下一页</button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Audit Logs ── */}
      {tab === "auditLogs" && (
        <div className="admin-tab-content">
          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-stat-grid">
                <div className="admin-stat-card"><span>今日操作</span><strong>{auditLogs.summary?.today_total ?? 0}</strong></div>
                <div className="admin-stat-card"><span>今日高风险</span><strong>{auditLogs.summary?.today_high_risk ?? 0}</strong></div>
                <div className="admin-stat-card"><span>角色变更</span><strong>{auditLogs.summary?.admin_role_changes ?? 0}</strong></div>
                <div className="admin-stat-card"><span>配置变更</span><strong>{auditLogs.summary?.settings_changes ?? 0}</strong></div>
                <div className="admin-stat-card"><span>失败操作</span><strong>{auditLogs.summary?.failed ?? 0}</strong></div>
              </div>
              <div className="admin-filters">
                <input className="field" placeholder="操作人" value={auditFilters.actor} onChange={(e) => setAuditFilters((prev) => ({ ...prev, actor: e.target.value }))} />
                <input className="field" placeholder="操作类型" value={auditFilters.action} onChange={(e) => setAuditFilters((prev) => ({ ...prev, action: e.target.value }))} />
                <select className="field" value={auditFilters.target_type} onChange={(e) => setAuditFilters((prev) => ({ ...prev, target_type: e.target.value }))}>
                  <option value="">全部目标</option>
                  {AUDIT_TARGET_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                </select>
                <input className="field" placeholder="关键词" value={auditFilters.keyword} onChange={(e) => setAuditFilters((prev) => ({ ...prev, keyword: e.target.value }))} />
                <input className="field" type="date" value={auditFilters.start_date} onChange={(e) => setAuditFilters((prev) => ({ ...prev, start_date: e.target.value }))} />
                <input className="field" type="date" value={auditFilters.end_date} onChange={(e) => setAuditFilters((prev) => ({ ...prev, end_date: e.target.value }))} />
                <button className="primary-button" onClick={() => fetchAuditLogs(1)}>查询</button>
                <button className="ghost-button" onClick={() => { setAuditFilters({ actor: "", action: "", target_type: "", keyword: "", start_date: "", end_date: "" }); setTimeout(() => fetchAuditLogs(1), 0); }}>重置</button>
                {hasPermission("audit_logs.export") && (
                  <button className="primary-button" onClick={handleAuditExport} disabled={auditExporting}>{auditExporting ? "导出中..." : "导出 CSV"}</button>
                )}
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>操作人</th>
                      <th>操作类型</th>
                      <th>目标对象</th>
                      <th>结果</th>
                      <th>IP</th>
                      <th>详情</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.items.map((log, i) => (
                      <tr key={log.id || i}>
                        <td>{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
                        <td>{log.admin_username}</td>
                        <td>{log.action_label || log.action}</td>
                        <td>{formatAuditTarget(log)}</td>
                        <td><span className={`status-pill ${log.result === "success" ? "status-pill--ok" : "status-pill--fail"}`}>{log.result || "success"}</span></td>
                        <td>{log.ip || "-"}</td>
                        <td><button className="ghost-button compact" onClick={() => setAuditDetail(log)}>查看</button></td>
                      </tr>
                    ))}
                    {auditLogs.items.length === 0 && (
                      <tr><td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>暂无操作记录</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {renderPagination(auditLogs, fetchAuditLogs)}
            </>
          )}
        </div>
      )}

      {/* ── Report Shares ── */}
      {tab === "reportShares" && (
        <div className="admin-tab-content">
          {hasPermission("batch.reports") && selectedShares.size > 0 && (
            <div className="admin-batch-bar">
              <span>已选择 {selectedShares.size} 项</span>
              <button className="primary-button compact" style={{ color: "#059669" }} onClick={() => batchShareStatus("approved")}>批量通过</button>
              <button className="ghost-button compact" style={{ color: "#ef4444" }} onClick={() => batchShareStatus("revoked")}>批量撤销</button>
              <button className="ghost-button compact" onClick={() => batchShareStatus("pending")}>批量恢复</button>
              <button className="ghost-button compact" onClick={() => clearSelection(setSelectedShares)}>清空选择</button>
            </div>
          )}
          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      {hasPermission("batch.reports") && <th><input type="checkbox" onChange={(e) => e.target.checked ? selectAll(setSelectedShares, reportShares.items.map((s) => s.id)) : clearSelection(setSelectedShares)} /></th>}
                      <th>报告标题</th>
                      <th>用户</th>
                      <th>状态</th>
                      <th>浏览量</th>
                      <th>创建时间</th>
                      <th>撤销时间</th>
                      <th>最近查看</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportShares.items.map((s) => (
                      <tr key={s.id}>
                        {hasPermission("batch.reports") && <td><input type="checkbox" checked={selectedShares.has(s.id)} onChange={() => toggleSelect(setSelectedShares, s.id)} /></td>}
                        <td title={s.title}>{s.title && s.title.length > 30 ? s.title.slice(0, 30) + "..." : (s.title || "-")}</td>
                        <td>{s.username}</td>
                        <td><span className={`status-pill ${s.is_active ? "status-pill--ok" : "status-pill--fail"}`}>{s.is_active ? "已通过" : "已撤销"}</span></td>
                        <td>{s.view_count || 0}</td>
                        <td>{s.created_at ? new Date(s.created_at).toLocaleString("zh-CN") : "-"}</td>
                        <td>{s.revoked_at ? new Date(s.revoked_at).toLocaleString("zh-CN") : "-"}</td>
                        <td>{s.last_viewed_at ? new Date(s.last_viewed_at).toLocaleString("zh-CN") : "-"}</td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          {hasPermission("report_shares.moderate") && (
                            s.is_active ? (
                              <button className="ghost-button compact" style={{ color: "#ef4444" }} onClick={() => handleShareStatus(s, "revoked")}>撤销</button>
                            ) : (
                              <button className="ghost-button compact" style={{ color: "#059669" }} onClick={() => handleShareStatus(s, "approved")}>恢复</button>
                            )
                          )}
                        </td>
                      </tr>
                    ))}
                    {reportShares.items.length === 0 && (
                      <tr><td colSpan={8} style={{ textAlign: "center", color: "#6b7280" }}>暂无分享记录</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {renderPagination(reportShares, fetchReportShares)}
            </>
          )}
        </div>
      )}

      {/* ── Backups ── */}
      {tab === "backups" && (
        <div className="admin-tab-content">
          <div className="backup-info-card">
            <h3>数据备份</h3>
            <p>仅超级管理员可创建、下载和删除数据库备份。备份文件可能包含用户数据、AI 日志和资料文本，请妥善保管。</p>
          </div>
          <div className="admin-filters">
            {hasPermission("backups.create") && (
              <button className="primary-button" onClick={createBackup} disabled={backupCreating}>
                {backupCreating ? "创建中..." : "创建备份"}
              </button>
            )}
            <button className="ghost-button" onClick={fetchBackups} disabled={backupLoading}>
              {backupLoading ? "刷新中..." : "刷新列表"}
            </button>
            {backupActionMsg && <span className="backup-action-msg">{backupActionMsg}</span>}
          </div>
          {backupLoading ? <div className="empty-state">加载中...</div> : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>文件名</th>
                    <th>大小</th>
                    <th>创建时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {backups.items.map((backup) => (
                    <tr key={backup.filename}>
                      <td>{backup.filename}</td>
                      <td>{backup.size_label || formatSize(backup.size_bytes)}</td>
                      <td>{backup.created_at ? new Date(backup.created_at).toLocaleString("zh-CN") : "-"}</td>
                      <td>
                        {hasPermission("backups.download") && (
                          <button className="ghost-button compact" disabled={backupBusyFile === backup.filename} onClick={() => downloadBackup(backup)}>下载</button>
                        )}
                        {hasPermission("backups.delete") && (
                          <button className="ghost-button compact" style={{ color: "#ef4444", marginLeft: 4 }} disabled={backupBusyFile === backup.filename} onClick={() => deleteBackup(backup)}>删除</button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {backups.items.length === 0 && (
                    <tr><td colSpan={4} style={{ textAlign: "center", color: "#6b7280" }}>暂无备份文件</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Model Config ── */}
      {tab === "modelConfig" && (
        <div className="admin-tab-content">
          {modelConfigLoading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="backup-info-card">
                <h3>模型配置</h3>
                <p>API Key 仍由服务器环境变量管理，当前页面不会展示或保存密钥。</p>
              </div>
              <div className="admin-stat-grid">
                <div className="admin-stat-card">
                  <span>DeepSeek</span>
                  <strong>{modelConfig?.status?.deepseek?.configured ? "已配置" : "未配置"}</strong>
                </div>
                <div className="admin-stat-card">
                  <span>Qwen</span>
                  <strong>{modelConfig?.status?.qwen?.configured ? "已配置" : "未配置"}</strong>
                </div>
              </div>
              <div className="model-config-grid">
                <section className="model-config-panel">
                  <h3>文本模型</h3>
                  <label className="field-label">模型提供商</label>
                  <select className="field" value={modelConfigForm.ai_text_model_provider || "deepseek"} onChange={(e) => updateModelConfigForm("ai_text_model_provider", e.target.value)}>
                    <option value="deepseek">deepseek</option>
                  </select>
                  <label className="field-label">模型名称</label>
                  <input className="field" value={modelConfigForm.ai_text_model_name || ""} onChange={(e) => updateModelConfigForm("ai_text_model_name", e.target.value)} placeholder="deepseek-chat" />
                  <label className="field-label">temperature（0 - 1.5）</label>
                  <input className="field" type="number" min="0" max="1.5" step="0.1" value={modelConfigForm.ai_text_temperature || "0.3"} onChange={(e) => updateModelConfigForm("ai_text_temperature", e.target.value)} />
                  <label className="field-label">max_tokens（256 - 8000）</label>
                  <input className="field" type="number" min="256" max="8000" step="1" value={modelConfigForm.ai_text_max_tokens || "2000"} onChange={(e) => updateModelConfigForm("ai_text_max_tokens", e.target.value)} />
                </section>
                <section className="model-config-panel">
                  <h3>视觉解析</h3>
                  <label className="field-label">视觉提供商</label>
                  <select className="field" value={modelConfigForm.ai_vision_model_provider || "qwen"} onChange={(e) => updateModelConfigForm("ai_vision_model_provider", e.target.value)}>
                    <option value="qwen">qwen</option>
                  </select>
                  <label className="model-toggle-row">
                    <input type="checkbox" checked={(modelConfigForm.ai_vision_enabled || "true") === "true"} onChange={(e) => updateModelConfigForm("ai_vision_enabled", e.target.checked ? "true" : "false")} />
                    <span>启用 Qwen 视觉解析</span>
                  </label>
                  <label className="model-toggle-row">
                    <input type="checkbox" checked={(modelConfigForm.ai_pdf_scan_parse_enabled || "true") === "true"} onChange={(e) => updateModelConfigForm("ai_pdf_scan_parse_enabled", e.target.checked ? "true" : "false")} />
                    <span>启用扫描 PDF 视觉解析</span>
                  </label>
                  <label className="field-label">扫描 PDF 最大页数（1 - 20）</label>
                  <input className="field" type="number" min="1" max="20" step="1" value={modelConfigForm.ai_pdf_scan_max_pages || "10"} onChange={(e) => updateModelConfigForm("ai_pdf_scan_max_pages", e.target.value)} />
                </section>
              </div>
              <div className="model-config-panel">
                <h3>功能策略</h3>
                <label className="model-toggle-row">
                  <input type="checkbox" checked={(modelConfigForm.ai_chat_enabled_model_config || "true") === "true"} onChange={(e) => updateModelConfigForm("ai_chat_enabled_model_config", e.target.checked ? "true" : "false")} />
                  <span>AI 问答使用模型配置</span>
                </label>
                <label className="model-toggle-row">
                  <input type="checkbox" checked={(modelConfigForm.ai_report_enabled_model_config || "true") === "true"} onChange={(e) => updateModelConfigForm("ai_report_enabled_model_config", e.target.checked ? "true" : "false")} />
                  <span>学习报告使用模型配置</span>
                </label>
                <label className="model-toggle-row">
                  <input type="checkbox" checked={(modelConfigForm.ai_question_generation_enabled_model_config || "true") === "true"} onChange={(e) => updateModelConfigForm("ai_question_generation_enabled_model_config", e.target.checked ? "true" : "false")} />
                  <span>题目生成使用模型配置</span>
                </label>
              </div>
              <div className="admin-filters">
                {hasPermission("model_config.manage") && (
                  <button className="primary-button" onClick={saveModelConfig} disabled={modelConfigSaving}>{modelConfigSaving ? "保存中..." : "保存配置"}</button>
                )}
                <button className="ghost-button" onClick={fetchModelConfig}>刷新</button>
                {modelConfigMsg && <span className="backup-action-msg">{modelConfigMsg}</span>}
              </div>
            </>
          )}
        </div>
      )}

      {/* ── System Health ── */}
      {tab === "systemHealth" && (
        <div className="admin-tab-content">
          {systemHealth ? (
            <>
              {/* Health cards */}
              <div className="admin-stat-row" style={{ marginBottom: 16 }}>
                {[
                  { label: "系统状态", value: systemHealth.status === "ok" ? "正常" : "异常", icon: systemHealth.status === "ok" ? "✅" : "⚠️", bg: systemHealth.status === "ok" ? "#f0fdf4" : "#fef3c7" },
                  { label: "数据库", value: "正常", icon: "🗄️", bg: "#eff6ff", sub: `${systemHealth.database?.users_count || 0} 用户 / ${systemHealth.database?.materials_count || 0} 资料 / ${systemHealth.database?.chunks_count || 0} chunks` },
                  { label: "上传目录", value: systemHealth.storage?.upload_dir_exists ? "可用" : "不可用", icon: systemHealth.storage?.upload_dir_exists ? "✅" : "❌", bg: systemHealth.storage?.upload_dir_exists ? "#f0fdf4" : "#fef2f2" },
                  { label: "DeepSeek", value: systemHealth.ai_services?.deepseek?.configured ? "已配置" : "未配置", icon: systemHealth.ai_services?.deepseek?.configured ? "✅" : "⚠️", bg: systemHealth.ai_services?.deepseek?.configured ? "#f0fdf4" : "#fef3c7", sub: systemHealth.ai_services?.deepseek?.recent_failed > 0 ? `${systemHealth.ai_services.deepseek.recent_failed} 失败` : "" },
                  { label: "Qwen 图片解析", value: systemHealth.ai_services?.qwen?.configured ? "已配置" : "未配置", icon: systemHealth.ai_services?.qwen?.configured ? "✅" : "⚠️", bg: systemHealth.ai_services?.qwen?.configured ? "#f0fdf4" : "#fef3c7" },
                ].map(({ label, value, icon, bg, sub }) => (
                  <div key={label} className="admin-stat-card-v2">
                    <div className="admin-stat-top"><span className="admin-stat-label">{label}</span><span className="admin-stat-icon-v2" style={{ background: bg }}>{icon}</span></div>
                    <div className="admin-stat-value-v2" style={{ fontSize: "1.1rem" }}>{value}</div>
                    {sub && <div className="admin-stat-sub">{sub}</div>}
                  </div>
                ))}
              </div>

              {/* Alerts */}
              {(systemHealth.alerts || []).length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  {systemHealth.alerts.map((a, i) => (
                    <div key={i} style={{ padding: "8px 14px", marginBottom: 6, borderRadius: 10, background: a.level === "warning" ? "#fef3c7" : "#eff6ff", border: "1px solid " + (a.level === "warning" ? "#fde68a" : "#bfdbfe"), fontSize: "0.8rem", color: a.level === "warning" ? "#92400e" : "#1e40af" }}>
                      <strong>{a.title}</strong> — {a.message}
                    </div>
                  ))}
                </div>
              )}
              {(!systemHealth.alerts || systemHealth.alerts.length === 0) && (
                <div style={{ padding: "10px 14px", marginBottom: 16, borderRadius: 10, background: "#f0fdf4", border: "1px solid #bbf7d0", fontSize: "0.8rem", color: "#166534" }}>✅ 系统运行正常，未发现明显异常</div>
              )}

              {/* Material issues */}
              <div className="admin-card">
                <div className="admin-chart-header">
                  <h4>资料解析异常</h4>
                  <select className="field compact" value={materialIssueType} onChange={(e) => { setMaterialIssueType(e.target.value); fetchMaterialIssues(1); }}>
                    <option value="all">全部</option><option value="empty_text">解析文本为空</option><option value="no_chunks">未建立索引</option>
                  </select>
                </div>
                <div className="admin-table-wrap">
                  <table className="admin-table-v2">
                    <thead><tr><th>文件名</th><th>用户</th><th>课程</th><th>问题类型</th><th>文本长度</th><th>Chunks</th><th>操作</th></tr></thead>
                    <tbody>
                      {materialIssues.items.map((m) => (
                        <tr key={m.id}>
                          <td title={m.filename}>{m.filename && m.filename.length > 30 ? m.filename.slice(0, 30) + "..." : m.filename}</td>
                          <td>{m.username}</td><td>{m.course_name || "-"}</td>
                          <td><span className={`status-pill ${m.issue_type === "empty_text" ? "status-pill--fail" : "status-pill--ok"}`}>{m.issue_label}</span></td>
                          <td>{m.extracted_text_length}</td><td>{m.chunk_count}</td>
                          <td style={{ whiteSpace: "nowrap" }}>
                            {hasPermission("materials.reindex") && (
                              <button className="ghost-button compact" disabled={reindexingId === m.id} onClick={() => handleMaterialReindex(m)}>{reindexingId === m.id ? "索引中..." : "重索引"}</button>
                            )}
                            {hasPermission("materials.delete") && (
                              <button className="ghost-button compact" style={{ color: "#ef4444", marginLeft: 4 }} onClick={() => handleMaterialDelete(m)}>删除</button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {materialIssues.items.length === 0 && <tr><td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>暂无资料异常</td></tr>}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-state">加载系统健康数据...</div>
          )}
        </div>
      )}

      {/* ── Audit Log Detail Modal ── */}
      {auditDetail && (
        <div className="admin-modal-overlay" onClick={() => setAuditDetail(null)}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 640 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3>审计详情</h3>
              <button className="modal-close" onClick={() => setAuditDetail(null)}>&times;</button>
            </div>
            <div className="admin-detail-grid">
              <div><span>时间：</span>{auditDetail.created_at ? new Date(auditDetail.created_at).toLocaleString("zh-CN") : "-"}</div>
              <div><span>操作人：</span>{auditDetail.admin_username || "-"}</div>
              <div><span>操作：</span>{auditDetail.action_label || auditDetail.action || "-"}</div>
              <div><span>目标：</span>{formatAuditTarget(auditDetail)}</div>
              <div><span>结果：</span><span className={`status-pill ${auditDetail.result === "success" ? "status-pill--ok" : "status-pill--fail"}`}>{auditDetail.result || "success"}</span></div>
              <div><span>IP：</span>{auditDetail.ip || "-"}</div>
            </div>
            <div className="admin-detail-section">
              <h4>详情</h4>
              <pre className="audit-detail-json">{formatAuditDetails(auditDetail.details) || auditDetail.detail || "-"}</pre>
            </div>
            <div style={{ textAlign: "right", marginTop: 16 }}>
              <button className="ghost-button" onClick={() => setAuditDetail(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* ── AI Log Detail Modal ── */}
      {aiLogDetail && (
        <div className="admin-modal-overlay" onClick={() => setAiLogDetail(null)}>
          <div className="admin-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3>AI 调用详情</h3>
              <button className="modal-close" onClick={() => setAiLogDetail(null)}>&times;</button>
            </div>
            <div className="admin-detail-grid">
              <div><span>用户：</span>{aiLogDetail.username}</div>
              <div><span>功能：</span>{FEATURE_LABELS[aiLogDetail.feature] || aiLogDetail.feature}</div>
              <div><span>状态：</span><span className={`status-pill ${aiLogDetail.status === "success" ? "status-pill--ok" : "status-pill--fail"}`}>{aiLogDetail.status === "success" ? "成功" : "失败"}</span></div>
              <div><span>模型：</span>{aiLogDetail.model || "未知"}</div>
              <div><span>Tokens：</span>{aiLogDetail.estimated_tokens || 0}</div>
              <div><span>时间：</span>{aiLogDetail.created_at ? new Date(aiLogDetail.created_at).toLocaleString("zh-CN") : "-"}</div>
              {aiLogDetail.status !== "success" && (
                <div style={{ gridColumn: "1 / -1" }}>
                  <span>错误信息：</span>
                  <pre style={{ margin: "4px 0 0", padding: 10, background: "#fef2f2", borderRadius: 8, fontSize: 12, color: "#991b1b", whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>
                    {aiLogDetail.error_message || "暂无错误详情"}
                  </pre>
                </div>
              )}
            </div>
            <div style={{ textAlign: "right", marginTop: 16 }}>
              <button className="ghost-button" onClick={() => setAiLogDetail(null)}>关闭</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Platform Config ── */}
      {tab === "platformConfig" && (
        <div className="admin-tab-content">
          {/* Announcements */}
          <div className="admin-card">
            <div className="admin-chart-header">
              <h4>公告管理</h4>
              {hasPermission("announcements.manage") && (
                <button className="primary-button compact" onClick={() => { setEditingAnnounceId(null); setAnnounceForm({ title: "", content: "", type: "info", target: "all", is_active: 1 }); setShowAnnounceForm(true); }}>+ 新建公告</button>
              )}
            </div>
            {hasPermission("announcements.manage") && showAnnounceForm && (
              <div style={{ marginBottom: 16, padding: 16, background: "#f8fafc", borderRadius: 10, border: "1px solid #e2e8f0" }}>
                <input className="field" placeholder="公告标题" value={announceForm.title} onChange={(e) => setAnnounceForm((f) => ({ ...f, title: e.target.value }))} style={{ marginBottom: 8 }} />
                <textarea className="field" rows={3} placeholder="公告内容" value={announceForm.content} onChange={(e) => setAnnounceForm((f) => ({ ...f, content: e.target.value }))} style={{ marginBottom: 8 }} />
                <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
                  <select className="field compact" value={announceForm.type} onChange={(e) => setAnnounceForm((f) => ({ ...f, type: e.target.value }))}>
                    <option value="info">普通通知</option><option value="warning">重要提醒</option><option value="success">成功提示</option><option value="danger">风险警告</option>
                  </select>
                  <select className="field compact" value={announceForm.target} onChange={(e) => setAnnounceForm((f) => ({ ...f, target: e.target.value }))}>
                    <option value="all">全部用户</option><option value="free">免费用户</option><option value="pro">专业版用户</option><option value="admin">管理员</option>
                  </select>
                </div>
                <button className="primary-button compact" onClick={saveAnnouncement}>{editingAnnounceId ? "保存修改" : "创建公告"}</button>
                <button className="ghost-button compact" style={{ marginLeft: 8 }} onClick={() => setShowAnnounceForm(false)}>取消</button>
              </div>
            )}
            <div className="admin-table-wrap">
              <table className="admin-table-v2">
                <thead><tr><th>标题</th><th>类型</th><th>目标</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead>
                <tbody>
                  {announcements.map((a) => (
                    <tr key={a.id}>
                      <td>{a.title.length > 30 ? a.title.slice(0, 30) + "..." : a.title}</td>
                      <td><span className={`status-pill ${a.type === "danger" ? "status-pill--fail" : a.type === "warning" ? "status-pill--ok" : a.type === "success" ? "status-pill--ok" : "status-pill--ok"}`}>{a.type}</span></td>
                      <td>{a.target}</td>
                      <td><span className={`status-pill ${a.is_active ? "status-pill--ok" : "status-pill--fail"}`}>{a.is_active ? "启用" : "停用"}</span></td>
                      <td>{a.created_at ? new Date(a.created_at).toLocaleString("zh-CN") : "-"}</td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {hasPermission("announcements.manage") && (
                          <>
                            <button className="ghost-button compact" onClick={() => { setEditingAnnounceId(a.id); setAnnounceForm({ title: a.title, content: a.content, type: a.type, target: a.target, is_active: a.is_active }); setShowAnnounceForm(true); }}>编辑</button>
                            <button className="ghost-button compact" onClick={() => toggleAnnounceStatus(a)}>{a.is_active ? "停用" : "启用"}</button>
                            <button className="ghost-button compact" style={{ color: "#ef4444" }} onClick={() => deleteAnnouncement(a)}>删除</button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                  {announcements.length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>暂无公告</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          {/* Feature Toggles */}
          <div className="admin-card">
            <div className="admin-chart-header"><h4>功能开关</h4></div>
            {[
              { key: "feature_ai_chat_enabled", label: "AI 问答", desc: "控制AI问答功能是否可用" },
              { key: "feature_material_upload_enabled", label: "资料上传", desc: "控制资料上传功能是否可用" },
              { key: "feature_code_studio_enabled", label: "编程助手", desc: "控制编程助手功能是否可用" },
              { key: "feature_practice_center_enabled", label: "练习中心", desc: "控制练习中心功能是否可用" },
              { key: "feature_report_share_enabled", label: "报告分享", desc: "控制报告分享功能是否可用" },
            ].map(({ key, label, desc }) => (
              <div key={key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderBottom: "1px solid #f1f5f9" }}>
                <div><div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#1e293b" }}>{label}</div><div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{desc}</div></div>
                <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <span style={{ fontSize: "0.8rem", color: settings[key] === "true" ? "#16a34a" : "#94a3b8" }}>{settings[key] === "true" ? "已开启" : "已关闭"}</span>
                  <input type="checkbox" className="config-input" name={key} defaultChecked={settings[key] === "true"} disabled={!hasPermission("settings.manage")} style={{ width: 40, height: 22 }} />
                </label>
              </div>
            ))}
          </div>

          {/* AI Quota */}
          <div className="admin-card">
            <div className="admin-chart-header"><h4>AI 额度配置</h4></div>
            {[
              { key: "limit_free_daily_ai_calls", label: "免费版每日 AI 调用", desc: "免费用户每天可使用的AI调用总数" },
              { key: "limit_pro_daily_ai_calls", label: "专业版每日 AI 调用", desc: "专业版用户每天可使用的AI调用总数" },
              { key: "limit_admin_daily_ai_calls", label: "管理员每日 AI 调用", desc: "管理员每天可使用的AI调用总数（-1 无限制）" },
            ].map(({ key, label, desc }) => (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderBottom: "1px solid #f1f5f9" }}>
                <div style={{ flex: 1 }}><div style={{ fontWeight: 600, fontSize: "0.9rem", color: "#1e293b" }}>{label}</div><div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{desc}</div></div>
                <input type="number" className="field config-input" name={key} defaultValue={settings[key] || "5"} disabled={!hasPermission("settings.manage")} style={{ width: 100, textAlign: "center" }} />
              </div>
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}>
            {hasPermission("settings.manage") && (
              <button className="primary-button" onClick={saveSettings} disabled={configSaving}>{configSaving ? "保存中..." : "保存所有配置"}</button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
