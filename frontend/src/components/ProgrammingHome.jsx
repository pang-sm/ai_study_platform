import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./ProgrammingHome.css";
import ProgrammingWorkbench from "./ProgrammingWorkbench.jsx";
import KnowledgeLearningPage from "./KnowledgeLearningPage.jsx";
import { getExerciseDescription, getExerciseTitle } from "./programmingExerciseCopy.js";

const NAV_ITEMS = [
  { key: "home", label: "首页", icon: "home" },
  { key: "status", label: "知识点学习", icon: "chart" },
  { key: "workbench", label: "编程工作台", icon: "terminal" },
  { key: "questions", label: "题库", icon: "list" },
];

const PROGRAMMING_NAV_KEY = "ai_study_programming_active_nav";
const CURRENT_PRACTICE_KEY = "ai_study_programming_current_practice";

function readCurrentPractice(username) {
  if (!username) return null;
  try {
    const saved = JSON.parse(localStorage.getItem(`${CURRENT_PRACTICE_KEY}:${username}`) || "null");
    return saved?.exerciseId ? saved : null;
  } catch {
    return null;
  }
}

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

function formatAiQuota(remaining, limit) {
  return Number(limit) >= 999999 ? "无限" : `${remaining ?? 0} / ${limit ?? 0} 次`;
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

function ExerciseLibrary({ user, apiBase, onStart }) {
  const [language, setLanguage] = useState("Python");
  const [tag, setTag] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [paging, setPaging] = useState({ total: 0, total_pages: 1 });
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestIdRef = useRef(0);
  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ language, page: String(page), page_size: String(pageSize) });
      if (user?.username) query.set("username", user.username);
      if (tag.trim()) query.set("tag", tag.trim());
      if (statusFilter) query.set("status", statusFilter);
      if (sourceFilter) query.set("source", sourceFilter);
      const res = await fetch(`${apiBase}/programming/exercises?${query}`);
      const data = await safeJson(res);
      if (!res.ok) throw new Error(data.detail || "题库加载失败");
      if (requestId !== requestIdRef.current) return;
      setItems(data.exercises || []);
      setPaging({ total: data.total || 0, total_pages: data.total_pages || 1 });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(err.message || "题库加载失败");
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [apiBase, language, tag, statusFilter, sourceFilter, page, pageSize, user?.username]);
  useEffect(() => { load(); }, [load]);
  const start = async (exercise) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/programming/exercises/${exercise.id}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username }),
      });
      const data = await safeJson(res);
      if (!res.ok || !data.project) throw new Error(data.detail || "练习初始化失败");
      onStart(data.project.id, data.project.language, exercise.id);
    } catch (err) {
      setError(err.message || "练习初始化失败");
    } finally {
      setLoading(false);
    }
  };
  return (
    <section className="ph-exercise-panel">
      <div className="ph-library-head">
        <div><h2>编程题库</h2><p>包含标准输入输出原创 OJ 题与经典练习，做题后直接进入对应 Workbench。</p></div>
        <button type="button" onClick={load} disabled={loading}>刷新</button>
      </div>
      <div className="ph-exercise-filters">
        {['C', 'C++', 'Python', 'Java'].map((item) => <button key={item} type="button" className={language === item ? 'is-active' : ''} onClick={() => { requestIdRef.current += 1; setItems([]); setPage(1); setLanguage(item); }}>{item}</button>)}
        <input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="知识点标签" />
      </div>
      {error && <div className="ph-error">{error}</div>}
      <div className="ph-exercise-filters ph-exercise-status-filters">
        <select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}><option value="">全部状态</option><option value="needs_improvement">待改进</option><option value="not_started">未开始</option><option value="passed">已通过</option></select>
        <select value={sourceFilter} onChange={(event) => { setSourceFilter(event.target.value); setPage(1); }}><option value="">全部题源</option><option value="first_party_original">原创题目</option><option value="classic_exercise">经典练习</option></select>
        <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}><option value={12}>12/页</option><option value={24}>24/页</option><option value={48}>48/页</option></select>
      </div>
      <div className="ph-exercise-grid">
        {items.map((exercise) => (
          <article key={exercise.id} className="ph-exercise-card">
            <div className={`ph-exercise-personal-status ph-exercise-personal-status--${exercise.personal_progress?.personal_status || "not_started"}`}>{exercise.personal_progress?.personal_status === "passed" ? "已通过" : exercise.personal_progress?.personal_status === "needs_work" ? "待改进" : "未开始"}</div>
            <div className="ph-exercise-card-top"><span>{exercise.language}</span><em>{exercise.difficulty}</em><small>{exercise.source_label}</small></div>
            <h3>{getExerciseTitle(exercise)}</h3>
            <p>{getExerciseDescription(exercise)}</p>
            <div className="ph-exercise-tags">{(exercise.tags || []).slice(0, 5).map((item) => <span key={item}>{item}</span>)}</div>
            <button type="button" onClick={() => start(exercise)} disabled={loading}>{exercise.personal_progress?.personal_status === "passed" ? "再次练习" : exercise.personal_progress?.personal_status === "needs_work" ? "继续改进" : "开始做题"}</button>
          </article>
        ))}
      </div>
      {!loading && !items.length && <div className="ph-lib-empty">暂无符合筛选条件的已审计题目。</div>}
      <div className="ph-pagination"><span>共 {paging.total} 道，第 {page}/{paging.total_pages} 页</span><button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1 || loading}>上一页</button><button type="button" onClick={() => setPage((value) => Math.min(paging.total_pages, value + 1))} disabled={page >= paging.total_pages || loading}>下一页</button></div>
    </section>
  );
}

export default function ProgrammingHome({ user, apiBase = "/api", setPage }) {
  const savedPractice = readCurrentPractice(user?.username);
  const [activeNav, setActiveNav] = useState(() => {
    try {
      return localStorage.getItem(PROGRAMMING_NAV_KEY) || "home";
    } catch {
      return "home";
    }
  });
  const [homeData, setHomeData] = useState(null);
  const [workbenchProjectId, setWorkbenchProjectId] = useState(() => savedPractice?.projectId || null);
  const [workbenchLanguage, setWorkbenchLanguage] = useState(() => savedPractice?.language || "");
  const [workbenchExerciseId, setWorkbenchExerciseId] = useState(() => savedPractice?.exerciseId || null);
  const [knowledgeLanguage, setKnowledgeLanguage] = useState(() => homeData?.onboarding?.main_language || "Python");
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

  const openExercise = useCallback(async (exerciseId) => {
    if (!exerciseId || !user?.username) return;
    const res = await fetch(`${apiBase}/programming/exercises/${exerciseId}/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username }),
    });
    const data = await safeJson(res);
    if (!res.ok || !data.project) return;
    setWorkbenchProjectId(data.project.id);
    setWorkbenchLanguage(data.project.language);
    setWorkbenchExerciseId(exerciseId);
    setActiveNav("workbench");
  }, [apiBase, user?.username]);

  useEffect(() => {
    try {
      localStorage.setItem(PROGRAMMING_NAV_KEY, activeNav);
    } catch {
      // ignore
    }
  }, [activeNav]);

  useEffect(() => {
    if (!user?.username || !workbenchExerciseId) return;
    try {
      localStorage.setItem(`${CURRENT_PRACTICE_KEY}:${user.username}`, JSON.stringify({
        projectId: workbenchProjectId,
        language: workbenchLanguage,
        exerciseId: workbenchExerciseId,
      }));
    } catch {
      // ignore storage failures; server-side exercise state remains authoritative.
    }
  }, [user?.username, workbenchExerciseId, workbenchLanguage, workbenchProjectId]);

  const activateNav = useCallback((key) => {
    setActiveNav(key);
  }, []);

  const tasks = homeData?.tasks || [];
  const completed = tasks.filter((task) => task.completed).length;
  const total = tasks.length || 4;
  const progressText = `${completed}/${total}`;
  const progressPercent = total ? Math.round((completed / total) * 100) : 0;
  const quota = homeData?.quota || {};
  const plan = homeData?.plan || "free";

  const navContent = useMemo(() => {
    if (activeNav === "workbench") {
      return (
          <ProgrammingWorkbench
            key={workbenchExerciseId ? `exercise-${workbenchExerciseId}` : "workbench-empty"}
          user={user}
          apiBase={apiBase}
          homeData={homeData}
          initialProjectId={workbenchProjectId}
          initialLanguageSelection={workbenchLanguage}
          initialExerciseId={workbenchExerciseId}
          onProjectChanged={loadHomeData}
          onOpenQuestions={() => setActiveNav("questions")}
          setPage={setPage}
          onGoHome={() => {
            loadHomeData();
            setActiveNav("home");
          }}
        />
      );
    }
    if (activeNav === "questions") {
      return <ExerciseLibrary user={user} apiBase={apiBase} onStart={(projectId, language, exerciseId) => { setWorkbenchProjectId(projectId); setWorkbenchLanguage(language); setWorkbenchExerciseId(exerciseId); setActiveNav("workbench"); }} />;
    }
    if (activeNav === "status") {
      const knowledgeCourse = {
        C: { id: "c_programming", name: "C 语言程序设计" },
        "C++": { id: "cpp_programming", name: "C++ 程序设计" },
        Python: { id: "python_programming", name: "Python 程序设计" },
        Java: { id: "java_programming", name: "Java 程序设计" },
      }[knowledgeLanguage] || { id: "python_programming", name: "Python 程序设计" };
      return (
        <KnowledgeLearningPage
          user={user}
          mode="course_learning"
          courseId={knowledgeCourse.id}
          courseName={knowledgeCourse.name}
          programmingLanguageTabs
          programmingLanguage={knowledgeLanguage}
          onProgrammingLanguageChange={setKnowledgeLanguage}
          apiBase={apiBase}
          onOpenExercise={openExercise}
          onNavigateToAI={() => setActiveNav("workbench")}
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
  }, [activeNav, apiBase, homeData, knowledgeLanguage, loadHomeData, openExercise, setPage, user, workbenchExerciseId, workbenchLanguage, workbenchProjectId]);

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
              onClick={() => activateNav(item.key)}
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
                  <span>连续学习 {homeData?.stats?.streak_days ?? "暂无数据"}{homeData?.stats?.streak_days == null ? "" : " 天"}</span>
                  <span>{homeData?.stats?.momentum || "暂无学习记录"}</span>
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
                  <div><span>AI问答 / 纠错剩余额度</span><strong>{formatAiQuota(quota.ai_chat?.remaining, quota.ai_chat?.limit)}</strong></div>
                  <div><span>AI出题剩余额度</span><strong>{quota.ai_question?.remaining ?? 0} / {quota.ai_question?.limit ?? 0} 次</strong></div>
                </div>
              </section>

              <section className="ph-card ph-learning-entry-card">
                <div className="ph-card-title">
                  <span><Icon type="code" /></span>
                  <h2>开始练习</h2>
                </div>
                <p className="ph-learning-entry-copy">从一道真实题目开始，AI 教练会陪你完成理解、编码、测试和提交。</p>
                <div className="ph-learning-entry-actions">
                  <button type="button" onClick={() => activateNav("workbench")}>继续上次练习</button>
                  <button type="button" onClick={() => activateNav("questions")}>从题库选题</button>
                </div>
              </section>
            </div>
          </>
        )}

        <p className="ph-footer">代码改变世界，学习成就未来</p>
      </main>
    </div>
  );
}
