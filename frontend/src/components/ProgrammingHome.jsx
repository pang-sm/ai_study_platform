import { useCallback, useEffect, useMemo, useState } from "react";
import "./ProgrammingHome.css";
import ProgrammingWorkbench from "./ProgrammingWorkbench.jsx";

const NAV_ITEMS = [
  { key: "home", label: "首页", icon: "home" },
  { key: "status", label: "学习情况", icon: "chart" },
  { key: "workbench", label: "编程工作台", icon: "terminal" },
  { key: "questions", label: "题库", icon: "list" },
  { key: "files", label: "文件库", icon: "folder" },
];

const PROGRAMMING_NAV_KEY = "ai_study_programming_active_nav";

function Icon({ type }) {
  const common = { viewBox: "0 0 24 24", "aria-hidden": "true" };
  if (type === "chart") return <svg {...common}><path d="M5 19V9M12 19V5M19 19v-8" /></svg>;
  if (type === "terminal") return <svg {...common}><path d="m8 9-4 3 4 3M16 9l4 3-4 3M14 5l-4 14" /></svg>;
  if (type === "list") return <svg {...common}><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" /></svg>;
  if (type === "folder") return <svg {...common}><path d="M3 7h7l2 3h9v9H3V7Z" /></svg>;
  if (type === "quota") return <svg {...common}><path d="M12 3 4 7v10l8 4 8-4V7l-8-4ZM4 7l8 4 8-4M12 11v10" /></svg>;
  if (type === "task") return <svg {...common}><path d="M9 11l2 2 4-5M5 4h14v16H5V4Z" /></svg>;
  if (type === "code") return <svg {...common}><path d="m8 9-4 3 4 3M16 9l4 3-4 3" /></svg>;
  return <svg {...common}><path d="M4 12 12 5l8 7v8H4v-8Z" /></svg>;
}

function safeJson(res) {
  return res.json().catch(() => ({}));
}

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "0 MB";
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value) {
  if (!value) return "暂无";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "暂无";
  return date.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function getFileTypeLabel(file) {
  const type = String(file?.file_type || file?.mime_type || "").toLowerCase();
  const name = String(file?.original_filename || file?.filename || file?.name || file?.file_name || "").toLowerCase();
  if (type.includes("pdf") || name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".cpp") || name.endsWith(".c") || name.endsWith(".h") || name.endsWith(".py") || name.endsWith(".java")) return "代码";
  if (name.endsWith(".xlsx")) return "Excel";
  if (name.endsWith(".zip")) return "ZIP";
  if (name.endsWith(".md")) return "Markdown";
  return type || "文件";
}

function buildFileTree(files = []) {
  const root = { name: "", path: "", folders: new Map(), files: [] };
  files.forEach((file) => {
    const parts = String(file.relative_path || file.filename || "").split("/").filter(Boolean);
    let node = root;
    parts.slice(0, -1).forEach((part, index) => {
      const path = parts.slice(0, index + 1).join("/");
      if (!node.folders.has(part)) node.folders.set(part, { name: part, path, folders: new Map(), files: [] });
      node = node.folders.get(part);
    });
    node.files.push(file);
  });
  return root;
}

function LibraryTree({ node, depth = 0 }) {
  const folders = [...node.folders.values()].sort((a, b) => a.name.localeCompare(b.name));
  const files = [...node.files].sort((a, b) => a.relative_path.localeCompare(b.relative_path));
  return (
    <>
      {folders.map((folder) => (
        <div key={folder.path}>
          <div className="ph-lib-tree-folder" style={{ paddingLeft: 10 + depth * 16 }}>
            <span>▸</span>
            <strong>{folder.name}/</strong>
          </div>
          <LibraryTree node={folder} depth={depth + 1} />
        </div>
      ))}
      {files.map((file) => (
        <div key={file.id} className="ph-lib-tree-file" style={{ paddingLeft: 28 + depth * 16 }} title={file.relative_path}>
          <span>{getFileTypeLabel(file)}</span>
          <strong>{file.filename}</strong>
          <small>{formatDate(file.updated_at)}</small>
        </div>
      ))}
    </>
  );
}

function ProfileButton({ user, apiBase, onClick }) {
  const name = user?.nickname || user?.username || "同学";
  const avatarUrl = user?.avatar_url || "";
  return (
    <button type="button" className="ph-profile-button" onClick={onClick}>
      {avatarUrl ? (
        <img src={`${apiBase}${avatarUrl}?username=${encodeURIComponent(user?.username || "")}`} alt="头像" />
      ) : (
        <span>{name.charAt(0).toUpperCase()}</span>
      )}
      <strong>个人资料</strong>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5" /></svg>
    </button>
  );
}

function ProgrammingFileLibrary({ user, apiBase, onOpenProject }) {
  const [library, setLibrary] = useState({ projects: [], materials: [] });
  const [selectedProject, setSelectedProject] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  const loadLibrary = useCallback(async () => {
    if (!user?.username) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/programming/file-library?username=${encodeURIComponent(user.username)}`);
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || "文件库读取失败");
      setLibrary({ projects: data.projects || [], materials: data.materials || [] });
      if (selectedProject?.id) {
        const latest = (data.projects || []).find((item) => item.id === selectedProject.id);
        if (!latest) setSelectedProject(null);
      }
    } catch (err) {
      setError(err.message || "文件库读取失败");
    } finally {
      setLoading(false);
    }
  }, [apiBase, selectedProject?.id, user?.username]);

  const loadProjectDetail = useCallback(async (projectId) => {
    if (!user?.username || !projectId) return;
    setDetailLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/code/projects/${projectId}?username=${encodeURIComponent(user.username)}`);
      const data = await safeJson(res);
      if (!res.ok || !data.project) throw new Error(data.detail || "项目详情读取失败");
      setSelectedProject(data.project);
    } catch (err) {
      setError(err.message || "项目详情读取失败");
    } finally {
      setDetailLoading(false);
    }
  }, [apiBase, user?.username]);

  useEffect(() => { loadLibrary(); }, [loadLibrary]);

  const tree = useMemo(() => buildFileTree(selectedProject?.files || []), [selectedProject?.files]);

  return (
    <section className="ph-library-panel">
      <div className="ph-library-head">
        <div>
          <h2>编程文件库</h2>
          <p>项目来自 code_projects / code_project_files，普通文件来自 subject=programming 的 materials。</p>
        </div>
        <button type="button" onClick={loadLibrary} disabled={loading}>{loading ? "刷新中" : "刷新"}</button>
      </div>

      {error && <div className="ph-error">{error}</div>}

      <div className="ph-library-layout">
        <div className="ph-library-sections">
          <section className="ph-library-section">
            <div className="ph-library-section-title">
              <h3>我的编程项目</h3>
              <span>{library.projects.length} 个项目</span>
            </div>
            {library.projects.length === 0 ? (
              <div className="ph-lib-empty">还没有项目。从编程工作台新建后会立即出现在这里。</div>
            ) : (
              <div className="ph-project-grid">
                {library.projects.map((project) => (
                  <article key={project.id} className="ph-project-card">
                    <button type="button" onClick={() => loadProjectDetail(project.id)}>
                      <span>编程项目</span>
                      <strong>{project.name}</strong>
                      <small>{project.language} · {project.file_count || 0} 个文件</small>
                      <em>入口：{project.entry_file}</em>
                      <b>更新于：{formatDate(project.updated_at)}</b>
                    </button>
                    <button type="button" className="ph-open-workbench" onClick={() => onOpenProject(project.id)}>
                      打开工作台
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="ph-library-section">
            <div className="ph-library-section-title">
              <h3>普通文件</h3>
              <span>{library.materials.length} 个文件</span>
            </div>
            {library.materials.length === 0 ? (
              <div className="ph-lib-empty">暂无 programming 方向普通文件。</div>
            ) : (
              <div className="ph-material-list">
                {library.materials.map((file) => (
                  <div key={file.id}>
                    <span>{getFileTypeLabel(file)}</span>
                    <strong>{file.original_filename || file.file_name}</strong>
                    <small>{formatBytes(file.file_size)} · {formatDate(file.updated_at || file.created_at)}</small>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        <aside className="ph-project-detail">
          {!selectedProject ? (
            <div className="ph-lib-empty">选择一个项目查看真实文件树。</div>
          ) : (
            <>
              <div className="ph-project-detail-head">
                <span>{selectedProject.language}</span>
                <h3>{selectedProject.name}</h3>
                <p>入口文件：{selectedProject.entry_file}</p>
              </div>
              <dl className="ph-project-meta">
                <div><dt>文件数量</dt><dd>{selectedProject.files?.length || 0}</dd></div>
                <div><dt>创建时间</dt><dd>{formatDate(selectedProject.created_at)}</dd></div>
                <div><dt>更新时间</dt><dd>{formatDate(selectedProject.updated_at)}</dd></div>
              </dl>
              <div className="ph-lib-tree">
                {detailLoading ? <div className="ph-lib-empty">详情读取中...</div> : <LibraryTree node={tree} />}
              </div>
              <button type="button" className="ph-detail-open" onClick={() => onOpenProject(selectedProject.id)}>
                在编程工作台打开
              </button>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}

export default function ProgrammingHome({ user, apiBase = "/api", setPage }) {
  const [activeNav, setActiveNav] = useState(() => {
    try {
      return localStorage.getItem(PROGRAMMING_NAV_KEY) || "home";
    } catch {
      return "home";
    }
  });
  const [homeData, setHomeData] = useState(null);
  const [workbenchProjectId, setWorkbenchProjectId] = useState(null);
  const [error, setError] = useState("");

  const loadHomeData = useCallback(() => {
    if (!user?.username) return;
    fetch(`${apiBase}/programming/home?username=${encodeURIComponent(user.username)}`)
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) throw new Error(data.detail || "编程首页数据读取失败");
        setHomeData(data);
      })
      .catch((err) => {
        setError(err.message || "编程首页数据读取失败");
      });
  }, [apiBase, user?.username]);

  useEffect(() => { loadHomeData(); }, [loadHomeData]);

  useEffect(() => {
    try {
      localStorage.setItem(PROGRAMMING_NAV_KEY, activeNav);
    } catch {
      // ignore
    }
  }, [activeNav]);

  const openProjectInWorkbench = useCallback((projectId) => {
    setWorkbenchProjectId(projectId);
    setActiveNav("workbench");
  }, []);

  const tasks = homeData?.tasks || [];
  const completed = tasks.filter((task) => task.completed).length;
  const total = tasks.length || 4;
  const progressText = `${completed}/${total}`;
  const progressPercent = total ? Math.round((completed / total) * 100) : 0;
  const quota = homeData?.quota || {};
  const files = homeData?.files || [];
  const plan = homeData?.plan || "free";

  const navContent = useMemo(() => {
    if (activeNav === "workbench") {
      return (
        <ProgrammingWorkbench
          user={user}
          apiBase={apiBase}
          homeData={homeData}
          initialProjectId={workbenchProjectId}
          onProjectChanged={loadHomeData}
          setPage={setPage}
          onGoHome={() => {
            loadHomeData();
            setActiveNav("home");
          }}
        />
      );
    }
    if (activeNav === "files") {
      return (
        <ProgrammingFileLibrary
          user={user}
          apiBase={apiBase}
          onOpenProject={openProjectInWorkbench}
        />
      );
    }
    if (activeNav !== "home") {
      const item = NAV_ITEMS.find((nav) => nav.key === activeNav);
      return (
        <section className="ph-placeholder-panel">
          <h2>{item?.label || "功能入口"}</h2>
          <p>当前入口保留在编程学习方向内，后续功能将继续接入真实数据。</p>
        </section>
      );
    }
    return null;
  }, [activeNav, apiBase, homeData, loadHomeData, openProjectInWorkbench, setPage, user, workbenchProjectId]);

  return (
    <div className="ph-page">
      <aside className="ph-sidebar">
        <div className="ph-brand">
          <span><Icon type="code" /></span>
          <strong>编程学习</strong>
        </div>
        <nav className="ph-nav" aria-label="编程学习导航">
          {NAV_ITEMS.map((item) => (
            <button
              type="button"
              key={item.key}
              className={activeNav === item.key ? "is-active" : ""}
              onClick={() => setActiveNav(item.key)}
            >
              <Icon type={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        {plan === "free" ? (
          <div className="ph-member-card">
            <strong>会员权益</strong>
            <p>开通会员解锁更多功能</p>
            <button type="button" onClick={() => setPage?.("programmingPackageStep")}>了解会员</button>
          </div>
        ) : (
          <div className="ph-member-card ph-member-card--active">
            <strong>{homeData?.plan_label || "已开通会员"}</strong>
            <p>你的编程套餐权益已生效</p>
          </div>
        )}
      </aside>

      <main className="ph-main">
        {activeNav !== "workbench" && (
          <ProfileButton user={user} apiBase={apiBase} onClick={() => setPage?.("programmingProfile")} />
        )}

        {activeNav !== "home" ? navContent : (
          <>
            <section className="ph-hero">
              <div className="ph-hero-copy">
                <h1>你好，开始今天的<br />编程学习</h1>
                <p>坚持每天进步一点点，编程能力持续提升。</p>
                <div className="ph-status-tags">
                  <span>连续学习 {homeData?.stats?.streak_days ?? 0} 天</span>
                  <span>{homeData?.stats?.momentum || "初始状态"}</span>
                </div>
              </div>
              <div className="ph-hero-art" aria-hidden="true">
                <div className="ph-monitor">
                  <div><span /><span /><span /></div>
                  <pre>{`function learn() {\n  practice();\n  improve();\n}`}</pre>
                </div>
                <div className="ph-laptop">&lt;/&gt;</div>
                <div className="ph-bubble ph-bubble--left">{"{...}"}</div>
                <div className="ph-bubble ph-bubble--right">&lt;/&gt;</div>
              </div>
            </section>

            {error && <div className="ph-error">{error}</div>}

            <div className="ph-dashboard-grid">
              <section className="ph-card ph-task-card">
                <div className="ph-card-title">
                  <span><Icon type="task" /></span>
                  <h2>今日编程任务</h2>
                  <em>进度 {progressText}</em>
                </div>
                <div className="ph-progress"><span style={{ width: `${progressPercent}%` }} /></div>
                <div className="ph-task-list">
                  {tasks.map((task) => (
                    <div key={task.id} className={task.completed ? "is-done" : ""}>
                      <span />
                      <strong>{task.title}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <section className="ph-card ph-quota-card">
                <div className="ph-card-title">
                  <span><Icon type="quota" /></span>
                  <h2>今日额度剩余</h2>
                </div>
                <div className="ph-quota-list">
                  <div><span>AI问答 / 纠错剩余额度</span><strong>{quota.ai_chat?.remaining ?? 0} / {quota.ai_chat?.limit ?? 0} 次</strong></div>
                  <div><span>AI出题剩余额度</span><strong>{quota.ai_question?.remaining ?? 0} / {quota.ai_question?.limit ?? 0} 次</strong></div>
                  <div><span>文件库剩余额度</span><strong>{formatBytes((quota.file_library?.limit_bytes || 0) - (quota.file_library?.used_bytes || 0))} / {formatBytes(quota.file_library?.limit_bytes)} </strong></div>
                </div>
              </section>

              <section className="ph-card ph-file-card">
                <div className="ph-card-title">
                  <span><Icon type="folder" /></span>
                  <h2>文件库</h2>
                </div>
                {files.length === 0 ? (
                  <div className="ph-empty-files">当前暂无编程项目或 programming 普通文件。</div>
                ) : (
                  <div className="ph-file-list">
                    {files.map((file) => {
                      const isProject = file.item_type === "project";
                      return (
                        <button key={`${file.item_type}-${file.id}`} type="button" onClick={() => (isProject ? openProjectInWorkbench(file.id) : setActiveNav("files"))}>
                          <span>{isProject ? "项目" : getFileTypeLabel(file)}</span>
                          <strong>{isProject ? file.name : file.original_filename || file.file_name}</strong>
                          <small>{isProject ? `${file.language} · ${file.file_count || 0} 个文件` : `${getFileTypeLabel(file)} · ${formatBytes(file.file_size)}`}</small>
                          <em>›</em>
                        </button>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>
          </>
        )}

        <p className="ph-footer">代码改变世界，学习成就未来</p>
      </main>
    </div>
  );
}
