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
  courseId,
  courseName,
  source = "course_workspace",
  onUploadSuccess,
  compact = false,
  user,
  getSubjectLabel,
}) {
  const fileInputRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadError, setUploadError] = useState("");
  const [uploadSuccess, setUploadSuccess] = useState("");
  const [batchCount, setBatchCount] = useState(0);

  const effectiveSubject = courseId || "";
  const courseLabel = courseName || (effectiveSubject && getSubjectLabel ? getSubjectLabel(effectiveSubject) : effectiveSubject) || "当前课程";

  const openFileDialog = () => {
    setUploadError("");
    setUploadSuccess("");
    fileInputRef.current?.click();
  };

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    if (!user?.username) {
      setUploadError("请先登录后再上传资料。");
      return;
    }
    if (!effectiveSubject) {
      setUploadError("请先选择课程后再上传资料。");
      return;
    }

    const fileList = Array.from(files);
    // Validate
    for (const f of fileList) {
      if (f.size > MAX_FILE_SIZE_BYTES) {
        setUploadError(`文件 "${f.name}" 超过 ${MAX_FILE_SIZE}MB 限制，请压缩后重试。`);
        return;
      }
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        setUploadError(`不支持的文件格式：${f.name}。支持的格式：${SUPPORTED_FORMATS}`);
        return;
      }
    }

    setUploading(true);
    setUploadError("");
    setUploadSuccess("");
    setBatchCount(fileList.length);

    let successCount = 0;
    let failCount = 0;
    const progress = {};
    fileList.forEach((f, i) => { progress[i] = 0; });
    setUploadProgress({ ...progress });

    for (let i = 0; i < fileList.length; i++) {
      const file = fileList[i];
      try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("username", user.username);
        formData.append("subject", effectiveSubject);
        formData.append("save_to_materials", "true");

        progress[i] = 50;
        setUploadProgress({ ...progress });

        const res = await fetch(`${API_BASE}/materials/upload`, {
          method: "POST",
          body: formData,
        });

        progress[i] = 100;
        setUploadProgress({ ...progress });

        if (res.ok) {
          successCount++;
        } else {
          const data = await res.json().catch(() => ({}));
          if (data.detail && data.detail.includes("已存在")) {
            successCount++; // treat duplicate as success
          } else {
            failCount++;
          }
        }
      } catch (err) {
        failCount++;
        progress[i] = -1;
        setUploadProgress({ ...progress });
      }
    }

    setUploading(false);

    if (failCount === 0) {
      setUploadSuccess(`成功上传 ${successCount} 个文件到「${courseLabel}」`);
    } else if (successCount > 0) {
      setUploadSuccess(`成功上传 ${successCount} 个文件，${failCount} 个失败`);
      setUploadError(`${failCount} 个文件上传失败，请检查网络后重试。`);
    } else {
      setUploadError(`上传失败，请检查网络后重试。`);
    }

    // Clear progress after a bit
    setTimeout(() => setUploadProgress({}), 2000);

    if (onUploadSuccess && successCount > 0) {
      onUploadSuccess(successCount);
    }
  };

  const onFileInputChange = (e) => {
    handleFiles(e.target.files);
    e.target.value = "";
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  if (compact) {
    return (
      <div className={`cu-upload cu-upload--compact ${dragOver ? "cu-upload--drag" : ""}`}
        onDragOver={onDragOver} onDragLeave={onDragLeave} onDrop={onDrop}
      >
        <input
          ref={fileInputRef}
          type="file" multiple
          accept={ALLOWED_EXTENSIONS.join(",")}
          onChange={onFileInputChange}
          style={{ display: "none" }}
        />
        <div className="cu-upload-compact-body">
          <button className="cu-btn cu-btn--primary cu-btn--sm" type="button" onClick={openFileDialog} disabled={uploading}>
            {uploading ? "上传中..." : "上传资料"}
          </button>
          <span className="cu-upload-compact-hint">拖拽文件到此处或点击上传 · {SUPPORTED_FORMATS}</span>
        </div>
        {uploadError && <div className="cu-upload-error">{uploadError}</div>}
        {uploadSuccess && <div className="cu-upload-success">{uploadSuccess}</div>}
      </div>
    );
  }

  const hasProgress = Object.keys(uploadProgress).length > 0;

  return (
    <div className="cu-upload">
      <input
        ref={fileInputRef}
        type="file" multiple
        accept={ALLOWED_EXTENSIONS.join(",")}
        onChange={onFileInputChange}
        style={{ display: "none" }}
      />

      {/* Upload drop zone */}
      <div
        className={`cu-upload-zone ${dragOver ? "cu-upload-zone--drag" : ""}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={!uploading ? openFileDialog : undefined}
      >
        <div className="cu-upload-zone-icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#93c5fd" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <div className="cu-upload-zone-text">
          <span className="cu-upload-zone-title">拖拽文件到此处上传</span>
          <span className="cu-upload-zone-hint">或</span>
        </div>
        <div className="cu-upload-zone-buttons">
          <button className="cu-btn cu-btn--primary" type="button" disabled={uploading}
            onClick={(e) => { e.stopPropagation(); openFileDialog(); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            上传资料
          </button>
          <button className="cu-btn cu-btn--secondary" type="button" disabled={uploading}
            onClick={(e) => { e.stopPropagation(); openFileDialog(); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <line x1="3" y1="9" x2="21" y2="9" />
              <line x1="9" y1="21" x2="9" y2="9" />
            </svg>
            批量上传
          </button>
          <button className="cu-btn cu-btn--ghost" type="button" disabled={uploading}
            onClick={(e) => { e.stopPropagation(); openFileDialog(); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
            从电脑选择
          </button>
        </div>
        <div className="cu-upload-zone-formats">
          支持格式：{SUPPORTED_FORMATS} · 单文件最大 {MAX_FILE_SIZE}MB
        </div>
      </div>

      {/* Progress */}
      {hasProgress && uploading && (
        <div className="cu-upload-progress">
          <div className="cu-upload-progress-bar">
            <div className="cu-upload-progress-fill" style={{
              width: `${Math.round(Object.values(uploadProgress).reduce((a, b) => a + (b > 0 ? b : 0), 0) / Math.max(1, Object.keys(uploadProgress).length))}%`
            }} />
          </div>
          <span className="cu-upload-progress-text">
            正在上传 {Object.keys(uploadProgress).length} 个文件...
          </span>
        </div>
      )}

      {/* Error */}
      {uploadError && (
        <div className="cu-upload-error">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {uploadError}
        </div>
      )}

      {/* Success */}
      {uploadSuccess && (
        <div className="cu-upload-success">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          {uploadSuccess}
        </div>
      )}

      {/* Hint */}
      <div className="cu-upload-hint">
        上传即入库，自动解析，智能生成知识点。
      </div>
    </div>
  );
}
