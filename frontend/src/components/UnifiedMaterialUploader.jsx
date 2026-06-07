import { useRef, useState } from "react";

const API_BASE = "/api";

const ALLOWED_EXTENSIONS = [
  ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".docx", ".pptx",
  ".txt", ".md", ".markdown",
  ".py", ".java", ".c", ".cpp", ".h", ".hpp", ".js", ".jsx", ".ts", ".tsx",
  ".html", ".htm", ".css", ".json", ".xml", ".yaml", ".yml",
  ".sql", ".sh", ".bash", ".go", ".rs", ".php", ".rb",
];

const SUPPORTED_FORMATS = "PDF / DOCX / PPT / 图片 / TXT / MD / 代码文件等";
const MAX_FILE_SIZE = 20;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE * 1024 * 1024;

export default function UnifiedMaterialUploader({
  courseId, courseName, source = "course_workspace",
  onUploadSuccess, compact = false, user, getSubjectLabel,
}) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");

  const effectiveSubject = courseId || "";
  const courseLabel = courseName || (effectiveSubject && getSubjectLabel ? getSubjectLabel(effectiveSubject) : effectiveSubject) || "当前课程";

  const openFileDialog = () => {
    setUploadError(""); setUploadSuccess(""); fileInputRef.current?.click();
  };

  const handleFiles = async (files) => {
    if (!files?.length) return;
    if (!user?.username) { setUploadError("请先登录后再上传资料。"); return; }
    if (!effectiveSubject) { setUploadError("请先选择课程后再上传资料。"); return; }
    const fileList = Array.from(files);
    for (const f of fileList) {
      if (f.size > MAX_FILE_SIZE_BYTES) { setUploadError(`"${f.name}" 超过 ${MAX_FILE_SIZE}MB 限制。`); return; }
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) { setUploadError(`不支持的文件格式：${f.name}`); return; }
    }
    setUploading(true); setUploadError(""); setUploadSuccess("");
    const progress = {};
    fileList.forEach((_, i) => { progress[i] = 0; });
    setUploadProgress({ ...progress });

    let successCount = 0, failCount = 0;
    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("username", user.username);
        formData.append("subject", effectiveSubject);
        formData.append("save_to_materials", "true");
        progress[i] = 50; setUploadProgress({ ...progress });
        const res = await fetch(`${API_BASE}/materials/upload`, { method: "POST", body: formData });
        progress[i] = 100; setUploadProgress({ ...progress });
        if (res.ok) { successCount++; }
        else {
          const data = await res.json().catch(() => ({}));
          if (data.detail && data.detail.includes("已存在")) successCount++;
          else failCount++;
        }
      } catch { failCount++; progress[i] = -1; setUploadProgress({ ...progress }); }
    }
    setUploading(false);
    if (failCount === 0) setUploadSuccess(`成功上传 ${successCount} 个文件到「${courseLabel}」`);
    else if (successCount > 0) {
      setUploadSuccess(`成功上传 ${successCount} 个文件，${failCount} 个失败`);
      setUploadError(`${failCount} 个文件上传失败，请检查网络后重试。`);
    } else setUploadError("上传失败，请检查网络后重试。");
    setTimeout(() => setUploadProgress({}), 2000);
    if (onUploadSuccess && successCount > 0) onUploadSuccess(successCount);
  };

  const onDragOver = (e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); };
  const onDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); };
  const onDrop = (e) => { e.preventDefault(); e.stopPropagation(); setDragOver(false); handleFiles(e.dataTransfer.files); };

  if (compact) {
    return (
      <div onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
        style={{ border: `2px dashed ${dragOver ? "#2563eb" : "#dce2ec"}`, borderRadius: 12, padding: "14px 18px", background: dragOver ? "#eff6ff" : "#fafbfd" }}>
        <input ref={fileInputRef} type="file" multiple accept={ALLOWED_EXTENSIONS.join(",")} onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} style={{ display: "none" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="cd-btn cd-btn--primary cd-btn--sm" type="button" onClick={openFileDialog} disabled={uploading}>{uploading ? "上传中..." : "上传资料"}</button>
          <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>拖拽文件或点击上传 · {SUPPORTED_FORMATS}</span>
        </div>
        {uploadError && <div className="cd-upload-msg cd-upload-msg--error">{uploadError}</div>}
        {uploadSuccess && <div className="cd-upload-msg cd-upload-msg--success">{uploadSuccess}</div>}
      </div>
    );
  }

  const hasProgress = Object.keys(uploadProgress).length > 0;
  return (
    <div>
      <input ref={fileInputRef} type="file" multiple accept={ALLOWED_EXTENSIONS.join(",")}
        onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} style={{ display: "none" }} />

      <div className={`cd-upload-zone ${dragOver ? "cd-upload-zone--drag" : ""}`}
        onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
        onClick={!uploading ? openFileDialog : undefined}>

        <div className="cd-upload-icon">
          <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <p className="cd-upload-title">拖拽文件到此处上传</p>
        <p className="cd-upload-sub">或选择上传方式</p>

        <div className="cd-upload-actions">
          <button className="cd-btn cd-btn--primary" type="button" disabled={uploading}
            onClick={(e) => { e.stopPropagation(); openFileDialog(); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
            上传资料
          </button>
          <button className="cd-btn cd-btn--secondary" type="button" disabled={uploading}
            onClick={(e) => { e.stopPropagation(); openFileDialog(); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" /></svg>
            批量上传
          </button>
          <button className="cd-btn cd-btn--ghost" type="button" disabled={uploading}
            onClick={(e) => { e.stopPropagation(); openFileDialog(); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>
            从电脑选择
          </button>
        </div>
        <div className="cd-upload-formats">
          支持格式：{SUPPORTED_FORMATS} · 单文件最大 {MAX_FILE_SIZE}MB
        </div>
      </div>

      {hasProgress && uploading && (
        <div className="cd-upload-progress">
          <div className="cd-upload-progress-bar">
            <div className="cd-upload-progress-fill" style={{
              width: `${Math.round(Object.values(uploadProgress).reduce((a, b) => a + (b > 0 ? b : 0), 0) / Math.max(1, Object.keys(uploadProgress).length))}%`
            }} />
          </div>
          <span className="cd-upload-progress-text">正在上传 {Object.keys(uploadProgress).length} 个文件...</span>
        </div>
      )}

      {uploadError && <div className="cd-upload-msg cd-upload-msg--error">{uploadError}</div>}
      {uploadSuccess && <div className="cd-upload-msg cd-upload-msg--success">{uploadSuccess}</div>}

      <div className="cd-upload-hint">上传即入库，自动解析，智能生成知识点。</div>
    </div>
  );
}
