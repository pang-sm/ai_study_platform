import { useState, useMemo } from "react";
import { getExamSubjectConfig } from "./ExamSubjectDashboard.jsx";

export default function ExamStudyPlanTaskModal({ user, subjectKey, chapters, editTask, onSaved, onClose }) {
  const config = getExamSubjectConfig(subjectKey);
  const username = user?.username || "";
  const isEdit = !!editTask;

  const [title, setTitle] = useState(editTask?.title || "");
  const [kpName, setKpName] = useState(
    editTask?.knowledge_point_name || editTask?.secondary_knowledge || ""
  );
  const [scopeType, setScopeType] = useState(editTask?.scope_type || "single");
  const [taskType, setTaskType] = useState(editTask?.task_type || "knowledge");
  const [dueDate, setDueDate] = useState(editTask?.due_date || "");
  const [note, setNote] = useState(editTask?.note || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Gather all section (二级知识点) names for dropdown
  const allSections = useMemo(() => {
    const result = [];
    for (const ch of (chapters || [])) {
      for (const sec of (ch.children || [])) {
        const name = sec.title || "";
        if (name && !result.find((r) => r.name === name)) {
          result.push({ name, code: sec.code || "" });
        }
      }
    }
    return result;
  }, [chapters]);

  const handleSave = async () => {
    if (!title.trim()) {
      setError("请输入任务标题");
      return;
    }
    if (scopeType !== "all" && !kpName.trim()) {
      setError("请选择知识点");
      return;
    }
    setSaving(true);
    setError("");

    const body = {
      username,
      subject_key: subjectKey,
      title: title.trim(),
      knowledge_point_name: scopeType === "all" ? "全部范围" : kpName,
      scope_type: scopeType,
      task_type: taskType,
      due_date: dueDate,
      note: note.trim(),
    };

    try {
      const url = isEdit
        ? `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/tasks/${editTask.id}`
        : `/api/exam/11408/subjects/${encodeURIComponent(subjectKey)}/study-plan/tasks`;
      const method = isEdit ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.success) onSaved?.();
    } catch (e) {
      setError(e.message || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const TASK_TYPES = [
    { value: "knowledge", label: "知识点学习" },
    { value: "chapter_practice", label: "章节练习" },
    { value: "review", label: "阶段复习" },
  ];

  return (
    <div className="esp-modal-overlay" onClick={onClose}>
      <div className="esp-modal" onClick={(e) => e.stopPropagation()}>
        <div className="esp-modal-header">
          <h2>{isEdit ? "✏️ 编辑任务" : "➕ 新建阶段任务"} — {config.title}</h2>
          <button type="button" className="esp-modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="esp-modal-body">
          {error && <div className="esp-modal-error">{error}</div>}

          <div className="esp-form-group">
            <label>任务标题 *</label>
            <input type="text" value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="例如：完成线性表知识点学习" />
          </div>

          <div className="esp-form-group">
            <label>知识点 *</label>
            <select value={scopeType === "all" ? "__all__" : kpName}
              onChange={(e) => {
                const val = e.target.value;
                if (val === "__all__") {
                  setScopeType("all");
                  setKpName("全部范围");
                } else {
                  setScopeType("single");
                  setKpName(val);
                }
              }}
              required>
              <option value="__all__">📚 全部范围</option>
              <option value="" disabled>—— 选择具体知识点 ——</option>
              {allSections.map((s) => (
                <option key={s.code || s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="esp-form-group">
            <label>任务类型</label>
            <select value={taskType} onChange={(e) => setTaskType(e.target.value)}>
              {TASK_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div className="esp-form-group">
            <label>计划完成日期</label>
            <input type="date" value={dueDate}
              onChange={(e) => setDueDate(e.target.value)} />
          </div>

          <div className="esp-form-group">
            <label>备注（可选）</label>
            <textarea value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="补充说明..."
              rows={3}
              style={{ resize: "vertical", padding: "10px 14px", borderRadius: "10px", border: "1px solid #d1d5db", fontSize: "14px", outline: "none", fontFamily: "inherit" }} />
          </div>

          <p style={{ fontSize: "12px", color: "#6b7280", margin: 0 }}>
            💡 任务完成状态由系统自动计算，无需手动设置。
          </p>
        </div>
        <div className="esp-modal-footer">
          <button type="button" className="esp-modal-cancel" onClick={onClose} disabled={saving}>取消</button>
          <button type="button" className="esp-modal-save" onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : isEdit ? "保存修改" : "创建任务"}
          </button>
        </div>
      </div>
    </div>
  );
}
