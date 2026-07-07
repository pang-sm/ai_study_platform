import { useEffect, useMemo, useRef, useState } from "react";
import "./CourseLearningHome.css";
import { COURSE_LEARNING_CATALOG, COURSE_DISPLAY_NAMES, normalizeCourseLearningName, resolveCourseId } from "../courseLearningCatalog.js";

const COURSE_THEMES = [
  { icon: "DS", tone: "purple" },
  { icon: "DM", tone: "blue" },
  { icon: "OS", tone: "green" },
  { icon: "CN", tone: "cyan" },
  { icon: "DB", tone: "orange" },
  { icon: "AI", tone: "violet" },
];

const GOAL_OPTIONS = ["平日学习", "考试突击"];

function uniqueValues(values) {
  return Array.from(new Set((values || []).map((item) => `${item || ""}`.trim()).filter(Boolean)));
}

function normalizeCourseName(course) {
  return normalizeCourseLearningName(course) || `${course || ""}`.trim();
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "0 MB";
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function getMaterialChunkCount(material) {
  return Number(material?.chunk_count ?? material?.chunks ?? material?.chunkCount ?? 0) || 0;
}

function getMaterialTime(material) {
  const value = material?.created_at || material?.uploaded_at || material?.upload_time || material?.updated_at || "";
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function formatRecentUpload(materials) {
  const latest = [...(materials || [])].sort((a, b) => getMaterialTime(b) - getMaterialTime(a))[0];
  const time = getMaterialTime(latest);
  if (!time) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(time));
}

function getCourseInitials(course, index) {
  const known = {
    程序设计基础: "PF",
    "C 语言程序设计": "C",
    "Python 程序设计": "PY",
    "Java 程序设计": "JA",
    面向对象程序设计: "OO",
    数据结构: "DS",
    离散数学: "DM",
    操作系统: "OS",
    计算机网络: "CN",
    计算机组成原理: "CO",
    数据库系统: "DB",
    算法设计与分析: "AL",
    编译原理: "CP",
    软件工程: "SE",
    数字逻辑: "DL",
    "Linux 系统基础": "LX",
  };
  return known[course] || COURSE_THEMES[index % COURSE_THEMES.length].icon;
}

function UserCard({ user, apiBase, onProfile, planLabel }) {
  const name = user?.nickname || user?.username || "同学";
  const hasAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");

  return (
    <button className="clh-user-card" type="button" aria-label="个人信息" onClick={onProfile}>
      {hasAvatar ? (
        <img className="clh-user-avatar" src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}`} alt="头像" />
      ) : (
        <span className="clh-user-avatar clh-user-avatar--text">{name.charAt(0).toUpperCase()}</span>
      )}
      <span className="clh-user-meta">
        <strong>{name}</strong>
        <span>{planLabel || "免费模式"}</span>
      </span>
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
  const [entitlements, setEntitlements] = useState(null);
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
    fetch(`${apiBase}/course-learning/entitlements?username=${encodeURIComponent(user.username)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setEntitlements(data))
      .catch(() => setEntitlements(null));
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
    return COURSE_DISPLAY_NAMES.filter((course) => !selected.has(normalizeCourseName(course)));
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

  const planItems = [];

  const totalSize = materials.reduce((sum, item) => sum + Number(item.file_size || 0), 0);
  const indexedMaterialCount = materials.filter((item) => {
    const status = String(item.parse_status || item.index_status || "").toLowerCase();
    return Number(getMaterialChunkCount(item)) > 0 || status === "success" || status === "partial" || status === "indexed";
  }).length;
  const knowledgeChunkCount = materials.reduce((sum, item) => sum + getMaterialChunkCount(item), 0);
  const recentUploadText = formatRecentUpload(materials);
  const uploadLimitMb = entitlements?.upload_limits?.single_file_size_mb || entitlements?.permissions?.material_upload_limit_mb || 0;
  const uploadLimitText = uploadLimitMb ? (Number(uploadLimitMb) >= 1024 ? `${Number(uploadLimitMb) / 1024} GB` : `${uploadLimitMb} MB`) : "未获取";
  const overviewStats = [
    { key: "total", label: "资料总数", value: `${materials.length}`, hint: "份" },
    { key: "indexed", label: "AI 索引", value: `${indexedMaterialCount}`, hint: "份" },
    { key: "chunks", label: "知识片段", value: knowledgeChunkCount.toLocaleString("zh-CN"), hint: "个" },
    { key: "recent", label: "最近上传", value: recentUploadText, hint: "" },
  ];

  const openCourse = (course) => {
    const courseName = normalizeCourseName(course);
    const learningGoal = courseGoals[courseName] || courseGoals[course] || "平日学习";
    const courseContext = {
      id: courseName,
      courseId: courseName,
      name: courseName,
      title: courseName,
      courseName,
      courseTitle: courseName,
      subject: courseName,
      learningGoal,
      learning_goal: learningGoal,
      track: "course_learning",
      serviceKey: "course_learning",
    };
    if (courseName && setSubject) setSubject(courseName);
    setPage("dashboard", courseContext);
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
          <UserCard user={user} apiBase={apiBase} planLabel={entitlements?.plan_label || "免费模式"} onProfile={() => setPage?.("courseProfile")} />
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
              {planItems.length === 0 && (
                <div className="clh-plan-empty">
                  <strong>暂无今日学习计划</strong>
                  <span>进入具体课程后，可在学习计划中查看课程任务。</span>
                </div>
              )}
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
            <div className="clh-material-overview">
              <div className="clh-material-stats">
                {overviewStats.map((item) => (
                  <div className="clh-material-stat" key={item.key}>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    {item.hint && <em>{item.hint}</em>}
                  </div>
                ))}
              </div>
              <p className="clh-material-note">
                当前课程资料已同步到资料库，可用于 AI 问答、知识整理与学习计划生成。
              </p>
            </div>
            <div className="clh-storage">
              <span>已上传 {materials.length} 份资料 · 合计 {formatSize(totalSize)} · 单文件上限 {uploadLimitText}</span>
              <div className="clh-storage-track">
                <span style={{ width: `${materials.length > 0 ? 6 : 0}%` }} />
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
