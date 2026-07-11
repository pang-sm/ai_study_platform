import { useEffect, useMemo, useState } from "react";
import "./ProgrammingHome.css";

const NAV_ITEMS = [
  { key: "home", label: "首页", icon: "home" },
  { key: "status", label: "学习情况", icon: "chart" },
  { key: "workbench", label: "编程工作台", icon: "terminal" },
  { key: "questions", label: "题库", icon: "list" },
  { key: "files", label: "文件库", icon: "folder" },
];

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

function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "0 GB";
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function getFileTypeLabel(file) {
  const type = String(file?.file_type || file?.mime_type || "").toLowerCase();
  const name = String(file?.original_filename || file?.filename || file?.name || "");
  if (type.includes("pdf") || name.endsWith(".pdf")) return "PDF";
  if (name.endsWith(".cpp") || name.endsWith(".c") || name.endsWith(".py") || name.endsWith(".java")) return "代码";
  if (name.endsWith(".xlsx")) return "Excel";
  if (name.endsWith(".zip")) return "ZIP";
  if (name.endsWith(".md")) return "Markdown";
  return type || "文件";
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

export default function ProgrammingHome({ user, apiBase = "/api", setPage }) {
  const [activeNav, setActiveNav] = useState("home");
  const [homeData, setHomeData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user?.username) return;
    let alive = true;
    fetch(`${apiBase}/programming/home?username=${encodeURIComponent(user.username)}`)
      .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (!alive) return;
        if (!ok) throw new Error(data.detail || "编程首页数据读取失败");
        setHomeData(data);
      })
      .catch((err) => {
        if (alive) setError(err.message || "编程首页数据读取失败");
      });
    return () => { alive = false; };
  }, [apiBase, user?.username]);

  const tasks = homeData?.tasks || [];
  const completed = tasks.filter((task) => task.completed).length;
  const total = tasks.length || 4;
  const progressText = `${completed}/${total}`;
  const progressPercent = total ? Math.round((completed / total) * 100) : 0;
  const quota = homeData?.quota || {};
  const files = homeData?.files || [];
  const plan = homeData?.plan || "free";

  const openWorkbench = () => {
    setPage?.("codeStudio", {
      source: "programming",
      returnPage: "programmingHome",
      subject: user?.default_course_id || homeData?.onboarding?.main_language || "Python",
    });
  };

  const navContent = useMemo(() => {
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
  }, [activeNav]);

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
              onClick={() => (item.key === "workbench" ? openWorkbench() : setActiveNav(item.key))}
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
        <ProfileButton user={user} apiBase={apiBase} onClick={() => setPage?.("programmingProfile")} />

        {activeNav !== "home" ? navContent : (
          <>
            <section className="ph-hero">
              <div className="ph-hero-copy">
                <h1>你好，开始今天的<br />编程学习！ <span>👋</span></h1>
                <p>坚持每天进步一点点，编程能力持续提升！</p>
                <div className="ph-status-tags">
                  <span>连续学习 {homeData?.stats?.streak_days ?? 0} 天</span>
                  <span>{homeData?.stats?.momentum || "初始状态"} 🔥</span>
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
                  <div><span>文件库剩余额度</span><strong>{formatBytes(quota.file_library?.limit_bytes - quota.file_library?.used_bytes)} / {formatBytes(quota.file_library?.limit_bytes)} </strong></div>
                </div>
              </section>

              <section className="ph-card ph-file-card">
                <div className="ph-card-title">
                  <span><Icon type="folder" /></span>
                  <h2>文件库</h2>
                </div>
                {files.length === 0 ? (
                  <div className="ph-empty-files">当前暂无编程文件，上传后会显示真实文件记录。</div>
                ) : (
                  <div className="ph-file-list">
                    {files.map((file) => (
                      <div key={file.id}>
                        <span>{getFileTypeLabel(file)}</span>
                        <strong>{file.original_filename || file.filename || file.name}</strong>
                        <small>{getFileTypeLabel(file)} · {formatBytes(file.file_size)}</small>
                        <em>⋮</em>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </>
        )}

        <p className="ph-footer">代码改变世界，学习成就未来 <span>♥</span></p>
      </main>
    </div>
  );
}
