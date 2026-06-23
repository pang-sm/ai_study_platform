import { useEffect, useMemo, useRef, useState } from "react";
import "./CourseLearningHome.css";

const COURSE_THEMES = [
  { icon: "DS", tone: "purple", fallback: "数据结构", status: "正在学习" },
  { icon: "DM", tone: "blue", fallback: "离散数学", status: "上次学习 昨天" },
  { icon: "OS", tone: "green", fallback: "操作系统", status: "上次学习 3 天前" },
];

const MATERIAL_TYPES = [
  { key: "slides", label: "课件讲义", hint: "份", tone: "blue", match: ["ppt", "课件", "讲义", "slides"] },
  { key: "books", label: "教材电子书", hint: "本", tone: "orange", match: ["教材", "电子书", "book"] },
  { key: "notes", label: "课堂笔记", hint: "份", tone: "indigo", match: ["笔记", "note"] },
  { key: "exercises", label: "习题集", hint: "份", tone: "cyan", match: ["习题", "作业", "exercise", "homework"] },
  { key: "labs", label: "实验报告", hint: "份", tone: "green", match: ["实验", "报告", "lab"] },
  { key: "reading", label: "拓展阅读", hint: "篇", tone: "violet", match: ["阅读", "论文", "paper", "reference"] },
];

function uniqueValues(values) {
  return Array.from(new Set((values || []).filter(Boolean)));
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

function UserCard({ user, apiBase }) {
  const name = user?.nickname || user?.username || "同学";
  const hasAvatar = (user?.avatar_url || "").startsWith("/me/avatar/");

  return (
    <button className="clh-user-card" type="button" aria-label="个人信息">
      {hasAvatar ? (
        <img className="clh-user-avatar" src={`${apiBase}${user.avatar_url}?username=${encodeURIComponent(user?.username || "")}`} alt="头像" />
      ) : (
        <span className="clh-user-avatar clh-user-avatar--text">{name.charAt(0)}</span>
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

  const selectedCourses = useMemo(() => {
    const fromOnboarding = uniqueValues(onboarding?.selected_courses);
    const base = fromOnboarding.length > 0 ? fromOnboarding : uniqueValues([subject, ...courseOptions]).slice(0, 3);
    return base.slice(0, 3);
  }, [onboarding?.selected_courses, subject, courseOptions]);

  const courseCards = selectedCourses.map((course, index) => ({
    name: getSubjectLabel ? getSubjectLabel(course) : course,
    value: course,
    ...COURSE_THEMES[index % COURSE_THEMES.length],
  }));

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
                  <strong>{course.name || course.fallback}</strong>
                  <small>{course.status}</small>
                </span>
                {index === 0 && <span className="clh-course-check">✓</span>}
              </button>
            ))}
            <button className="clh-add-course" type="button" onClick={() => setPage("dashboard")}>
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
    </div>
  );
}
