import { useEffect, useState } from "react";

const MAJOR_OPTIONS = [
  "计算机科学与技术",
  "软件工程",
  "人工智能",
  "数据科学与大数据技术",
  "网络工程",
  "信息安全",
  "物联网工程",
  "其他专业",
];

const GRADE_OPTIONS = ["大一", "大二", "大三", "大四", "研究生", "已工作"];

const COURSE_OPTIONS = [
  "数据结构",
  "操作系统",
  "计算机网络",
  "计算机组成原理",
  "C 语言",
  "Python",
  "Java",
  "离散数学",
  "数据库系统",
  "算法设计与分析",
  "编译原理",
  "软件工程",
];

const MATERIAL_OPTIONS = ["PPT", "教材", "作业", "往年卷", "笔记", "暂时没有"];
const EMPTY_MATERIAL = "暂时没有";

function uniqueValues(values) {
  return Array.from(new Set((values || []).filter(Boolean)));
}

export default function CourseLearningOnboarding({
  user,
  apiBase,
  initialData,
  onComplete,
  onBack,
}) {
  const [major, setMajor] = useState("");
  const [grade, setGrade] = useState("");
  const [selectedCourses, setSelectedCourses] = useState([]);
  const [materialTypes, setMaterialTypes] = useState([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMajor(initialData?.major || user?.major || "");
    setGrade(initialData?.grade || user?.grade || "");
    setSelectedCourses(uniqueValues(initialData?.selected_courses));
    setMaterialTypes(uniqueValues(initialData?.material_types));
  }, [initialData, user?.major, user?.grade]);

  const toggleCourse = (course) => {
    setSelectedCourses((prev) =>
      prev.includes(course) ? prev.filter((item) => item !== course) : [...prev, course]
    );
    setMessage("");
  };

  const toggleMaterial = (material) => {
    setMaterialTypes((prev) => {
      if (material === EMPTY_MATERIAL) {
        return prev.includes(EMPTY_MATERIAL) ? [] : [EMPTY_MATERIAL];
      }
      const withoutEmpty = prev.filter((item) => item !== EMPTY_MATERIAL);
      return withoutEmpty.includes(material)
        ? withoutEmpty.filter((item) => item !== material)
        : [...withoutEmpty, material];
    });
  };

  const handleSubmit = async () => {
    if (!major.trim()) {
      setMessage("请选择你的专业，我们会据此推荐更贴近课程体系的入口。");
      return;
    }
    if (!grade.trim()) {
      setMessage("请选择你的年级，方便调整学习节奏。");
      return;
    }
    if (selectedCourses.length === 0) {
      setMessage("请选择至少一门想学习的课程。");
      return;
    }
    if (!user?.username) {
      setMessage("登录状态已失效，请重新登录后再试。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const res = await fetch(`${apiBase}/course-learning/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${user.username}`,
        },
        body: JSON.stringify({
          major,
          grade,
          selected_courses: selectedCourses,
          material_types: materialTypes,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.detail || "保存失败，请稍后再试。");
        return;
      }
      onComplete?.(data);
    } catch (error) {
      console.error("Failed to save course learning onboarding:", error);
      setMessage("暂时无法保存学习详情，请检查网络后重试。");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="course-onboarding-page">
      <section className="course-onboarding-card" aria-label="课程学习详情引导">
        <div className="course-onboarding-header">
          <div className="course-onboarding-step">第 2 步</div>
          <h1>学习详情</h1>
          <p>请补充你的课程学习信息，我们将为你制定更合适的学习内容与功能入口</p>
        </div>

        <div className="course-onboarding-section">
          <h2>1. 你的专业、年级？</h2>
          <div className="course-onboarding-select-row">
            <label className="course-onboarding-select-wrap">
              <span className="course-onboarding-select-icon">专</span>
              <select value={major} onChange={(event) => { setMajor(event.target.value); setMessage(""); }}>
                <option value="">请选择专业</option>
                {MAJOR_OPTIONS.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="course-onboarding-select-wrap">
              <span className="course-onboarding-select-icon">级</span>
              <select value={grade} onChange={(event) => { setGrade(event.target.value); setMessage(""); }}>
                <option value="">请选择年级</option>
                {GRADE_OPTIONS.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="course-onboarding-section">
          <h2>2. 想学习哪些课程？（多选）</h2>
          <div className="course-onboarding-chip-grid course-onboarding-chip-grid--courses">
            {COURSE_OPTIONS.map((course) => (
              <button
                key={course}
                type="button"
                className={`course-onboarding-chip ${selectedCourses.includes(course) ? "is-selected" : ""}`}
                onClick={() => toggleCourse(course)}
              >
                {course}
              </button>
            ))}
          </div>
        </div>

        <div className="course-onboarding-section">
          <h2>3. 是否已有课程资料？</h2>
          <div className="course-onboarding-chip-grid course-onboarding-chip-grid--materials">
            {MATERIAL_OPTIONS.map((material) => (
              <button
                key={material}
                type="button"
                className={`course-onboarding-material ${materialTypes.includes(material) ? "is-selected" : ""}`}
                onClick={() => toggleMaterial(material)}
              >
                <span className="course-onboarding-material-icon">{material === "暂时没有" ? "无" : material.slice(0, 1)}</span>
                <span>{material}</span>
              </button>
            ))}
          </div>
        </div>

        {message && <div className="course-onboarding-message">{message}</div>}

        <div className="course-onboarding-actions">
          <button type="button" className="course-onboarding-back" onClick={onBack} disabled={saving}>
            上一步
          </button>
          <button type="button" className="course-onboarding-next" onClick={handleSubmit} disabled={saving}>
            {saving ? "保存中..." : "下一步"}
          </button>
        </div>
      </section>
    </div>
  );
}
