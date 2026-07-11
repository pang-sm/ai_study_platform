import { useEffect, useState } from "react";
import "./ProgrammingOnboarding.css";

const LANGUAGE_OPTIONS = ["C", "Python", "Java", "C++", "暂时不确定"];
const LEVEL_OPTIONS = [
  { key: "零基础", title: "零基础", icon: "rocket" },
  { key: "学过语法", title: "学过语法", icon: "bars" },
];
const PROBLEM_OPTIONS = [
  { key: "概念不熟", title: "概念不熟", desc: "基础概念理解不牢，容易混淆", icon: "brain" },
  { key: "题目思路不足", title: "题目思路不足", desc: "面对编程题时，不清楚解题思路", icon: "puzzle" },
  { key: "缺少系统练习计划", title: "缺少系统练习计划", desc: "不知道每天练什么，缺少规划", icon: "calendar" },
];

function ProgrammingIcon({ type }) {
  if (type === "bars") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 19V9M12 19V5M19 19v-8" />
      </svg>
    );
  }
  if (type === "puzzle") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 3h6v4h2a3 3 0 1 1 0 6h-2v8H9v-3a3 3 0 1 0 0-6V9H3V3h6Z" />
      </svg>
    );
  }
  if (type === "calendar") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 3v4M17 3v4M4 9h16M6 5h12a2 2 0 0 1 2 2v13H4V7a2 2 0 0 1 2-2Z" />
      </svg>
    );
  }
  if (type === "brain") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 4a4 4 0 0 0-4 4v8a4 4 0 0 0 4 4M15 4a4 4 0 0 1 4 4v8a4 4 0 0 1-4 4M9 4v16M15 4v16M5 12h14" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 15c4.5-.7 8.3-4.5 9-9 2.2.5 3.5 1.8 4 4-4.5.7-8.3 4.5-9 9-2.2-.5-3.5-1.8-4-4Z" />
      <path d="M14 6l4-4M9 19l-3 3M10 11l3 3" />
    </svg>
  );
}

export default function ProgrammingOnboardingStep({
  user,
  apiBase = "/api",
  initialData,
  onBack,
  onNext,
  hideBackButton = false,
}) {
  const [language, setLanguage] = useState("Python");
  const [level, setLevel] = useState("零基础");
  const [problems, setProblems] = useState(["概念不熟"]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!initialData) return;
    setLanguage(initialData.main_language || "Python");
    setLevel(initialData.level || "零基础");
    setProblems(Array.isArray(initialData.problems) && initialData.problems.length ? initialData.problems : ["概念不熟"]);
  }, [initialData]);

  useEffect(() => {
    if (initialData || !user?.username) return;
    let alive = true;
    fetch(`${apiBase}/programming/onboarding`, {
      headers: { Authorization: `Bearer ${encodeURIComponent(user.username)}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!alive || !data) return;
        setLanguage(data.main_language || "Python");
        setLevel(data.level || "零基础");
        setProblems(Array.isArray(data.problems) && data.problems.length ? data.problems : ["概念不熟"]);
      })
      .catch(() => {});
    return () => { alive = false; };
  }, [apiBase, initialData, user?.username]);

  const toggleProblem = (key) => {
    setProblems((prev) => (
      prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]
    ));
    setMessage("");
  };

  const handleNext = async () => {
    if (!language) {
      setMessage("请选择主要练习语言");
      return;
    }
    if (!level) {
      setMessage("请选择当前水平");
      return;
    }
    if (!user?.username) {
      setMessage("登录状态已失效，请重新登录后再试");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const res = await fetch(`${apiBase}/programming/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${encodeURIComponent(user.username)}`,
        },
        body: JSON.stringify({
          main_language: language,
          level,
          problems,
          onboarding_completed: false,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "保存编程学习详情失败");
      onNext?.(data);
    } catch (error) {
      setMessage(error.message || "暂时无法保存学习详情，请稍后再试");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="programming-onboarding-page">
      <section className="programming-onboarding-card" aria-label="编程学习详情">
        <div className="programming-onboarding-header">
          <span>第 2 步</span>
          <h1>学习详情</h1>
          <p>请补充你的编程学习信息，我们将为你定制更合适的学习内容与功能入口</p>
        </div>

        <div className="programming-question">
          <h2>1. 你想要练习什么编程语言？</h2>
          <div className="programming-language-grid" role="radiogroup" aria-label="主要练习语言">
            {LANGUAGE_OPTIONS.map((item) => (
              <button
                key={item}
                type="button"
                className={language === item ? "is-selected" : ""}
                role="radio"
                aria-checked={language === item}
                onClick={() => { setLanguage(item); setMessage(""); }}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="programming-question">
          <h2>2. 当前水平？</h2>
          <div className="programming-level-grid" role="radiogroup" aria-label="当前水平">
            {LEVEL_OPTIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={level === item.key ? "is-selected" : ""}
                role="radio"
                aria-checked={level === item.key}
                onClick={() => { setLevel(item.key); setMessage(""); }}
              >
                <span className="programming-icon"><ProgrammingIcon type={item.icon} /></span>
                <strong>{item.title}</strong>
              </button>
            ))}
          </div>
        </div>

        <div className="programming-question">
          <h2>3. 目前代码学习遇到的问题？</h2>
          <div className="programming-problem-grid">
            {PROBLEM_OPTIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                className={problems.includes(item.key) ? "is-selected" : ""}
                onClick={() => toggleProblem(item.key)}
              >
                <span className="programming-icon"><ProgrammingIcon type={item.icon} /></span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.desc}</small>
                </span>
              </button>
            ))}
          </div>
        </div>

        {message && <div className="programming-onboarding-error">{message}</div>}

        <div className="programming-onboarding-actions">
          {!hideBackButton && (
            <button type="button" className="programming-btn-secondary" onClick={onBack} disabled={saving}>上一步</button>
          )}
          <button type="button" className="programming-btn-primary" onClick={handleNext} disabled={saving}>
            {saving ? "保存中..." : "下一步"}
          </button>
        </div>
      </section>
    </div>
  );
}
