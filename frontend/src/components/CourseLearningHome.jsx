import { useEffect, useMemo, useRef, useState } from "react";
import "./CourseLearningHome.css";
import { COURSE_DISPLAY_NAMES, normalizeCourseLearningName } from "../courseLearningCatalog.js";

const MODE_LABELS = {
  daily: "平日学习",
  exam: "考前突击",
};

const COURSE_THEMES = [
  { icon: "DS", tone: "purple" },
  { icon: "DM", tone: "blue" },
  { icon: "OS", tone: "green" },
  { icon: "CN", tone: "cyan" },
  { icon: "DB", tone: "orange" },
  { icon: "AI", tone: "violet" },
];

function uniqueValues(values) {
  return Array.from(new Set((values || []).map((item) => `${item || ""}`.trim()).filter(Boolean)));
}

function normalizeCourseName(course) {
  return normalizeCourseLearningName(course) || `${course || ""}`.trim();
}

function getCourseInitials(course, index) {
  const ascii = `${course || ""}`.match(/[A-Za-z]+/g)?.join("") || "";
  if (ascii) return ascii.slice(0, 2).toUpperCase();
  return COURSE_THEMES[index % COURSE_THEMES.length].icon;
}

function formatDate(value) {
  if (!value) return "无日期";
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) return `${value}`.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit" }).format(time);
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "0 MB";
  if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
  return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
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
}) {
  const [onboarding, setOnboarding] = useState(null);
  const [courses, setCourses] = useState([]);
  const [coursesLoading, setCoursesLoading] = useState(false);
  const [coursesError, setCoursesError] = useState("");
  const [todayPlan, setTodayPlan] = useState([]);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState("");
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [pendingCourse, setPendingCourse] = useState("");
  const [pendingGoal, setPendingGoal] = useState("daily");
  const [saveError, setSaveError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [settingsCourse, setSettingsCourse] = useState(null);
  const [settingsForm, setSettingsForm] = useState({ display_name: "", note: "", default_mode: "daily", primary_mode: "daily", show_mode_priority: true });
  const [settingsError, setSettingsError] = useState("");
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [entitlements, setEntitlements] = useState(null);
  const loadMaterialsRef = useRef(loadMaterials);

  useEffect(() => {
    loadMaterialsRef.current = loadMaterials;
  }, [loadMaterials]);

  const authHeaders = useMemo(() => ({
    Authorization: `Bearer ${encodeURIComponent(user?.username || "")}`,
  }), [user?.username]);

  const loadOnboarding = async () => {
    if (!user?.username) return null;
    const res = await fetch(`${apiBase}/course-learning/onboarding`, { headers: authHeaders });
    if (!res.ok) throw new Error("课程选择信息读取失败");
    const data = await res.json();
    setOnboarding(data);
    return data;
  };

  const loadCourses = async () => {
    if (!user?.username) return;
    setCoursesLoading(true);
    setCoursesError("");
    try {
      const res = await fetch(`${apiBase}/course-learning/courses?username=${encodeURIComponent(user.username)}`, { headers: authHeaders });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "我的课程读取失败");
      setCourses(Array.isArray(data.courses) ? data.courses : []);
    } catch (error) {
      setCourses([]);
      setCoursesError(error.message || "我的课程读取失败");
    } finally {
      setCoursesLoading(false);
    }
  };

  const loadTodayPlan = async () => {
    if (!user?.username) return;
    setPlanLoading(true);
    setPlanError("");
    try {
      const res = await fetch(`${apiBase}/course-learning/today-plan?username=${encodeURIComponent(user.username)}`, { headers: authHeaders });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "今日计划读取失败");
      setTodayPlan(Array.isArray(data.items) ? data.items : []);
    } catch (error) {
      setTodayPlan([]);
      setPlanError(error.message || "今日计划读取失败");
    } finally {
      setPlanLoading(false);
    }
  };

  useEffect(() => {
    if (!user?.username) return;
    loadOnboarding().catch(() => setOnboarding(null));
    loadCourses();
    loadTodayPlan();
    fetch(`${apiBase}/course-learning/entitlements?username=${encodeURIComponent(user.username)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setEntitlements(data))
      .catch(() => setEntitlements(null));
  }, [apiBase, authHeaders, user?.username]);

  useEffect(() => {
    if (!user?.username || !loadMaterialsRef.current) return;
    loadMaterialsRef.current("");
  }, [user?.username]);

  const selectedCourseNames = useMemo(() => new Set(courses.map((course) => normalizeCourseName(course.name || course.display_name || course.course_id))), [courses]);

  const availableCourses = useMemo(() => {
    return COURSE_DISPLAY_NAMES.filter((course) => !selectedCourseNames.has(normalizeCourseName(course)));
  }, [selectedCourseNames]);

  const courseCards = courses.map((course, index) => {
    const theme = COURSE_THEMES[index % COURSE_THEMES.length];
    return {
      ...course,
      icon: getCourseInitials(course.display_name || course.name || course.course_id, index),
      tone: theme.tone,
      displayName: course.display_name || course.name || course.course_id,
      primaryMode: course.primary_mode || "daily",
      defaultMode: course.default_mode || "daily",
    };
  });

  const totalSize = materials.reduce((sum, item) => sum + Number(item.file_size || 0), 0);
  const recentUploadText = formatRecentUpload(materials);
  const uploadLimitMb = entitlements?.upload_limits?.single_file_size_mb || entitlements?.permissions?.material_upload_limit_mb || 0;
  const uploadLimitText = uploadLimitMb ? (Number(uploadLimitMb) >= 1024 ? `${Number(uploadLimitMb) / 1024} GB` : `${uploadLimitMb} MB`) : "未获取";
  const overviewStats = [
    { key: "total", label: "资料总数", value: `${materials.length}`, hint: "份" },
    { key: "courses", label: "已选课程", value: `${courses.length}`, hint: "门" },
    { key: "plans", label: "今日计划", value: `${todayPlan.length}`, hint: "项" },
    { key: "recent", label: "最近上传", value: recentUploadText, hint: "" },
  ];

  const buildCourseContext = (course, mode = course?.default_mode || "daily") => {
    const courseName = course?.course_id || course?.subject || course?.displayName || course?.name;
    const learningGoal = MODE_LABELS[mode] || "平日学习";
    return {
      id: courseName,
      courseId: courseName,
      name: course.displayName || course.name || courseName,
      title: course.displayName || course.name || courseName,
      courseName: course.displayName || course.name || courseName,
      courseTitle: course.displayName || course.name || courseName,
      subject: courseName,
      learningGoal,
      learning_goal: learningGoal,
      track: "course_learning",
      serviceKey: "course_learning",
    };
  };

  const openCourse = (course, mode = course?.default_mode || "daily") => {
    const courseName = course?.course_id || course?.subject || course?.displayName || course?.name;
    if (courseName && setSubject) setSubject(courseName);
    setPage("dashboard", buildCourseContext(course, mode));
  };

  const openAddModal = () => {
    setPendingCourse(availableCourses[0] || "");
    setPendingGoal("daily");
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
      setSaveError("请选择一门课程");
      return;
    }
    setIsSaving(true);
    setSaveError("");
    try {
      const current = onboarding || await loadOnboarding();
      const existingCourses = Array.isArray(current?.selected_courses) ? current.selected_courses : [];
      const nextCourses = uniqueValues([...existingCourses, pendingCourse]);
      const nextGoals = { ...(current?.course_goals || {}), [pendingCourse]: MODE_LABELS[pendingGoal] || "平日学习" };
      const res = await fetch(`${apiBase}/course-learning/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({
          major: current?.major || user?.major || "其他专业",
          grade: current?.grade || user?.grade || "暂不确定",
          selected_courses: nextCourses,
          material_types: Array.isArray(current?.material_types) ? current.material_types : [],
          plan: current?.plan || "free",
          onboarding_completed: true,
          course_goals: nextGoals,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "课程加入失败");
      setOnboarding(data?.onboarding || null);
      setIsAddModalOpen(false);
      await loadCourses();
      await loadTodayPlan();
    } catch (error) {
      setSaveError(error.message || "课程加入失败");
    } finally {
      setIsSaving(false);
    }
  };

  const openSettings = (event, course) => {
    event.stopPropagation();
    setSettingsCourse(course);
    setSettingsForm({
      display_name: course.display_name || course.name || "",
      note: course.note || "",
      default_mode: course.default_mode || "daily",
      primary_mode: course.primary_mode || "daily",
      show_mode_priority: course.show_mode_priority !== false,
    });
    setSettingsError("");
  };

  const saveSettings = async () => {
    if (!settingsCourse) return;
    setSettingsSaving(true);
    setSettingsError("");
    try {
      const res = await fetch(`${apiBase}/course-learning/courses/${encodeURIComponent(settingsCourse.course_id)}/settings?username=${encodeURIComponent(user.username)}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify(settingsForm),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "课程设置保存失败");
      setSettingsCourse(null);
      await loadCourses();
      await loadTodayPlan();
    } catch (error) {
      setSettingsError(error.message || "课程设置保存失败");
    } finally {
      setSettingsSaving(false);
    }
  };

  const savePlanOrder = async (items) => {
    setTodayPlan(items);
    try {
      const res = await fetch(`${apiBase}/course-learning/today-plan/order`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders,
        },
        body: JSON.stringify({ username: user.username, ordered_ids: items.map((item) => item.id) }),
      });
      if (!res.ok) throw new Error("order save failed");
    } catch {
      setPlanError("顺序保存失败，请刷新后重试");
    }
  };

  const movePlanItem = (index, direction) => {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= todayPlan.length) return;
    const current = todayPlan[index];
    const target = todayPlan[nextIndex];
    if (current.urgency_rank !== target.urgency_rank) return;
    const next = [...todayPlan];
    next[index] = target;
    next[nextIndex] = current;
    savePlanOrder(next);
  };

  return (
    <div className="clh-page">
      <div className="clh-shell">
        <header className="clh-hero">
          <div>
            <h1>课程学习首页</h1>
            <p>按课程整理资料、计划和学习入口，今天先做最重要的一项。</p>
          </div>
          <UserCard user={user} apiBase={apiBase} planLabel={entitlements?.plan_label || "免费模式"} onProfile={() => setPage?.("courseProfile")} />
        </header>

        <section className="clh-card clh-courses-card">
          <div className="clh-section-title">
            <h2>我的课程</h2>
            <span />
          </div>
          <div className="clh-course-row">
            {coursesLoading && <div className="clh-inline-state">正在读取你的课程...</div>}
            {coursesError && <div className="clh-inline-error">{coursesError}</div>}
            {!coursesLoading && !coursesError && courseCards.length === 0 && (
              <div className="clh-empty-course">
                <strong>还没有已选课程</strong>
                <span>从 onboarding 或“添加课程”选择后，这里会显示真实后端课程。</span>
              </div>
            )}
            {courseCards.map((course, index) => (
              <article
                key={course.course_id}
                className={`clh-course-card clh-course-card--${course.tone}${index === 0 ? " is-active" : ""}`}
              >
                <button className="clh-course-main" type="button" onClick={() => openCourse(course, course.defaultMode)}>
                  <span className="clh-course-visual">{course.icon}</span>
                  <span className="clh-course-text">
                    <strong>{course.displayName}</strong>
                    <small>{course.note || `${course.material_count || 0} 份资料 · ${course.pending_task_count || 0} 个计划`}</small>
                  </span>
                </button>
                <div className="clh-mode-actions">
                  <button type="button" className={course.primaryMode === "daily" ? "is-primary" : ""} onClick={() => openCourse(course, "daily")}>平日学习</button>
                  <button type="button" className={course.primaryMode === "exam" ? "is-primary" : ""} onClick={() => openCourse(course, "exam")}>考前突击</button>
                </div>
                <button className="clh-course-settings" type="button" onClick={(event) => openSettings(event, course)}>设置</button>
              </article>
            ))}
            <button className="clh-add-course" type="button" onClick={openAddModal}>
              <span>+</span>
              <strong>添加课程</strong>
            </button>
          </div>
        </section>

        <div className="clh-main-grid">
          <section className="clh-card clh-plan-card">
            <div className="clh-panel-heading">
              <span className="clh-panel-icon clh-panel-icon--calendar">日</span>
              <h2>今日计划</h2>
            </div>
            <div className="clh-plan-list">
              {planLoading && <div className="clh-plan-empty"><strong>正在读取真实计划...</strong></div>}
              {planError && <div className="clh-inline-error">{planError}</div>}
              {!planLoading && !planError && todayPlan.length === 0 && (
                <div className="clh-plan-empty">
                  <strong>暂无今日计划</strong>
                  <span>进入具体课程后创建学习计划，这里会按紧急程度汇总。</span>
                </div>
              )}
              {todayPlan.map((item, index) => {
                const canMoveUp = index > 0 && todayPlan[index - 1]?.urgency_rank === item.urgency_rank;
                const canMoveDown = index < todayPlan.length - 1 && todayPlan[index + 1]?.urgency_rank === item.urgency_rank;
                return (
                  <div className="clh-plan-item" key={item.id}>
                    <span className={`clh-urgency-rank clh-urgency-rank--${item.urgency_rank}`}>{item.urgency_rank}</span>
                    <div className="clh-plan-body">
                      <strong>{item.title}</strong>
                      <span>{item.course_name}</span>
                      <em>{item.mode_label} · {formatDate(item.due_date)} · {item.urgency_label}</em>
                    </div>
                    <div className="clh-plan-actions">
                      <button type="button" disabled={!canMoveUp} onClick={() => movePlanItem(index, -1)}>上移</button>
                      <button type="button" disabled={!canMoveDown} onClick={() => movePlanItem(index, 1)}>下移</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="clh-card clh-material-card">
            <div className="clh-panel-heading">
              <span className="clh-panel-icon clh-panel-icon--folder">库</span>
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
              <p className="clh-material-note">旧资料保留在资料库中；通用资料会同时服务平日学习和考前突击。</p>
            </div>
            <div className="clh-storage">
              <span>已上传 {materials.length} 份资料 · 合计 {formatSize(totalSize)} · 单文件上限 {uploadLimitText}</span>
              <div className="clh-storage-track">
                <span style={{ width: `${materials.length > 0 ? 6 : 0}%` }} />
              </div>
            </div>
          </section>
        </div>
      </div>

      {isAddModalOpen && (
        <div className="clh-modal-backdrop" role="presentation" onMouseDown={closeAddModal}>
          <section className="clh-add-modal" role="dialog" aria-modal="true" aria-labelledby="clh-add-course-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="clh-modal-close" type="button" onClick={closeAddModal} aria-label="关闭">x</button>
            <div className="clh-modal-header">
              <span>添加课程</span>
              <h2 id="clh-add-course-title">选择要加入“我的课程”的课程</h2>
              <p>保存后会写入后端 onboarding 数据，刷新后仍然保留。</p>
            </div>
            <div className="clh-modal-section">
              <h3>可选课程</h3>
              {availableCourses.length > 0 ? (
                <div className="clh-course-picker">
                  {availableCourses.map((course) => (
                    <button className={`clh-picker-item${pendingCourse === course ? " is-selected" : ""}`} type="button" key={course} onClick={() => setPendingCourse(course)}>
                      {course}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="clh-empty-picker">当前目录课程都已加入。</p>
              )}
            </div>
            <div className="clh-modal-section">
              <h3>默认模式</h3>
              <div className="clh-goal-toggle" role="radiogroup" aria-label="默认模式">
                {Object.entries(MODE_LABELS).map(([mode, label]) => (
                  <button className={`clh-goal-option${pendingGoal === mode ? " is-selected" : ""}`} type="button" role="radio" aria-checked={pendingGoal === mode} key={mode} onClick={() => setPendingGoal(mode)}>
                    {label}
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

      {settingsCourse && (
        <div className="clh-modal-backdrop" role="presentation" onMouseDown={() => !settingsSaving && setSettingsCourse(null)}>
          <section className="clh-add-modal" role="dialog" aria-modal="true" aria-labelledby="clh-settings-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="clh-modal-close" type="button" onClick={() => setSettingsCourse(null)} aria-label="关闭">x</button>
            <div className="clh-modal-header">
              <span>课程设置</span>
              <h2 id="clh-settings-title">{settingsCourse.displayName}</h2>
              <p>只调整显示和模式优先级，不删除资料、计划或学习记录。</p>
            </div>
            <div className="clh-settings-grid">
              <label>
                显示名称
                <input value={settingsForm.display_name} onChange={(event) => setSettingsForm((prev) => ({ ...prev, display_name: event.target.value }))} />
              </label>
              <label>
                课程备注
                <textarea value={settingsForm.note} onChange={(event) => setSettingsForm((prev) => ({ ...prev, note: event.target.value }))} rows={3} />
              </label>
              <label>
                默认进入模式
                <select value={settingsForm.default_mode} onChange={(event) => setSettingsForm((prev) => ({ ...prev, default_mode: event.target.value }))}>
                  <option value="daily">平日学习</option>
                  <option value="exam">考前突击</option>
                </select>
              </label>
              <label>
                当前主模式
                <select value={settingsForm.primary_mode} onChange={(event) => setSettingsForm((prev) => ({ ...prev, primary_mode: event.target.value }))}>
                  <option value="daily">平日学习</option>
                  <option value="exam">考前突击</option>
                </select>
              </label>
              <label className="clh-checkbox-row">
                <input type="checkbox" checked={settingsForm.show_mode_priority} onChange={(event) => setSettingsForm((prev) => ({ ...prev, show_mode_priority: event.target.checked }))} />
                显示主模式优先级
              </label>
            </div>
            {settingsError && <p className="clh-modal-error">{settingsError}</p>}
            <div className="clh-modal-actions">
              <button className="clh-modal-secondary" type="button" onClick={() => setSettingsCourse(null)} disabled={settingsSaving}>取消</button>
              <button className="clh-modal-primary" type="button" onClick={saveSettings} disabled={settingsSaving}>
                {settingsSaving ? "保存中..." : "保存设置"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
