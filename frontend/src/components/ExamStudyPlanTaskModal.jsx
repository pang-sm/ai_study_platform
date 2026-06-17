import { useState, useMemo } from "react";
import { getExamSubjectConfig } from "./ExamSubjectDashboard.jsx";

export default function ExamStudyPlanTaskModal({ user, subjectKey, chapters, editTask, onSaved, onClose }) {
  const config = getExamSubjectConfig(subjectKey);
  const username = user?.username || "";
  const isEdit = !!editTask;

  const [title, setTitle] = useState(editTask?.title || "");
  const [primaryKp, setPrimaryKp] = useState(editTask?.primary_knowledge || "");
  const [secondaryKp, setSecondaryKp] = useState(editTask?.secondary_knowledge || "");
  const [taskType, setTaskType] = useState(editTask?.task_type || "knowledge");
  const [status, setStatus] = useState(editTask?.status || "not_started");
  const [dueDate, setDueDate] = useState(editTask?.due_date || "");
  const [note, setNote] = useState(editTask?.note || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Flatten knowledge points for dropdowns
  const allSections = useMemo(() => {
    const result = [];
    for (const ch of (chapters || [])) {
      const chName = ch.title || "";
      for (const sec of (ch.children || [])) {
        result.push({
          chapterName: chName,
          sectionName: sec.title || "",
          sectionCode: sec.code || "",
        });
        for (const sub of (sec.children || [])) {
          if (sub.children && sub.children.length > 0) {
            for (const leaf of sub.children) {
              if (!leaf.children || leaf.children.length === 0) {
                // This is a leaf — skip, we only want section level
              }
            }
          }
        }
      }
    }
    return result;
  }, [chapters]);

  const allChapterNames = useMemo(() => {
    return [...new Set((chapters || []).map((c) => c.title || "").filter(Boolean))];
  }, [chapters]);

  const handleSave = async () => {
    if (!title.trim()) {
      setError("请输入任务标题");
      return;
    }
    setSaving(true);
    setError("");

    const body = {
      username,
      subject_key: subjectKey,
      title: title.trim(),
      primary_knowledge: primaryKp,
      secondary_knowledge: secondaryKp,
      task_type: taskType,
      status,
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
              placeholder="例如：完成线性表顺序表与链表复习" />
          </div>

          <div className="esp-form-row">
            <div className="esp-form-group">
              <label>所属一级知识点</label>
              <select value={primaryKp} onChange={(e) => setPrimaryKp(e.target.value)}>
                <option value="">不指定</option>
                {allChapterNames.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div className="esp-form-group">
              <label>所属二级知识点</label>
              <select value={secondaryKp} onChange={(e) => setSecondaryKp(e.target.value)}>
                <option value="">不指定</option>
                {allSections.map((s) => (
                  <option key={s.sectionCode} value={s.sectionName}>{s.sectionName}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="esp-form-row">
            <div className="esp-form-group">
              <label>任务类型</label>
              <select value={taskType} onChange={(e) => setTaskType(e.target.value)}>
                {TASK_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="esp-form-group">
              <label>状态</label>
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="not_started">未开始</option>
                <option value="in_progress">进行中</option>
                <option value="completed">已完成</option>
              </select>
            </div>
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
