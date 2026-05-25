import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

const API_BASE = "/api";

const STATUS_OPTIONS = [
  { value: "not_started", label: "未开始" },
  { value: "learning", label: "学习中" },
  { value: "mastered", label: "已掌握" },
  { value: "weak", label: "薄弱" },
  { value: "review", label: "待复习" },
];

export default function KnowledgeRoadmap({
  user,
  course,
  getSubjectLabel,
}) {
  const [points, setPoints] = useState([]);
  const [roots, setRoots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({});
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState(null);

  // AI generation flow
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [genMode, setGenMode] = useState("course_name");
  const [genImportMode, setGenImportMode] = useState("append");
  const [genPreview, setGenPreview] = useState(null);
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState("");
  const [genStep, setGenStep] = useState("settings"); // settings | preview
  const [importing, setImporting] = useState(false);

  // Create form
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createParentId, setCreateParentId] = useState("");
  const [createLevel, setCreateLevel] = useState("");

  // Edit form
  const [editId, setEditId] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editParentId, setEditParentId] = useState("");

  const loadPoints = async () => {
    if (!user?.username || !course) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/knowledge-points?username=${encodeURIComponent(user.username)}&course_id=${encodeURIComponent(course)}`
      );
      const data = await res.json();
      if (res.ok) {
        setPoints(data.knowledge_points || []);
        setRoots(data.roots || []);
        const newExpanded = {};
        (data.knowledge_points || []).forEach((p) => {
          if (p.children && p.children.length > 0) newExpanded[p.id] = true;
        });
        setExpanded(newExpanded);
      }
    } catch (e) {
      console.error("Failed to load knowledge points:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPoints();
  }, [user?.username, course]);

  const toggleExpand = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const pointMap = {};
  points.forEach((p) => { pointMap[p.id] = p; });

  const getParentLabel = (parentId) => {
    const p = pointMap[parentId];
    return p ? p.title : "无";
  };

  const flatOptions = (items, depth = 0) => {
    let result = [];
    items.forEach((p) => {
      result.push({ id: p.id, title: "  ".repeat(depth) + p.title });
      if (p.children && p.children.length > 0) {
        result = result.concat(flatOptions(p.children, depth + 1));
      }
    });
    return result;
  };

  const createPoint = async () => {
    if (!createTitle.trim()) return;
    setSaving(true);
    try {
      const body = {
        username: user.username,
        course_id: course,
        title: createTitle.trim(),
        description: createDescription.trim(),
        parent_id: createParentId ? parseInt(createParentId) : null,
        level: createLevel ? parseInt(createLevel) : null,
      };
      const res = await fetch(`${API_BASE}/knowledge-points`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowCreateModal(false);
        resetCreateForm();
        await loadPoints();
      } else {
        alert(data.detail || "创建失败");
      }
    } catch (e) {
      console.error("Failed to create knowledge point:", e);
    } finally {
      setSaving(false);
    }
  };

  const resetCreateForm = () => {
    setCreateTitle("");
    setCreateDescription("");
    setCreateParentId("");
    setCreateLevel("");
  };

  const openEditModal = (point) => {
    setEditId(point.id);
    setEditTitle(point.title);
    setEditDescription(point.description || "");
    setEditParentId(point.parent_id ? String(point.parent_id) : "");
    setShowEditModal(true);
  };

  const updatePoint = async () => {
    if (!editTitle.trim()) return;
    setSaving(true);
    try {
      const body = {
        username: user.username,
        title: editTitle.trim(),
        description: editDescription.trim(),
        parent_id: editParentId ? parseInt(editParentId) : null,
      };
      const res = await fetch(`${API_BASE}/knowledge-points/${editId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok) {
        setShowEditModal(false);
        await loadPoints();
      } else {
        alert(data.detail || "更新失败");
      }
    } catch (e) {
      console.error("Failed to update knowledge point:", e);
    } finally {
      setSaving(false);
    }
  };

  const deletePoint = async (point) => {
    if (!window.confirm(`确认删除知识点"${point.title}"吗？`)) return;
    setActionId(point.id);
    try {
      const res = await fetch(
        `${API_BASE}/knowledge-points/${point.id}?username=${encodeURIComponent(user.username)}`,
        { method: "DELETE" }
      );
      const data = await res.json();
      if (res.ok) {
        await loadPoints();
      } else {
        alert(data.detail || "删除失败");
      }
    } catch (e) {
      console.error("Failed to delete knowledge point:", e);
    } finally {
      setActionId(null);
    }
  };

  const updateProgress = async (point, newStatus, newScore) => {
    setActionId(point.id);
    try {
      const body = {
        username: user.username,
        status: newStatus !== undefined ? newStatus : point.status,
        mastery_score: newScore !== undefined ? newScore : point.mastery_score,
      };
      const res = await fetch(`${API_BASE}/knowledge-points/${point.id}/progress`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        await loadPoints();
      }
    } catch (e) {
      console.error("Failed to update progress:", e);
    } finally {
      setActionId(null);
    }
  };

  const openGenerateModal = () => {
    setGenMode("course_name");
    setGenImportMode("append");
    setGenPreview(null);
    setGenError("");
    setGenStep("settings");
    setShowGenerateModal(true);
  };

  const generatePreview = async () => {
    setGenLoading(true);
    setGenError("");
    try {
      const body = {
        username: user.username,
        course_id: course,
        course_name: getSubjectLabel(course),
        mode: genMode,
      };
      const res = await fetch(`${API_BASE}/knowledge-points/generate-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (res.ok && data.items && data.items.length > 0) {
        setGenPreview(data);
        setGenStep("preview");
      } else {
        setGenError(data.detail || "生成失败");
      }
    } catch (e) {
      setGenError("网络错误：" + (e.message || "请重试"));
    } finally {
      setGenLoading(false);
    }
  };

  const importGenerated = async () => {
    if (genImportMode === "replace") {
      if (!window.confirm("替换会删除当前课程已有知识点路线图，确定继续吗？")) return;
    }
    setImporting(true);
    setGenError("");
    try {
      const res = await fetch(`${API_BASE}/knowledge-points/import-generated`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: course,
          items: genPreview.items,
          import_mode: genImportMode,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setShowGenerateModal(false);
        await loadPoints();
        alert(data.message || "导入成功");
      } else {
        setGenError(data.detail || "导入失败");
      }
    } catch (e) {
      setGenError("网络错误：" + (e.message || "请重试"));
    } finally {
      setImporting(false);
    }
  };

  const countPreviewItems = (items) => {
    let count = 0;
    items.forEach((item) => {
      count += 1;
      if (item.children && item.children.length > 0) {
        count += item.children.length;
      }
    });
    return count;
  };

  const getMasteryColor = (score) => {
    if (score >= 80) return "#059669";
    if (score >= 60) return "#d97706";
    if (score > 0) return "#dc2626";
    return "#9ca3af";
  };

  const getStatusLabel = (status) => {
    const opt = STATUS_OPTIONS.find((o) => o.value === status);
    return opt ? opt.label : status || "未开始";
  };

  const getStatusClass = (status) => {
    if (status === "mastered") return "kp-status-mastered";
    if (status === "weak") return "kp-status-weak";
    if (status === "learning") return "kp-status-learning";
    if (status === "review") return "kp-status-review";
    return "kp-status-default";
  };

  const renderPointRow = (point, depth = 0) => {
    const isExpanded = expanded[point.id] !== false;
    const hasChildren = point.children && point.children.length > 0;

    return (
      <div key={point.id}>
        <div
          className="kp-row"
          style={{ paddingLeft: depth * 24 }}
        >
          <div className="kp-row-main">
            <div className="kp-row-header">
              {hasChildren ? (
                <button
                  className="kp-expand-btn"
                  onClick={() => toggleExpand(point.id)}
                >
                  {isExpanded ? "▼" : "▶"}
                </button>
              ) : (
                <span className="kp-expand-spacer" />
              )}
              <span className="kp-title">{point.title}</span>
              <span className={`kp-status-tag ${getStatusClass(point.status)}`}>
                {getStatusLabel(point.status)}
              </span>
              <span
                className="kp-mastery-tag"
                style={{ color: getMasteryColor(point.mastery_score || 0) }}
              >
                掌握度：{point.mastery_score || 0}%
              </span>
              {(point.question_count ?? 0) > 0 && (
                <span className="kp-mastery-tag" style={{ color: "#0f766e" }}>
                  题目：{point.question_count}
                </span>
              )}
            </div>
            {point.description && (
              <p className="kp-desc">{point.description}</p>
            )}
            <div className="kp-mastery-bar-wrap">
              <div className="kp-mastery-bar">
                <div
                  className="kp-mastery-fill"
                  style={{
                    width: `${point.mastery_score || 0}%`,
                    backgroundColor: getMasteryColor(point.mastery_score || 0),
                  }}
                />
              </div>
            </div>
          </div>
          <div className="kp-row-actions">
            <select
              className="field kp-status-select"
              value={point.status || "not_started"}
              onChange={(e) => updateProgress(point, e.target.value, undefined)}
              disabled={actionId === point.id}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              className="tiny-button"
              disabled={actionId === point.id}
              onClick={() => openEditModal(point)}
            >
              编辑
            </button>
            <button
              className="tiny-button"
              disabled={actionId === point.id}
              onClick={() => deletePoint(point)}
              style={{ color: "#dc2626" }}
            >
              删除
            </button>
          </div>
        </div>
        {hasChildren && isExpanded && (
          <div className="kp-children">
            {point.children.map((child) => renderPointRow(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <section className="dashboard-card dashboard-kp-card">
      <div className="panel-title-row">
        <h3>知识点路线图</h3>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            className="tiny-button"
            onClick={openGenerateModal}
            style={{ color: "#7c3aed" }}
          >
            AI 生成路线图
          </button>
          <button
            className="tiny-button"
            onClick={() => {
              resetCreateForm();
              setShowCreateModal(true);
            }}
          >
            新增知识点
          </button>
        </div>
      </div>

      {loading ? (
        <div className="empty-inline">加载中...</div>
      ) : points.length === 0 ? (
        <div className="empty-inline">
          <p>当前课程还没有知识点，点击右上角"新增知识点"开始构建。</p>
        </div>
      ) : (
        <div className="kp-tree">
          {roots.map((rootId) => {
            const root = pointMap[rootId];
            if (!root) return null;
            return renderPointRow(root);
          })}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal &&
        createPortal(
          <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>新增知识点</h3>
                <button className="modal-close" onClick={() => setShowCreateModal(false)}>
                  &times;
                </button>
              </div>
              <div className="task-modal-body">
                <label className="field-label">课程</label>
                <input className="field" value={getSubjectLabel(course)} disabled />
                <label className="field-label">知识点标题 *</label>
                <input
                  className="field"
                  placeholder="例如：数组与链表"
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                />
                <label className="field-label">描述</label>
                <textarea
                  className="field"
                  rows={2}
                  placeholder="知识点简要说明..."
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                />
                <label className="field-label">父知识点</label>
                <select
                  className="field"
                  value={createParentId}
                  onChange={(e) => setCreateParentId(e.target.value)}
                >
                  <option value="">无（作为根知识点）</option>
                  {flatOptions(roots.map((id) => pointMap[id]).filter(Boolean)).map(
                    (opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.title}
                      </option>
                    )
                  )}
                </select>
              </div>
              <div className="task-form-actions">
                <button
                  className="ghost-button compact"
                  onClick={() => setShowCreateModal(false)}
                >
                  取消
                </button>
                <button
                  className="primary-button compact"
                  disabled={saving || !createTitle.trim()}
                  onClick={createPoint}
                >
                  {saving ? "创建中..." : "创建"}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* Edit Modal */}
      {showEditModal &&
        createPortal(
          <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>编辑知识点</h3>
                <button className="modal-close" onClick={() => setShowEditModal(false)}>
                  &times;
                </button>
              </div>
              <div className="task-modal-body">
                <label className="field-label">知识点标题 *</label>
                <input
                  className="field"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                />
                <label className="field-label">描述</label>
                <textarea
                  className="field"
                  rows={2}
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                />
                <label className="field-label">父知识点</label>
                <select
                  className="field"
                  value={editParentId}
                  onChange={(e) => setEditParentId(e.target.value)}
                >
                  <option value="">无（作为根知识点）</option>
                  {flatOptions(roots.map((id) => pointMap[id]).filter(Boolean)).map(
                    (opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.title}
                      </option>
                    )
                  )}
                </select>
              </div>
              <div className="task-form-actions">
                <button
                  className="ghost-button compact"
                  onClick={() => setShowEditModal(false)}
                >
                  取消
                </button>
                <button
                  className="primary-button compact"
                  disabled={saving || !editTitle.trim()}
                  onClick={updatePoint}
                >
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* AI Generate Modal */}
      {showGenerateModal &&
        createPortal(
          <div className="modal-overlay" onClick={() => setShowGenerateModal(false)}>
            <div className="modal-card modal-card--wide" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3>AI 生成知识点路线图</h3>
                <button className="modal-close" onClick={() => setShowGenerateModal(false)}>
                  &times;
                </button>
              </div>
              <div className="task-modal-body">
                {genError && (
                  <div className="ai-feedback-box" style={{ marginBottom: 12, background: "#fef2f2", border: "1px solid #fecaca" }}>
                    <span style={{ color: "#dc2626" }}>{genError}</span>
                  </div>
                )}

                {genStep === "settings" && (
                  <>
                    <label className="field-label">课程</label>
                    <input className="field" value={getSubjectLabel(course)} disabled />

                    <label className="field-label">生成方式</label>
                    <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
                      <label className="question-option-label" style={{ flex: 1 }}>
                        <input
                          type="radio"
                          name="gen_mode"
                          value="course_name"
                          checked={genMode === "course_name"}
                          onChange={(e) => setGenMode(e.target.value)}
                        />
                        <span>根据课程名称生成</span>
                      </label>
                      <label className="question-option-label" style={{ flex: 1 }}>
                        <input
                          type="radio"
                          name="gen_mode"
                          value="materials"
                          checked={genMode === "materials"}
                          onChange={(e) => setGenMode(e.target.value)}
                        />
                        <span>根据课程资料生成</span>
                      </label>
                    </div>

                    <label className="field-label">导入方式</label>
                    <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
                      <label className="question-option-label" style={{ flex: 1 }}>
                        <input
                          type="radio"
                          name="gen_import_mode"
                          value="append"
                          checked={genImportMode === "append"}
                          onChange={(e) => setGenImportMode(e.target.value)}
                        />
                        <span>追加到现有路线图</span>
                      </label>
                      <label className="question-option-label" style={{ flex: 1 }}>
                        <input
                          type="radio"
                          name="gen_import_mode"
                          value="replace"
                          checked={genImportMode === "replace"}
                          onChange={(e) => setGenImportMode(e.target.value)}
                        />
                        <span>替换现有路线图</span>
                      </label>
                    </div>

                    {genImportMode === "replace" && (
                      <p style={{ color: "#dc2626", fontSize: 13, marginBottom: 12 }}>
                        警告：替换将删除当前课程所有已有知识点，不可恢复。
                      </p>
                    )}
                  </>
                )}

                {genStep === "preview" && genPreview && (
                  <>
                    <div className="kp-preview-info">
                      <span>生成方式：{genPreview.source === "materials" ? "根据课程资料" : "根据课程名称"}</span>
                      <span>共 {countPreviewItems(genPreview.items)} 个知识点</span>
                    </div>
                    <div className="kp-preview-tree">
                      {genPreview.items.map((item, idx) => (
                        <div key={idx} className="kp-preview-parent">
                          <div className="kp-preview-parent-title">
                            <span className="kp-preview-dot" />
                            {item.title}
                          </div>
                          {item.description && (
                            <div className="kp-preview-desc">{item.description}</div>
                          )}
                          {item.children && item.children.length > 0 && (
                            <div className="kp-preview-children">
                              {item.children.map((child, cIdx) => (
                                <div key={cIdx} className="kp-preview-child">
                                  <span className="kp-preview-dot kp-preview-dot--child" />
                                  <div>
                                    <div className="kp-preview-child-title">{child.title}</div>
                                    {child.description && (
                                      <div className="kp-preview-desc">{child.description}</div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
              <div className="task-form-actions">
                <button
                  className="ghost-button compact"
                  onClick={() => setShowGenerateModal(false)}
                >
                  取消
                </button>
                {genStep === "settings" && (
                  <button
                    className="primary-button compact"
                    disabled={genLoading}
                    onClick={generatePreview}
                  >
                    {genLoading ? "生成中..." : "生成预览"}
                  </button>
                )}
                {genStep === "preview" && (
                  <>
                    <button
                      className="ghost-button compact"
                      onClick={() => { setGenStep("settings"); setGenError(""); }}
                      disabled={importing}
                    >
                      重新生成
                    </button>
                    <button
                      className="primary-button compact"
                      disabled={importing}
                      onClick={importGenerated}
                    >
                      {importing ? "导入中..." : "确认导入"}
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>,
          document.body
        )}
    </section>
  );
}
