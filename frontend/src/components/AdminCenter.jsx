import { useEffect, useMemo, useState } from "react";
import { getSubjectLabel } from "../courseOptions.js";

const API_BASE = "/api";

const TABS = [
  { key: "overview", label: "总览" },
  { key: "users", label: "用户管理" },
  { key: "aiLogs", label: "AI 使用日志" },
  { key: "materials", label: "资料管理" },
  { key: "courses", label: "课程统计" },
  { key: "plans", label: "套餐管理" },
  { key: "auditLogs", label: "操作记录" },
  { key: "reportShares", label: "报告分享" },
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

  // Audit logs
  const [auditLogs, setAuditLogs] = useState({ items: [], total: 0, page: 1 });

  // Report shares
  const [reportShares, setReportShares] = useState({ items: [], total: 0, page: 1 });

  const isAdmin = user?.is_admin;

  useEffect(() => {
    if (!isAdmin) return;
    if (tab === "overview") { fetchDashboard(); fetchTrendData(trendDays); }
    if (tab === "courses") fetchCourses();
    if (tab === "plans") fetchPlanUsers(1);
  }, [tab, isAdmin]);

  // ── helpers ──
  const adminParam = `admin_username=${encodeURIComponent(user.username)}`;
  const getJson = async (url) => {
    const res = await fetch(url);
    if (!res.ok) { const body = await res.json().catch(()=>({})); throw new Error(body.detail || `请求失败 (${res.status})`); }
    return res.json();
  };

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

  // ── AI log detail ──
  const fetchAiLogDetail = (log) => { setAiLogDetail(log); };

  // ── Trend data ──
  const fetchTrendData = async (days) => {
    try {
      const data = await getJson(`${API_BASE}/admin/usage-trend?${adminParam}&days=${days}`);
      setTrendData(data);
    } catch { /* use fallback */ }
  };

  if (!isAdmin) {
    return (
      <div className="empty-state" style={{ padding: 48 }}>
        <h2>无权限访问管理中心</h2>
        <p>仅管理员可访问此页面。</p>
      </div>
    );
  }

  // ── Overview ──

  const fetchDashboard = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getJson(`${API_BASE}/admin/dashboard?${adminParam}`);
      setDashboard(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
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
      const data = await getJson(`${API_BASE}/admin/audit-logs?${params}`);
      setAuditLogs(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
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

  // ── activate tab ──

  const activateTab = (key) => {
    setTab(key);
    setError("");
    setUserDetail(null);
    if (key === "users") fetchUsers(1);
    if (key === "aiLogs") fetchAiLogs(1);
    if (key === "materials") fetchMaterials(1);
    if (key === "auditLogs") fetchAuditLogs(1);
    if (key === "reportShares") fetchReportShares(1);
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

  // Trend range selector
  const TREND_RANGES = [
    { value: 7, label: "近 7 天" },
    { value: 30, label: "近 30 天" },
    { value: 90, label: "近 90 天" },
  ];
  const [trendDays, setTrendDays] = useState(7);

  // Build trend bars from recent logs based on selected range
  const trendBars = useMemo(() => {
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
  }, [dashboard, trendDays, trendData]);

  // ── render ──
  return (
    <div className="admin-center-v2">

      {/* ── Tabs ── */}
      <div className="admin-dash-tabs">
        {TABS.map((t) => (
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

          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>用户名</th>
                      <th>昵称</th>
                      <th>套餐</th>
                      <th>到期</th>
                      <th>今日 AI</th>
                      <th>累计 AI</th>
                      <th>资料</th>
                      <th>知识点</th>
                      <th>任务</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.items.map((u) => (
                      <tr key={u.username}>
                        <td>{u.username}</td>
                        <td>{u.nickname || "-"}</td>
                        <td><span className={`plan-tag plan-${u.plan}`}>{PLAN_NAMES[u.plan] || u.plan}</span></td>
                        <td>{u.plan_expires_at ? new Date(u.plan_expires_at).toLocaleDateString("zh-CN") : "-"}</td>
                        <td>{u.today_ai_call_count}</td>
                        <td>{u.ai_call_count}</td>
                        <td>{u.material_count}</td>
                        <td>{u.knowledge_point_count}</td>
                        <td>{u.task_count}</td>
                        <td>
                          <button className="ghost-button compact" onClick={() => fetchUserDetail(u.username)}>
                            详情
                          </button>
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

          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>文件名</th>
                      <th>用户</th>
                      <th>课程</th>
                      <th>类型</th>
                      <th>大小</th>
                      <th>绑定知识点</th>
                      <th>解析状态</th>
                      <th>上传时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {materials.items.map((m) => (
                      <tr key={m.material_id}>
                        <td title={m.original_filename}>{m.original_filename.length > 30 ? m.original_filename.slice(0, 30) + "..." : m.original_filename}</td>
                        <td>{m.username}</td>
                        <td>{getSubjectLabel(m.subject) || m.subject || "-"}</td>
                        <td>{m.file_type}</td>
                        <td>{formatSize(m.file_size)}</td>
                        <td>{m.knowledge_link_count}</td>
                        <td>{m.parse_status === "success" ? "成功" : m.parse_status || "-"}</td>
                        <td>{m.created_at ? new Date(m.created_at).toLocaleString("zh-CN") : "-"}</td>
                      </tr>
                    ))}
                    {materials.items.length === 0 && (
                      <tr><td colSpan={8} style={{ textAlign: "center", color: "#6b7280" }}>暂无资料</td></tr>
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
          {loading ? <div className="empty-state">加载中...</div> : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>课程</th>
                    <th>用户数</th>
                    <th>资料数</th>
                    <th>知识点数</th>
                    <th>任务数</th>
                    <th>题目数</th>
                    <th>平均掌握度</th>
                  </tr>
                </thead>
                <tbody>
                  {courses.map((c) => (
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
                      <td><button className="ghost-button compact" onClick={() => setPlanEditForm({ username: u.username, plan: u.plan || "free", expire: u.plan_expires_at || "" })}>修改套餐</button></td>
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
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>管理员</th>
                      <th>操作</th>
                      <th>目标类型</th>
                      <th>目标用户</th>
                      <th>详情</th>
                      <th>时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditLogs.items.map((log, i) => (
                      <tr key={i}>
                        <td>{log.admin_username}</td>
                        <td>{log.action}</td>
                        <td>{log.target_type || "-"}</td>
                        <td>{log.target_username || "-"}</td>
                        <td>{log.detail || "-"}</td>
                        <td>{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
                      </tr>
                    ))}
                    {auditLogs.items.length === 0 && (
                      <tr><td colSpan={6} style={{ textAlign: "center", color: "#6b7280" }}>暂无操作记录</td></tr>
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
          {loading ? <div className="empty-state">加载中...</div> : (
            <>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>报告标题</th>
                      <th>用户</th>
                      <th>状态</th>
                      <th>浏览量</th>
                      <th>创建时间</th>
                      <th>撤销时间</th>
                      <th>最近查看</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportShares.items.map((s) => (
                      <tr key={s.id}>
                        <td title={s.title}>{s.title && s.title.length > 30 ? s.title.slice(0, 30) + "..." : (s.title || "-")}</td>
                        <td>{s.username}</td>
                        <td><span className={`status-tag ${s.is_active ? "status-success" : "status-failed"}`}>{s.is_active ? "活跃" : "已撤销"}</span></td>
                        <td>{s.view_count || 0}</td>
                        <td>{s.created_at ? new Date(s.created_at).toLocaleString("zh-CN") : "-"}</td>
                        <td>{s.revoked_at ? new Date(s.revoked_at).toLocaleString("zh-CN") : "-"}</td>
                        <td>{s.last_viewed_at ? new Date(s.last_viewed_at).toLocaleString("zh-CN") : "-"}</td>
                      </tr>
                    ))}
                    {reportShares.items.length === 0 && (
                      <tr><td colSpan={7} style={{ textAlign: "center", color: "#6b7280" }}>暂无分享记录</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              {renderPagination(reportShares, fetchReportShares)}
            </>
          )}
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
    </div>
  );
}
