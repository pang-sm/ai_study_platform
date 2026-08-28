import { useCallback, useEffect, useMemo, useState } from "react";
import "./ProgrammingHome.css";
import ProgrammingWorkbench from "./ProgrammingWorkbench.jsx";
import KnowledgeLearningPage from "./KnowledgeLearningPage.jsx";
import ProgrammingMaterialsPage from "./ProgrammingMaterialsPage.jsx";
import { getExerciseDescription, getExerciseTitle } from "./programmingExerciseCopy.js";
import ProgrammingProfileTrigger from "./ProgrammingProfileTrigger.jsx";
import FirstTimeGuideLauncher from "./FirstTimeGuideLauncher.jsx";
import { resolveProgrammingCourse } from "../programmingCourses.js";

const NAV_ITEMS = [
  { key: "home", label: "首页", icon: "home" },
  { key: "status", label: "知识点学习", icon: "chart" },
  { key: "workbench", label: "编程工作台", icon: "terminal" },
  { key: "questions", label: "题库", icon: "list" },
  { key: "materials", label: "资料库", icon: "folder" },
  { key: "chat", label: "AI问答", icon: "chat" },
];

const PROGRAMMING_NAV_KEY = "ai_study_programming_active_nav";
const CURRENT_PRACTICE_KEY = "ai_study_programming_current_practice";

const PROGRAMMING_GUIDE_STEPS = [
  { selector: '[data-tour="programming-overview"]', title: "今日学习概览", description: "在首页查看连续学习天数和今日 AI 使用额度，开始当天的真实练习。" },
  { selector: '[data-tour="programming-questions"]', title: "编程题库", description: "按语言、难度选择真实编程题，不会再出现已清理的今日假任务。" },
  { selector: '[data-tour="programming-workbench"]', title: "编程工作台", description: "在 Workbench 中编写、运行和提交代码；引导不会自动打开题目。" },
  { selector: '[data-tour="programming-knowledge"]', title: "知识点学习", description: "遇到薄弱知识点时，在这里进入对应语言的学习脉络。" },
  { selector: '[data-tour="programming-profile"]', title: "个人中心与会员", description: "在个人中心查看资料、会员与套餐权益；右上角 Profile 保持可点击且没有额外箭头。" },
];

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
  if (type === "code") return <svg {...common}><path d="m8 9-4 3 4 3M16 9l4 3-4 3" /></svg>;
  if (type === "chat") return <svg {...common}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>;
  return <svg {...common}><path d="M4 12 12 5l8 7v8H4v-8Z" /></svg>;
}

function safeJson(res) {
  return res.json().catch(() => ({}));
}

function formatAiQuota(remaining, limit) {
  return `${remaining ?? 0} / ${limit ?? 0} 次`;
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
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const loadExercises = async () => {
      setLoading(true);
      setError("");
      try {
        const query = new URLSearchParams({ language, page: String(page), page_size: String(pageSize) });
        if (user?.username) query.set("username", user.username);
        if (tag.trim()) query.set("tag", tag.trim());
        if (statusFilter) query.set("status", statusFilter);
        if (sourceFilter) query.set("source", sourceFilter);
        const res = await fetch(`${apiBase}/programming/exercises?${query}`, { signal: controller.signal });
        const data = await safeJson(res);
        if (!res.ok) throw new Error(data.detail || "题库加载失败");
        if (controller.signal.aborted) return;
        const exercises = Array.isArray(data.exercises) && data.exercises.length
          ? data.exercises
          : Array.isArray(data.items)
            ? data.items
            : [];
        setItems(exercises);
        setPaging({ total: data.total || 0, total_pages: data.total_pages || 1 });
      } catch (err) {
        if (!controller.signal.aborted) setError(err.message || "题库加载失败");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void loadExercises();
    return () => controller.abort();
  }, [apiBase, language, tag, statusFilter, sourceFilter, page, pageSize, refreshKey, user?.username]);
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
      <div className="ph-library-head ph-library-head--end">
        <button type="button" onClick={() => setRefreshKey((value) => value + 1)} disabled={loading}>刷新</button>
      </div>
      <div className="ph-exercise-filters">
        {['C', 'C++', 'Python', 'Java'].map((item) => <button key={item} type="button" className={language === item ? 'is-active' : ''} onClick={() => { setPage(1); setLanguage(item); }}>{item}</button>)}
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

export default function ProgrammingHome({ user, apiBase = "/api", setPage, guideReplayToken = 0, knowledgeDeepLink = null }) {
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
  const [knowledgeDeepLinkTarget, setKnowledgeDeepLinkTarget] = useState(null);
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

  // Apply an external knowledge deep-link (from AI 问答 "返回知识点") once.
  useEffect(() => {
    if (!knowledgeDeepLink) return;
    if (knowledgeDeepLink.language) setKnowledgeLanguage(knowledgeDeepLink.language);
    setKnowledgeDeepLinkTarget({
      chapterCode: knowledgeDeepLink.chapterCode || "",
      nodeCode: knowledgeDeepLink.nodeCode || "",
      nonce: knowledgeDeepLink.nonce || Date.now(),
    });
    setActiveNav("status");
  }, [knowledgeDeepLink?.nonce, knowledgeDeepLink?.language, knowledgeDeepLink?.chapterCode, knowledgeDeepLink?.nodeCode]);

  const resolveCourse = useCallback((language) => {
    try {
      return resolveProgrammingCourse(language);
    } catch (err) {
      setError(err.message || "未知编程课程");
      return null;
    }
  }, []);

  const openAIChat = useCallback((language, pendingAIContext = null) => {
    const course = resolveCourse(language);
    if (!course) return;
    setPage("programmingChat", {
      language: course.language,
      courseId: course.courseId,
      scopeSubject: course.courseName,
      displayName: course.language,
      pendingAIContext,
    });
  }, [resolveCourse, setPage]);

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
          onOpenProfile={() => setPage?.("programmingProfile")}
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
      const knowledgeCourse = resolveCourse(knowledgeLanguage);
      if (!knowledgeCourse) {
        return (
          <section className="ph-placeholder-panel">
            <h2>知识点学习</h2>
            <p>{error || "未知编程课程，无法加载知识点脉络。"}</p>
          </section>
        );
      }
      return (
        <KnowledgeLearningPage
          user={user}
          mode="course_learning"
          courseId={knowledgeCourse.courseId}
          courseName={knowledgeCourse.courseName}
          programmingLanguageTabs
          programmingLanguage={knowledgeLanguage}
          onProgrammingLanguageChange={setKnowledgeLanguage}
          apiBase={apiBase}
          onOpenExercise={openExercise}
          onNavigateToAI={(ctx) => openAIChat(knowledgeLanguage, ctx)}
          initialChapterCode={knowledgeDeepLinkTarget?.chapterCode || ""}
          initialNodeCode={knowledgeDeepLinkTarget?.nodeCode || ""}
        />
      );
    }
    if (activeNav === "materials") {
      return (
        <ProgrammingMaterialsPage
          user={user}
          apiBase={apiBase}
          language={knowledgeLanguage}
          onLanguageChange={setKnowledgeLanguage}
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
  }, [activeNav, apiBase, homeData, knowledgeLanguage, loadHomeData, openExercise, setPage, user, workbenchExerciseId, workbenchLanguage, workbenchProjectId, resolveCourse, openAIChat, error, knowledgeDeepLinkTarget]);

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
              onClick={() => {
                if (item.key === "chat") {
                  openAIChat(knowledgeLanguage);
                  return;
                }
                activateNav(item.key);
              }}
              data-tour={item.key === "questions" ? "programming-questions" : item.key === "workbench" ? "programming-workbench" : item.key === "status" ? "programming-knowledge" : item.key === "chat" ? "programming-chat" : undefined}
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
            <button
              type="button"
              onClick={() => setPage?.("membership", {
                serviceKey: "programming",
                profilePage: "programmingProfile",
                returnPage: "programmingHome",
              })}
            >了解会员</button>
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
          <span data-tour="programming-profile"><ProgrammingProfileTrigger
            user={user}
            apiBase={apiBase}
            className="ph-profile-trigger"
            onClick={() => setPage?.("programmingProfile")}
          /></span>
        )}

        {activeNav !== "home" ? navContent : (
          <>
            <section className="ph-hero" data-tour="programming-overview">
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
      <FirstTimeGuideLauncher serviceKey="programming" serviceLabel="编程学习" steps={PROGRAMMING_GUIDE_STEPS} apiBase={apiBase} ready={Boolean(homeData)} replayToken={guideReplayToken} />
    </div>
  );
}
