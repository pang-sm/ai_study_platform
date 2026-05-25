import { useEffect, useState } from "react";
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

  // Plan form
  const [planForm, setPlanForm] = useState({ username: "", plan: "free", expire: "" });
  const [planMsg, setPlanMsg] = useState("");

  // Audit logs
  const [auditLogs, setAuditLogs] = useState({ items: [], total: 0, page: 1 });

  const isAdmin = user?.is_admin;

  useEffect(() => {
    if (!isAdmin) return;
    if (tab === "overview") fetchDashboard();
    if (tab === "courses") fetchCourses();
  }, [tab, isAdmin]);

  if (!isAdmin) {
    return (
      <div className="empty-state" style={{ padding: 48 }}>
        <h2>无权限访问管理中心</h2>
        <p>仅管理员可访问此页面。</p>
      </div>
    );
  }

  const adminParam = `admin_username=${encodeURIComponent(user.username)}`;

  // ── helpers ──

  const getJson = async (url) => {
    const res = await fetch(url);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `请求失败 (${res.status})`);
    }
    return res.json();
  };

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

  // ── Plan ──

  const handlePlanUpdate = async () => {
    setPlanMsg("");
    const target = planForm.username.trim();
    if (!target) {
      setPlanMsg("请输入目标用户名");
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/admin/users/${encodeURIComponent(target)}/plan`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            admin_username: user.username,
            plan: planForm.plan,
            plan_expire_at: planForm.expire || null,
          }),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "修改失败");
      setPlanMsg(`已为 ${data.username} 设置套餐：${PLAN_NAMES[data.plan] || data.plan}`);
      fetchDashboard();
      fetchAuditLogs(1);
    } catch (e) {
      setPlanMsg(e.message || "修改失败");
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

  // ── activate tab ──

  const activateTab = (key) => {
    setTab(key);
    setError("");
    setUserDetail(null);
    if (key === "users") fetchUsers(1);
    if (key === "aiLogs") fetchAiLogs(1);
    if (key === "materials") fetchMaterials(1);
    if (key === "auditLogs") fetchAuditLogs(1);
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

  // ── render ──

  return (
    <div className="admin-center">
      <div className="admin-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`admin-tab ${tab === t.key ? "active" : ""}`}
            onClick={() => activateTab(t.key)}
          >
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
              <div className="admin-overview-cards">
                {[
                  ["总用户", dashboard.overview?.total_users],
                  ["免费用户", dashboard.overview?.free_users],
                  ["专业版用户", dashboard.overview?.pro_users],
                  ["管理员", dashboard.overview?.admin_users],
                  ["总资料", dashboard.overview?.total_materials],
                  ["总课程", dashboard.overview?.total_courses],
                  ["总知识点", dashboard.overview?.total_knowledge_points],
                  ["总任务", dashboard.overview?.total_tasks],
                  ["总题目", dashboard.overview?.total_questions],
                  ["今日 AI 调用", dashboard.overview?.today_ai_calls],
                  ["累计 AI 调用", dashboard.overview?.total_ai_calls],
                ].map(([label, value]) => (
                  <div key={label} className="admin-overview-card">
                    <div className="admin-overview-value">{value ?? 0}</div>
                    <div className="admin-overview-label">{label}</div>
                  </div>
                ))}
              </div>

              {(dashboard.today_usage_by_feature || []).length > 0 && (
                <section className="admin-section">
                  <h4>今日按功能调用统计</h4>
                  <div className="admin-feature-stats">
                    {dashboard.today_usage_by_feature.map((item) => (
                      <span key={item.feature} className="admin-feature-tag">
                        {FEATURE_LABELS[item.feature] || item.feature}：{item.count}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {(dashboard.recent_ai_logs || []).length > 0 && (
                <section className="admin-section">
                  <h4>最近 AI 使用记录</h4>
                  <div className="admin-table-wrap">
                    <table className="admin-table">
                      <thead>
                        <tr>
                          <th>用户</th>
                          <th>功能</th>
                          <th>状态</th>
                          <th>Tokens</th>
                          <th>时间</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.recent_ai_logs.map((log, i) => (
                          <tr key={i}>
                            <td>{log.username}</td>
                            <td>{FEATURE_LABELS[log.feature] || log.feature}</td>
                            <td><span className={`status-tag ${log.status === "success" ? "status-success" : "status-failed"}`}>{log.status}</span></td>
                            <td>{log.estimated_tokens || 0}</td>
                            <td>{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}

              {(dashboard.system_notes || []).length > 0 && (
                <section className="admin-section">
                  <h4>系统提示</h4>
                  <ul className="admin-notes">
                    {dashboard.system_notes.map((note, i) => (
                      <li key={i}>{note}</li>
                    ))}
                  </ul>
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
                        <td>{u.plan_expire_at ? new Date(u.plan_expire_at).toLocaleDateString("zh-CN") : "-"}</td>
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
                  <div><span>到期：</span>{userDetail.plan_expire_at ? new Date(userDetail.plan_expire_at).toLocaleDateString("zh-CN") : "无"}</div>
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
                      <tr key={i}>
                        <td>{log.username}</td>
                        <td>{FEATURE_LABELS[log.feature] || log.feature}</td>
                        <td>{log.model || "-"}</td>
                        <td>{log.estimated_tokens || 0}</td>
                        <td><span className={`status-tag ${log.status === "success" ? "status-success" : "status-failed"}`}>{log.status}</span></td>
                        <td>{log.created_at ? new Date(log.created_at).toLocaleString("zh-CN") : "-"}</td>
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
          <p style={{ color: "#6b7280", marginBottom: 16 }}>
            修改用户套餐后，用户刷新页面或重新登录即可生效，无需重新登录。
          </p>
          <div className="admin-plan-form">
            <input
              className="field"
              placeholder="目标用户名"
              value={planForm.username}
              onChange={(e) => setPlanForm((p) => ({ ...p, username: e.target.value }))}
            />
            <select
              className="field"
              value={planForm.plan}
              onChange={(e) => setPlanForm((p) => ({ ...p, plan: e.target.value }))}
            >
              <option value="free">免费版</option>
              <option value="pro">专业版</option>
              <option value="admin">管理员</option>
            </select>
            <input
              className="field"
              type="datetime-local"
              placeholder="到期时间（可选）"
              value={planForm.expire}
              onChange={(e) => setPlanForm((p) => ({ ...p, expire: e.target.value }))}
            />
            <button className="primary-button" onClick={handlePlanUpdate}>确认修改</button>
          </div>
          {planMsg && <p className="admin-plan-msg" style={{ marginTop: 12, color: planMsg.includes("失败") ? "#ef4444" : "#059669" }}>{planMsg}</p>}
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
    </div>
  );
}
