import { useEffect, useMemo, useRef, useState } from "react";
import "./CourseLearningHome.css";

const COURSE_THEMES = [
  { icon: "DS", tone: "purple" },
  { icon: "DM", tone: "blue" },
  { icon: "OS", tone: "green" },
  { icon: "CN", tone: "cyan" },
  { icon: "DB", tone: "orange" },
  { icon: "AI", tone: "violet" },
];

const COURSE_CATALOG = [
  "数据结构",
  "离散数学",
  "操作系统",
  "计算机网络",
  "计算机组成原理",
  "C 语言程序设计",
  "Python 程序设计",
  "Java 程序设计",
  "数据库系统",
  "算法设计与分析",
  "编译原理",
  "软件工程",
  "高等数学",
  "线性代数",
  "概率论与数理统计",
  "互联网计算",
  "计算机图形学",
  "人工智能导论",
];

const GOAL_OPTIONS = ["平日学习", "考试突击"];

const MATERIAL_TYPES = [
  { key: "slides", label: "课件讲义", hint: "份", tone: "blue", match: ["ppt", "课件", "讲义", "slides"] },
  { key: "books", label: "教材电子书", hint: "本", tone: "orange", match: ["教材", "电子书", "book"] },
  { key: "notes", label: "课堂笔记", hint: "份", tone: "indigo", match: ["笔记", "note"] },
  { key: "exercises", label: "习题集", hint: "份", tone: "cyan", match: ["习题", "作业", "exercise", "homework"] },
  { key: "labs", label: "实验报告", hint: "份", tone: "green", match: ["实验", "报告", "lab"] },
  { key: "reading", label: "拓展阅读", hint: "篇", tone: "violet", match: ["阅读", "论文", "paper", "reference"] },
];

function uniqueValues(values) {
  return Array.from(new Set((values || []).map((item) => `${item || ""}`.trim()).filter(Boolean)));
}

function normalizeCourseName(course) {
  const text = `${course || ""}`.trim();
  const aliases = {
    数据结构与算法: "数据结构",
    C语言: "C 语言程序设计",
    Python: "Python 程序设计",
    Java: "Java 程序设计",
  };
  return aliases[text] || text;
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "0 MB";
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function getMaterialTypeCount(materials, type) {
  return (materials || []).filter((item) => {
    const text = `${item.file_type || ""} ${item.file_name || ""} ${item.original_filename || ""} ${item.summary || ""}`.toLowerCase();
    return type.match.some((keyword) => text.includes(keyword.toLowerCase()));
  }).length;
}

function getCourseInitials(course, index) {
  const known = {
    数据结构: "DS",
    离散数学: "DM",
    操作系统: "OS",
    计算机网络: "CN",
    计算机组成原理: "CO",
    "C 语言程序设计": "C",
    "Python 程序设计": "PY",
    "Java 程序设计": "JA",
    数据库系统: "DB",
    算法设计与分析: "AL",
    编译原理: "CP",
    软件工程: "SE",
    高等数学: "MA",
    线性代数: "LA",
    概率论与数理统计: "PR",
    互联网计算: "IC",
    计算机图形学: "CG",
    人工智能导论: "AI",
  };
  return known[course] || COURSE_THEMES[index % COURSE_THEMES.length].icon;
}

function UserCard({ user, apiBase }) {
  const name = user?.nickname || user?.username || "同学";
  const hasAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");

  return (
    <button className="clh-user-card" type="button" aria-label="个人信息">
      {hasAvatar ? (
        <img className="clh-user-avatar" src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}`} alt="头像" />
      ) : (
        <span className="clh-user-avatar clh-user-avatar--text">{name.charAt(0).toUpperCase()}</span>
      )}
      <span className="clh-user-meta">
        <strong>{name}</strong>
        <span>会员 Pro</span>
      </span>
      <span className="clh-user-chevron">⌄</span>
    </button>
  );
}

export default function CourseLearningHome({
  user,
  apiBase = "/api",
  subject,
  setSubject,
  setPage,
  materials = [],
  loadMaterials,
  courseOptions = [],
  getSubjectLabel,
}) {
  const [onboarding, setOnboarding] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [pendingCourse, setPendingCourse] = useState("");
  const [pendingGoal, setPendingGoal] = useState("平日学习");
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const loadMaterialsRef = useRef(loadMaterials);

  useEffect(() => {
    loadMaterialsRef.current = loadMaterials;
  }, [loadMaterials]);

  useEffect(() => {
    if (!user?.username) return;
    fetch(`${apiBase}/course-learning/onboarding`, {
      headers: { Authorization: `Bearer ${encodeURIComponent(user.username)}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setOnboarding(data))
      .catch(() => setOnboarding(null));
  }, [apiBase, user?.username]);

  useEffect(() => {
    if (!user?.username || !loadMaterialsRef.current) return;
    loadMaterialsRef.current("");
  }, [user?.username]);

  const courseGoals = useMemo(() => {
    const raw = onboarding?.course_goals;
    return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  }, [onboarding?.course_goals]);

  const selectedCourses = useMemo(() => {
    const fromOnboarding = uniqueValues(onboarding?.selected_courses).map(normalizeCourseName);
    const fallbacks = uniqueValues([subject, ...courseOptions]).map((course) => normalizeCourseName(getSubjectLabel ? getSubjectLabel(course) : course));
    const base = fromOnboarding.length > 0 ? fromOnboarding : fallbacks;
    return uniqueValues(base).slice(0, 8);
  }, [onboarding?.selected_courses, subject, courseOptions, getSubjectLabel]);

  const availableCourses = useMemo(() => {
    const selected = new Set(selectedCourses.map(normalizeCourseName));
    return COURSE_CATALOG.filter((course) => !selected.has(normalizeCourseName(course)));
  }, [selectedCourses]);

  const courseCards = selectedCourses.map((course, index) => {
    const theme = COURSE_THEMES[index % COURSE_THEMES.length];
    return {
      name: course,
      value: course,
      icon: getCourseInitials(course, index),
      tone: theme.tone,
      status: index === 0 ? "正在学习" : "尚未开始",
      goal: courseGoals[course] || "平日学习",
    };
  });

  const planItems = [
    {
      title: `完成${courseCards[0]?.name || "数据结构"}的重点小节`,
      course: courseCards[0]?.name || "数据结构",
      progress: "0/3 节",
      done: false,
    },
    {
      title: `复盘${courseCards[0]?.name || "数据结构"}课堂笔记`,
      course: courseCards[0]?.name || "数据结构",
      progress: "2/2 节",
      done: true,
    },
    {
      title: courseCards[1] ? `整理${courseCards[1].name}练习题` : "整理课程练习题",
      course: courseCards[1]?.name || "课程学习",
      progress: "0/2 节",
      done: false,
    },
  ];

  const totalSize = materials.reduce((sum, item) => sum + Number(item.file_size || 0), 0);
  const quotaBytes = 10 * 1024 * 1024 * 1024;
  const usedPercent = Math.min(100, Math.round((totalSize / quotaBytes) * 100));

  const openCourse = (course) => {
    if (course && setSubject) setSubject(course);
    setPage("dashboard");
  };

  const openAddModal = () => {
    setPendingCourse(availableCourses[0] || "");
    setPendingGoal("平日学习");
    setSaveError("");
    setIsAddModalOpen(true);
  };

  const closeAddModal = () => {
    if (isSaving) return;
    setIsAddModalOpen(false);
    setSaveError("");
  };

  const saveAddedCourse = async () => {
    if (!pendingCourse) {
      setSaveError("请选择一门要加入主页的课程");
      return;
    }
    if (!GOAL_OPTIONS.includes(pendingGoal)) {
      setSaveError("请选择学习目标");
      return;
    }

    const nextCourses = uniqueValues([...selectedCourses, pendingCourse]);
    const nextGoals = { ...courseGoals, [pendingCourse]: pendingGoal };
    setIsSaving(true);
    setSaveError("");
    try {
      const res = await fetch(`${apiBase}/course-learning/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${encodeURIComponent(user?.username || "")}`,
        },
        body: JSON.stringify({
          major: onboarding?.major || user?.major || "其他专业",
          grade: onboarding?.grade || user?.grade || "暂不确定",
          selected_courses: nextCourses,
          material_types: Array.isArray(onboarding?.material_types) ? onboarding.material_types : [],
          plan: onboarding?.plan || "free",
          onboarding_completed: true,
          course_goals: nextGoals,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "课程加入失败，请稍后重试");
      setOnboarding(data?.onboarding || {
        ...onboarding,
        selected_courses: nextCourses,
        course_goals: nextGoals,
        onboarding_completed: true,
      });
      setIsAddModalOpen(false);
    } catch (error) {
      setSaveError(error.message || "课程加入失败，请稍后重试");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="clh-page">
      <div className="clh-shell">
        <header className="clh-hero">
          <div>
            <h1>欢迎回来，开始今天的课程学习 <span>✦</span></h1>
            <p>保持专注，持续进步，每一天都比昨天更优秀！</p>
          </div>
          <UserCard user={user} apiBase={apiBase} />
        </header>

        <section className="clh-card clh-courses-card">
          <div className="clh-section-title">
            <h2>我的课程</h2>
            <span />
          </div>
          <div className="clh-course-row">
            {courseCards.map((course, index) => (
              <button
                key={`${course.value}-${index}`}
                className={`clh-course-card clh-course-card--${course.tone}${index === 0 ? " is-active" : ""}`}
                type="button"
                onClick={() => openCourse(course.value)}
              >
                <span className="clh-course-visual">{course.icon}</span>
                <span className="clh-course-text">
                  <strong>{course.name}</strong>
                  <small>{course.status}</small>
                  <em>{course.goal}</em>
                </span>
                {index === 0 && <span className="clh-course-check">✓</span>}
              </button>
            ))}
            <button className="clh-add-course" type="button" onClick={openAddModal}>
              <span>＋</span>
              <strong>添加课程</strong>
            </button>
          </div>
        </section>

        <div className="clh-main-grid">
          <section className="clh-card clh-plan-card">
            <div className="clh-panel-heading">
              <span className="clh-panel-icon clh-panel-icon--calendar">▣</span>
              <h2>今日学习计划</h2>
            </div>
            <div className="clh-plan-list">
              {planItems.map((item) => (
                <div className="clh-plan-item" key={`${item.title}-${item.progress}`}>
                  <span className={`clh-plan-dot${item.done ? " is-done" : ""}`}>{item.done ? "✓" : ""}</span>
                  <div className="clh-plan-body">
                    <strong>{item.title}</strong>
                    <span>{item.course}</span>
                  </div>
                  <em>{item.progress}</em>
                </div>
              ))}
            </div>
          </section>

          <section className="clh-card clh-material-card">
            <div className="clh-panel-heading">
              <span className="clh-panel-icon clh-panel-icon--folder">▰</span>
              <h2>资料库概览</h2>
            </div>
            <div className="clh-material-grid">
              {MATERIAL_TYPES.map((type) => {
                const count = getMaterialTypeCount(materials, type);
                return (
                  <button
                    className="clh-material-item"
                    type="button"
                    key={type.key}
                    onClick={() => setPage("workspaceMaterials")}
                  >
                    <span className={`clh-material-icon clh-material-icon--${type.tone}`}>■</span>
                    <span>
                      <strong>{type.label}</strong>
                      <small>{count} {type.hint}</small>
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="clh-storage">
              <span>已用 {formatSize(totalSize)} / 共 10 GB</span>
              <div className="clh-storage-track">
                <span style={{ width: `${Math.max(usedPercent, totalSize > 0 ? 6 : 0)}%` }} />
              </div>
            </div>
          </section>
        </div>

        <footer className="clh-tip">
          <span>★</span>
          <strong>小贴士：</strong>
          <p>制定学习计划，合理安排时间，坚持学习会让你收获更大进步！</p>
          <div className="clh-tip-books" aria-hidden="true" />
        </footer>
      </div>

      {isAddModalOpen && (
        <div className="clh-modal-backdrop" role="presentation" onMouseDown={closeAddModal}>
          <section
            className="clh-add-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="clh-add-course-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button className="clh-modal-close" type="button" onClick={closeAddModal} aria-label="关闭">×</button>
            <div className="clh-modal-header">
              <span>添加课程</span>
              <h2 id="clh-add-course-title">选择你想加入学习主页的课程</h2>
              <p>已加入的课程不会重复出现，确认后会保存到你的课程主页。</p>
            </div>

            <div className="clh-modal-section">
              <h3>可选课程</h3>
              {availableCourses.length > 0 ? (
                <div className="clh-course-picker">
                  {availableCourses.map((course) => (
                    <button
                      className={`clh-picker-item${pendingCourse === course ? " is-selected" : ""}`}
                      type="button"
                      key={course}
                      onClick={() => setPendingCourse(course)}
                    >
                      {course}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="clh-empty-picker">所有示例课程都已经加入主页了。</p>
              )}
            </div>

            <div className="clh-modal-section">
              <h3>学习目标</h3>
              <div className="clh-goal-toggle" role="radiogroup" aria-label="学习目标">
                {GOAL_OPTIONS.map((goal) => (
                  <button
                    className={`clh-goal-option${pendingGoal === goal ? " is-selected" : ""}`}
                    type="button"
                    role="radio"
                    aria-checked={pendingGoal === goal}
                    key={goal}
                    onClick={() => setPendingGoal(goal)}
                  >
                    {goal}
                  </button>
                ))}
              </div>
            </div>

            {saveError && <p className="clh-modal-error">{saveError}</p>}

            <div className="clh-modal-actions">
              <button className="clh-modal-secondary" type="button" onClick={closeAddModal} disabled={isSaving}>取消</button>
              <button className="clh-modal-primary" type="button" onClick={saveAddedCourse} disabled={isSaving || !pendingCourse}>
                {isSaving ? "保存中..." : "确认加入"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
