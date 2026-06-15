import { useEffect, useState } from "react";
import ExamPastPaperPractice from "./ExamPastPaperPractice.jsx";

const API_BASE = "/api";

const EXAM_SUBJECTS = {
  data_structure: { key: "data_structure", label: "数据结构", shortLabel: "数据结构", courseId: "data_structure_11408" },
  computer_organization: { key: "computer_organization", label: "计算机组成原理", shortLabel: "计组", courseId: "computer_organization_11408" },
  operating_system: { key: "operating_system", label: "操作系统", shortLabel: "操作系统", courseId: "operating_system_11408" },
  computer_network: { key: "computer_network", label: "计算机网络", shortLabel: "计网", courseId: "computer_network_11408" },
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

function getKnowledgeNodeKey(node, fallback = "") {
  return String(node?.code || node?.id || node?.title || node?.name || fallback);
}

function getKnowledgeNodeTitle(node) {
  return node?.title || node?.name || node?.code || "未命名知识点";
}

function KnowledgePointSelector({ nodes = [], selectedPoint, onSelect, onClear }) {
  const [expanded, setExpanded] = useState(() => new Set(nodes.map((node, index) => getKnowledgeNodeKey(node, `root-${index}`))));

  useEffect(() => {
    setExpanded(new Set(nodes.map((node, index) => getKnowledgeNodeKey(node, `root-${index}`))));
  }, [nodes]);

  const selectedKey = selectedPoint ? getKnowledgeNodeKey(selectedPoint.node, selectedPoint.path) : "";

  const renderNode = (node, depth = 0, parentPath = []) => {
    const key = getKnowledgeNodeKey(node, `${parentPath.join("/")}-${depth}`);
    const title = getKnowledgeNodeTitle(node);
    const path = [...parentPath, title].filter(Boolean);
    const hasChildren = Boolean(node.children?.length);
    const isExpanded = expanded.has(key);
    const isSelected = selectedKey === key;

    return (
      <div key={key} className="ai-kp-tree-node">
        <div
          className={`ai-kp-tree-row${isSelected ? " ai-kp-tree-row--selected" : ""}`}
          style={{ paddingLeft: 10 + depth * 18 }}
        >
          {hasChildren ? (
            <button
              type="button"
              className="ai-kp-tree-toggle"
              onClick={() => {
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(key)) next.delete(key);
                  else next.add(key);
                  return next;
                });
              }}
              aria-label={isExpanded ? "收起知识点" : "展开知识点"}
            >
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : (
            <span className="ai-kp-tree-toggle-placeholder" />
          )}
          <button
            type="button"
            className="ai-kp-tree-select"
            onClick={() => onSelect({ key, node, path: path.join(" / ") })}
          >
            <span className="ai-kp-tree-code">{node.code || ""}</span>
            <span className="ai-kp-tree-title">{title}</span>
          </button>
        </div>
        {hasChildren && isExpanded && (
          <div className="ai-kp-tree-children">
            {node.children.map((child) => renderNode(child, depth + 1, path))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="ai-kp-selector">
      <div className="ai-kp-selected-summary">
        {selectedPoint ? (
          <>
            <span>已选范围</span>
            <strong>{selectedPoint.path}</strong>
            <button type="button" onClick={onClear}>清除</button>
          </>
        ) : (
          <span>可不选，按当前科目综合出题；也可选择任意父级或子级知识点范围。</span>
        )}
      </div>
      <div className="ai-kp-tree-panel">
        {nodes.length === 0 ? (
          <div className="ai-kp-tree-empty">知识点加载中...</div>
        ) : (
          nodes.map((node, index) => renderNode(node, 0, []))
        )}
      </div>
    </div>
  );
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

function formatPracticeDuration(minutes = 0) {
  const safeMinutes = Number.isFinite(Number(minutes)) ? Math.max(0, Number(minutes)) : 0;
  if (safeMinutes < 60) return `${Math.round(safeMinutes)}m`;
  const hours = safeMinutes / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)}h`;
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
  const [selectedPoint, setSelectedPoint] = useState(null);
  const [questionType, setQuestionType] = useState("choice");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");
  const [requirement, setRequirement] = useState("");
  const [aiQuestions, setAiQuestions] = useState([]);
  const [aiLoading, setAiLoading] = useState(true);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [aiError, setAiError] = useState("");
  const [editingQuestionId, setEditingQuestionId] = useState(null);
  const [editDraft, setEditDraft] = useState({ stem: "", standard_answer: "", analysis: "" });

  useEffect(() => {
    const params = new URLSearchParams({ course_id: subjectInfo.courseId });
    if (user?.username) params.set("username", user.username);
    safeJsonFetch(`${API_BASE}/knowledge-map?${params.toString()}`)
      .then((payload) => setMapData(payload))
      .catch(() => setMapData({ chapters: [] }));
  }, [subjectInfo.courseId, user?.username]);

  const loadAiQuestions = () => {
    if (!user?.username) {
      setAiQuestions([]);
      setAiLoading(false);
      return;
    }
    setAiLoading(true);
    const params = new URLSearchParams({ username: user.username });
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions?${params.toString()}`)
      .then((payload) => {
        setAiQuestions(payload.items || []);
        setAiError("");
      })
      .catch((err) => setAiError(`加载 AI 题库失败：${err.message || "服务器错误"}`))
      .finally(() => setAiLoading(false));
  };

  useEffect(() => {
    loadAiQuestions();
  }, [subjectInfo.key, user?.username]);

  const parsedCount = Number(count);
  const countInvalid = !Number.isInteger(parsedCount) || parsedCount < 1 || parsedCount > 10;

  const handleGenerateAIQuestions = async () => {
    setAiError("");
    setAiMessage("");
    if (!user?.username) {
      setAiError("生成失败：请先登录。");
      return;
    }
    if (countInvalid) {
      setAiError("生成失败：题目数量必须是 1-10 的整数。");
      return;
    }
    setAiGenerating(true);
    try {
      const payload = {
        username: user.username,
        knowledge_point_id: selectedPoint?.node?.code || selectedPoint?.node?.id || "",
        knowledge_point_name: selectedPoint?.node?.title || selectedPoint?.node?.name || "",
        knowledge_point_path: selectedPoint?.path || "",
        question_type: questionType === "big" ? "大题" : "选择题",
        count: parsedCount,
        difficulty,
        requirement,
      };
      const result = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setAiQuestions((prev) => [...(result.items || []), ...prev]);
      setAiMessage(`已生成 ${result.items?.length || 0} 道 mock 题。`);
    } catch (err) {
      setAiError(`生成失败：${err.message || "服务器错误"}`);
    } finally {
      setAiGenerating(false);
    }
  };

  const startEditQuestion = (item) => {
    setEditingQuestionId(item.id);
    setEditDraft({
      stem: item.stem || "",
      standard_answer: item.standard_answer || "",
      analysis: item.analysis || "",
    });
  };

  const saveEditQuestion = async (item) => {
    if (!user?.username) {
      setAiError("保存失败：请先登录。");
      return;
    }
    try {
      const result = await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: user.username, ...editDraft }),
      });
      setAiQuestions((prev) => prev.map((q) => (q.id === item.id ? result.item : q)));
      setEditingQuestionId(null);
      setAiMessage("题目已保存。");
      setAiError("");
    } catch (err) {
      setAiError(`保存失败：${err.message || "服务器错误"}`);
    }
  };

  const deleteAiQuestion = async (item) => {
    if (!user?.username) {
      setAiError("删除失败：请先登录。");
      return;
    }
    try {
      await safeJsonFetch(`${API_BASE}/exam/11408/${subjectInfo.key || "data_structure"}/ai-questions/${item.id}?username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
      });
      setAiQuestions((prev) => prev.filter((q) => q.id !== item.id));
      setAiMessage("题目已删除。");
      setAiError("");
    } catch (err) {
      setAiError(`删除失败：${err.message || "服务器错误"}`);
    }
  };

  return (
    <div className="exam-practice-subpage">
      <PracticeSubPageHeader title="AI 出题" subtitle="根据当前科目知识点，生成贴合 11408 真题风格的练习题" subjectInfo={subjectInfo} onBack={onBack} />
      <div className="exam-practice-split exam-practice-split--ai">
        <section className="exam-practice-panel">
          <h3>出题表单</h3>
          <div className="form-field">
            <span>知识点范围</span>
            <KnowledgePointSelector
              nodes={mapData?.chapters || []}
              selectedPoint={selectedPoint}
              onSelect={setSelectedPoint}
              onClear={() => setSelectedPoint(null)}
            />
          </div>
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
          {countInvalid && <div className="km-inline-message km-inline-message--error">题目数量必须是 1-10 的整数。</div>}
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
            <textarea className="field" rows={4} placeholder="例如：贴近 11408 真题，考查核心概念，不要偏题" value={requirement} onChange={(event) => setRequirement(event.target.value)} />
          </label>
          {aiError && <div className="km-inline-message km-inline-message--error">{aiError}</div>}
          {aiMessage && <div className="km-inline-message">{aiMessage}</div>}
          <button type="button" className="ai-generate-submit-btn" disabled={aiGenerating || countInvalid} onClick={handleGenerateAIQuestions}>
            {aiGenerating ? "生成中..." : "生成题目"}
          </button>
        </section>
        <section className="exam-practice-panel">
          <div className="exam-practice-panel-title">
            <h3>AI 题库</h3>
          </div>
          {aiLoading ? (
            <div className="past-paper-loading">正在加载 AI 题库...</div>
          ) : aiQuestions.length === 0 ? (
            <div className="exam-practice-empty-state">
              <strong>暂无 AI 生成题目</strong>
              <p>点击左侧“生成题目”后，mock 题会保存到当前用户的私有列表。</p>
            </div>
          ) : (
            <div className="ai-question-bank-list">
              {aiQuestions.map((item) => {
                const editing = editingQuestionId === item.id;
                return (
                  <article key={item.id} className="ai-question-bank-item">
                    <div className="past-paper-question-meta">
                      <span className="past-paper-q-type">{item.question_type}</span>
                      <span className="past-paper-q-number">{item.difficulty || "中等"}</span>
                      {item.knowledge_point_path && <span className="past-paper-q-year">{item.knowledge_point_path}</span>}
                    </div>
                    {editing ? (
                      <div className="ai-question-edit-form">
                        <textarea className="field" rows={4} value={editDraft.stem} onChange={(event) => setEditDraft((prev) => ({ ...prev, stem: event.target.value }))} />
                        <input className="field" value={editDraft.standard_answer} onChange={(event) => setEditDraft((prev) => ({ ...prev, standard_answer: event.target.value }))} />
                        <textarea className="field" rows={3} value={editDraft.analysis} onChange={(event) => setEditDraft((prev) => ({ ...prev, analysis: event.target.value }))} />
                      </div>
                    ) : (
                      <>
                        <div className="past-paper-q-content">{item.stem}</div>
                        {item.options && Object.keys(item.options).length > 0 && (
                          <div className="ai-question-options">
                            {Object.entries(item.options).map(([key, value]) => (
                              <div key={key}><strong>{key}.</strong> {value}</div>
                            ))}
                          </div>
                        )}
                        <div className="past-paper-q-answer-row"><span className="past-paper-q-label">标准答案：</span><span>{item.standard_answer}</span></div>
                        {item.analysis && <div className="past-paper-q-feedback"><p>{item.analysis}</p></div>}
                      </>
                    )}
                    <div className="ai-question-bank-meta">创建时间：{item.created_at || "未知"}</div>
                    <div className="exam-practice-action-row">
                      {editing ? (
                        <>
                          <button type="button" className="primary-button compact" onClick={() => saveEditQuestion(item)}>保存</button>
                          <button type="button" className="ghost-button compact" onClick={() => setEditingQuestionId(null)}>取消</button>
                        </>
                      ) : (
                        <>
                          <button type="button" className="ghost-button compact" onClick={() => startEditQuestion(item)}>编辑</button>
                          <button type="button" className="ghost-button compact" onClick={() => deleteAiQuestion(item)}>删除</button>
                          <button type="button" className="ghost-button compact" disabled>开始练习</button>
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
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
  const [practiceStats, setPracticeStats] = useState({
    total_practices: 0,
    completed_practices: 0,
    accuracy: 0,
    total_duration_minutes: 0,
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/exam/11408/${subjectKey}/past-papers`)
      .then((r) => r.json())
      .then((data) => setPastPapers(data))
      .catch(() => setPastPapers({ available: false, resource_files: [] }));
  }, [subjectKey]);

  useEffect(() => {
    if (!user?.username) {
      setPracticeStats({ total_practices: 0, completed_practices: 0, accuracy: 0, total_duration_minutes: 0 });
      setStatsLoading(false);
      setStatsError("登录后显示个人练习数据。");
      return;
    }
    setStatsLoading(true);
    setStatsError("");
    const params = new URLSearchParams({ username: user.username });
    safeJsonFetch(`${API_BASE}/exam/11408/${subjectKey}/practice/stats?${params.toString()}`)
      .then((payload) => setPracticeStats(payload))
      .catch((err) => {
        setPracticeStats({ total_practices: 0, completed_practices: 0, accuracy: 0, total_duration_minutes: 0 });
        setStatsError(`练习数据加载失败：${err.message || "服务器错误"}`);
      })
      .finally(() => setStatsLoading(false));
  }, [subjectKey, user?.username]);

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
    { key: "ai", icon: "🤖", title: "AI 出题", desc: "按知识点生成 11408 风格练习题", count: "自定义生成", className: "practice-type-card--ai" },
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
        {statsError && <div className="practice-stats-note">{statsError}</div>}
        <div className="practice-stats-grid">
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--docs">📄</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : practiceStats.total_practices || 0}</div><div className="practice-stat-card-label">总练习数</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--done">✓</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : practiceStats.completed_practices || 0}</div><div className="practice-stat-card-label">已完成</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--accuracy">★</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : `${practiceStats.accuracy || 0}%`}</div><div className="practice-stat-card-label">正确率</div></div></div>
          <div className="practice-stat-card--dashboard"><div className="practice-stat-card-icon practice-stat-card-icon--time">⏱</div><div className="practice-stat-card-body"><div className="practice-stat-card-value">{statsLoading ? "..." : formatPracticeDuration(practiceStats.total_duration_minutes || 0)}</div><div className="practice-stat-card-label">累计练习时长</div></div></div>
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
