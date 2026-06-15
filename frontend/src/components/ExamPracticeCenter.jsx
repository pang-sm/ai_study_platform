import { useEffect, useMemo, useState } from "react";
import ExamPastPaperPractice from "./ExamPastPaperPractice.jsx";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: { label: "数据结构", shortLabel: "数据结构", courseId: "data_structure_11408" },
  computer_organization: { label: "计算机组成原理", shortLabel: "计组", courseId: "computer_organization_11408" },
  operating_system: { label: "操作系统", shortLabel: "操作系统", courseId: "operating_system_11408" },
  computer_network: { label: "计算机网络", shortLabel: "计网", courseId: "computer_network_11408" },
};

const SOURCE_LABELS = {
  past_paper: "真题练习",
  chapter_practice: "章节练习",
  ai_generated: "AI 出题",
};

async function safeJsonFetch(url, options = {}) {
  const res = await fetch(url, options);
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(payload.detail || "请求失败");
  return payload;
}

function flattenKnowledge(nodes = []) {
  const items = [];
  const walk = (list, path = []) => {
    list.forEach((node) => {
      const currentPath = [...path, node.title || node.name || node.code || ""].filter(Boolean);
      items.push({ ...node, path: currentPath.join(" / ") });
      if (node.children?.length) walk(node.children, currentPath);
    });
  };
  walk(nodes);
  return items;
}

function KnowledgeTree({ nodes = [], selectedCode, onSelect }) {
  const [expanded, setExpanded] = useState(() => new Set(nodes.map((n) => n.code || n.id)));

  useEffect(() => {
    setExpanded(new Set(nodes.map((n) => n.code || n.id)));
  }, [nodes]);

  const renderNode = (node, depth = 0) => {
    const key = node.code || node.id || `${node.title}-${depth}`;
    const hasChildren = Boolean(node.children?.length);
    const isExpanded = expanded.has(key);
    const isSelected = selectedCode === key;
    return (
      <div key={key} className="exam-knowledge-node">
        <div
          className={`exam-knowledge-node-row${isSelected ? " exam-knowledge-node-row--active" : ""}`}
          style={{ paddingLeft: 12 + depth * 18 }}
          onClick={() => onSelect(node)}
        >
          {hasChildren ? (
            <button
              type="button"
              className="exam-knowledge-toggle"
              onClick={(event) => {
                event.stopPropagation();
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                });
              }}
              aria-label={isExpanded ? "收起" : "展开"}
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="exam-knowledge-toggle-placeholder" />
          )}
          <span className="exam-knowledge-node-title">{node.code ? `${node.code} ` : ""}{node.title || node.name}</span>
        </div>
        {hasChildren && isExpanded && (
          <div className="exam-knowledge-children">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return <div className="exam-knowledge-tree">{nodes.map((node) => renderNode(node))}</div>;
}

function PracticeSubPageHeader({ title, subtitle, subjectInfo, onBack }) {
  return (
    <div className="exam-practice-subpage-header">
      <button type="button" className="ghost-button compact" onClick={onBack}>← 返回练习中心</button>
      <div>
        <h2>{title}</h2>
        <p>{subtitle}</p>
        <span className="exam-practice-subject-pill">当前科目：{subjectInfo.label}</span>
      </div>
    </div>
  );
}

function ChapterPracticePage({ subjectInfo, user, onBack }) {
  const [mapData, setMapData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams({ course_id: subjectInfo.courseId });
    if (user?.username) params.set("username", user.username);
    setLoading(true);
    safeJsonFetch(`${API_BASE}/knowledge-map?${params.toString()}`)
      .then((payload) => {
        setMapData(payload);
        setSelected(payload.chapters?.[0] || null);
      })
      .catch((err) => setError(err.message || "知识点大纲加载失败"))
      .finally(() => setLoading(false));
  }, [subjectInfo.courseId, user?.username]);

  const chapters = mapData?.chapters || [];

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="章节练习" subtitle="按知识点体系进行针对性练习" subjectInfo={subjectInfo} onBack={onBack} />
      {loading ? <div className="past-paper-loading">正在加载知识点大纲...</div> : error ? (
        <div className="km-inline-message km-inline-message--error">{error}</div>
      ) : (
        <div className="exam-practice-split">
          <section className="exam-practice-panel exam-practice-outline-panel">
            <h3>知识点大纲</h3>
            <KnowledgeTree nodes={chapters} selectedCode={selected?.code || selected?.id} onSelect={setSelected} />
          </section>
          <section className="exam-practice-panel exam-practice-question-panel">
            <div className="exam-practice-panel-title">
              <h3>{selected?.title || selected?.name || "请选择知识点"}</h3>
              {selected?.code && <span>{selected.code}</span>}
            </div>
            <div className="exam-practice-empty-state">
              <strong>当前知识点暂未录入练习题</strong>
              <p>后续可在题库中补充。</p>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function WrongPracticePage({ subjectKey, subjectInfo, user, onBack }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadItems = () => {
    if (!user?.username) {
      setError("请先登录后查看错题练习。");
      setLoading(false);
      return;
    }
    const params = new URLSearchParams({ username: user.username });
    if (filter !== "all") params.set("source", filter);
    setLoading(true);
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/wrong-questions?${params.toString()}`)
      .then((payload) => {
        setItems(payload.items || []);
        setError("");
      })
      .catch((err) => setError(err.message || "错题加载失败"))
      .finally(() => setLoading(false));
  };

  useEffect(loadItems, [subjectKey, user?.username, filter]);

  const removeWrong = async (item) => {
    await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/wrong-questions/${item.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    loadItems();
  };

  const markMastered = async (item) => {
    await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/wrong-questions/${item.id}/mastered`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user.username }),
    });
    loadItems();
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="错题练习" subtitle="系统批改后自动收集当前用户的错题" subjectInfo={subjectInfo} onBack={onBack} />
      <div className="exam-practice-filter-row">
        {[
          ["all", "全部"],
          ["chapter_practice", "章节练习错题"],
          ["past_paper", "真题错题"],
          ["ai_generated", "AI 出题错题"],
        ].map(([value, label]) => (
          <button key={value} type="button" className={`past-paper-chip${filter === value ? " past-paper-chip--active" : ""}`} onClick={() => setFilter(value)}>{label}</button>
        ))}
      </div>
      {loading ? <div className="past-paper-loading">正在加载错题...</div> : error ? (
        <div className="km-inline-message km-inline-message--error">{error}</div>
      ) : items.length === 0 ? (
        <div className="exam-practice-empty-state">
          <strong>暂无错题，继续练习后这里会自动收集。</strong>
        </div>
      ) : (
        <div className="exam-practice-list">
          {items.map((item) => (
            <article key={`${item.source}-${item.id}`} className="exam-practice-question-item">
              <div className="past-paper-question-meta">
                <span className="past-paper-q-type">{SOURCE_LABELS[item.source] || item.source}</span>
                {item.year && <span className="past-paper-q-year">{item.year} 年 第 {item.number} 题</span>}
                <span className="past-paper-q-number">{item.question_type}</span>
                {item.mastered && <span className="past-paper-q-result-tag past-paper-q-result-tag--correct">已掌握</span>}
              </div>
              <div className="past-paper-q-content">{item.stem || "题干暂缺"}</div>
              <div className="past-paper-q-answer-row"><span className="past-paper-q-label">你的答案：</span><span className="text-wrong">{item.user_answer || "未作答"}</span></div>
              <div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{item.standard_answer || "暂无"}</span></div>
              {item.feedback && <div className="past-paper-q-feedback"><p>{item.feedback}</p></div>}
              <div className="exam-practice-action-row">
                <button type="button" className="ghost-button compact">AI 解析</button>
                <button type="button" className="ghost-button compact" onClick={() => removeWrong(item)}>移出错题本</button>
                <button type="button" className="primary-button compact" onClick={() => markMastered(item)}>标记已掌握</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function FavoritePracticePage({ subjectKey, subjectInfo, user, onBack }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadItems = () => {
    if (!user?.username) {
      setError("请先登录后查看收藏练习。");
      setLoading(false);
      return;
    }
    const params = new URLSearchParams({ username: user.username });
    setLoading(true);
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/favorites?${params.toString()}`)
      .then((payload) => {
        setItems(payload.items || []);
        setError("");
      })
      .catch((err) => setError(err.message || "收藏加载失败"))
      .finally(() => setLoading(false));
  };

  useEffect(loadItems, [subjectKey, user?.username]);

  const removeFavorite = async (item) => {
    await safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/favorites/${item.id}?username=${encodeURIComponent(user.username)}`, { method: "DELETE" });
    loadItems();
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="收藏练习" subtitle="查看并练习当前用户收藏的题目" subjectInfo={subjectInfo} onBack={onBack} />
      {loading ? <div className="past-paper-loading">正在加载收藏题...</div> : error ? (
        <div className="km-inline-message km-inline-message--error">{error}</div>
      ) : items.length === 0 ? (
        <div className="exam-practice-empty-state">
          <strong>暂无收藏题目</strong>
          <p>在真题答题页点击“☆ 收藏”后，会出现在这里。</p>
        </div>
      ) : (
        <div className="exam-practice-list">
          {items.map((item) => (
            <article key={item.id} className="exam-practice-question-item">
              <div className="past-paper-question-meta">
                <span className="past-paper-q-type">{SOURCE_LABELS[item.source] || item.source}</span>
                {item.year && <span className="past-paper-q-year">{item.year} 年 第 {item.number} 题</span>}
                <span className="past-paper-q-number">{item.question_type}</span>
              </div>
              <div className="past-paper-q-content">{item.stem || "题干暂缺"}</div>
              <div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{item.standard_answer || "暂无"}</span></div>
              <div className="exam-practice-action-row">
                <button type="button" className="ghost-button compact">开始练习</button>
                <button type="button" className="ghost-button compact">AI 解析</button>
                <button type="button" className="primary-button compact" onClick={() => removeFavorite(item)}>取消收藏</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function AIQuestionPracticePage({ subjectInfo, user, onBack }) {
  const [mapData, setMapData] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState("");
  const [questionType, setQuestionType] = useState("choice");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");

  useEffect(() => {
    const params = new URLSearchParams({ course_id: subjectInfo.courseId });
    if (user?.username) params.set("username", user.username);
    safeJsonFetch(`${API_BASE}/knowledge-map?${params.toString()}`)
      .then((payload) => setMapData(payload))
      .catch(() => setMapData({ chapters: [] }));
  }, [subjectInfo.courseId, user?.username]);

  const points = useMemo(() => flattenKnowledge(mapData?.chapters || []), [mapData]);

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="AI 出题" subtitle="根据当前科目知识点，生成贴合 11408 真题风格的练习题" subjectInfo={subjectInfo} onBack={onBack} />
      <div className="exam-practice-split exam-practice-split--ai">
        <section className="exam-practice-panel">
          <h3>出题表单</h3>
          <label className="form-field">
            <span>知识点</span>
            <select className="field" value={selectedPoint} onChange={(event) => setSelectedPoint(event.target.value)}>
              <option value="">请选择知识点</option>
              {points.map((point) => (
                <option key={point.code || point.id || point.path} value={point.code || point.id || point.title}>{point.path}</option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>题型</span>
            <select className="field" value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
              <option value="choice">选择题</option>
              <option value="big">大题</option>
            </select>
          </label>
          <label className="form-field">
            <span>题目数量</span>
            <input className="field" type="number" min="1" max="10" value={count} onChange={(event) => setCount(event.target.value)} />
          </label>
          <label className="form-field">
            <span>难度</span>
            <select className="field" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
              <option value="basic">基础</option>
              <option value="medium">中等</option>
              <option value="advanced">提高</option>
            </select>
          </label>
          <label className="form-field">
            <span>生成要求</span>
            <textarea className="field" rows={4} placeholder="例如：贴近 11408 真题，考查核心概念，不要偏题" />
          </label>
          <button type="button" className="primary-button" disabled>生成题目（后续开放）</button>
        </section>
        <section className="exam-practice-panel">
          <div className="exam-practice-panel-title">
            <h3>AI 题库</h3>
            <span>个人题库</span>
          </div>
          <div className="exam-practice-empty-state">
            <strong>暂无 AI 生成题目</strong>
            <p>题库列表已预留编辑、删除和开始练习入口。</p>
          </div>
          <div className="exam-practice-action-row">
            <button type="button" className="ghost-button compact" disabled>编辑</button>
            <button type="button" className="ghost-button compact" disabled>删除</button>
            <button type="button" className="ghost-button compact" disabled>开始练习</button>
          </div>
        </section>
      </div>
    </div>
  );
}

export default function ExamPracticeCenter({
  subjectKey = "data_structure",
  subjectName = "11408 数据结构",
  user,
}) {
  const subjectInfo = EXAM_SUBJECTS[subjectKey] || EXAM_SUBJECTS.data_structure;
  const [practiceView, setPracticeView] = useState("dashboard");
  const [pastPaperConfig, setPastPaperConfig] = useState(null);
  const [pastPapers, setPastPapers] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-papers`)
      .then((r) => r.json())
      .then((data) => setPastPapers(data))
      .catch(() => setPastPapers({ available: false, resource_files: [] }));
  }, [subjectKey]);

  const availableYears = [];
  if (pastPapers?.resource_files) {
    for (const f of pastPapers.resource_files) {
      for (const y of f.years || []) {
        if (!availableYears.includes(y)) availableYears.push(y);
      }
    }
    availableYears.sort((a, b) => b - a);
  }

  if (practiceView === "pastPaper" && pastPaperConfig) {
    return (
      <ExamPastPaperPractice
        subjectKey={pastPaperConfig.subjectKey}
        subjectName={pastPaperConfig.subjectName}
        years={pastPaperConfig.years}
        questionType={pastPaperConfig.questionType}
        user={user}
        onBack={() => setPracticeView("dashboard")}
      />
    );
  }

  if (practiceView === "chapter") {
    return <ChapterPracticePage subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }
  if (practiceView === "wrong") {
    return <WrongPracticePage subjectKey={subjectKey} subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }
  if (practiceView === "favorite") {
    return <FavoritePracticePage subjectKey={subjectKey} subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }
  if (practiceView === "ai") {
    return <AIQuestionPracticePage subjectInfo={subjectInfo} user={user} onBack={() => setPracticeView("dashboard")} />;
  }

  const cards = [
    { key: "chapter", icon: "📋", title: "章节练习", desc: "按章节知识点进行针对性练习", count: "题目待录入" },
    { key: "wrong", icon: "❌", title: "错题练习", desc: "查看批改后自动收集的个人错题", count: "个人错题本" },
    { key: "favorite", icon: "⭐", title: "收藏练习", desc: "练习自己收藏的题目", count: "个人收藏" },
    { key: "pastPaper", icon: "📜", title: "真题练习", desc: "基于历年 11408 真题进行专项训练", count: "近五年真题", className: "practice-type-card--past" },
    { key: "ai", icon: "🤖", title: "AI 出题", desc: "按知识点生成 11408 风格练习题", count: "个人题库", className: "practice-type-card--ai" },
  ];

  const openCard = (key) => {
    if (key === "pastPaper") {
      setPastPaperConfig({ subjectKey, subjectName, years: availableYears, questionType: "all" });
      setPracticeView("pastPaper");
      return;
    }
    setPracticeView(key);
  };

  return (
    <div className="exam-practice-dashboard">
      <div className="practice-dashboard-header">
        <div>
          <h2>练习中心</h2>
          <p>巩固知识，提升能力</p>
        </div>
      </div>

      <div className="practice-stats-section">
        <h3>练习数据</h3>
        <div className="practice-stats-grid">
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">128</div><div className="practice-stat-card-label">总练习数</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">96</div><div className="practice-stat-card-label">已完成</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">75%</div><div className="practice-stat-card-label">正确率</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">⏱</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">32h</div><div className="practice-stat-card-label">累计练习时长</div></div></div>
        </div>
      </div>

      <div className="practice-type-section">
        <h3>练习类型</h3>
        <div className="practice-type-grid">
          {cards.map((card) => (
            <button key={card.key} type="button" className={`practice-type-card ${card.className || ""}`} onClick={() => openCard(card.key)}>
              <div className="practice-type-icon">{card.icon}</div>
              <div className="practice-type-info">
                <strong>{card.title}</strong>
                <p>{card.desc}</p>
                <span className="practice-type-count">{card.count}</span>
              </div>
              <span className="practice-type-arrow">›</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
