import { useCallback, useEffect, useRef, useState } from "react";
import { resolveProgrammingCourse, PROGRAMMING_LANGUAGES } from "../programmingCourses.js";

function formatFileSize(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function getFileTypeLabel(type) {
  const t = String(type || "").toLowerCase();
  if (!t) return "未知";
  if (t.includes("pdf")) return "PDF";
  if (t.includes("doc")) return "Word";
  if (t.includes("ppt")) return "PPT";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(t)) return "图片";
  if (["txt", "md", "markdown"].includes(t)) return "文本";
  if (["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql", "sh", "bash", "html", "css", "json", "xml", "yaml", "yml"].includes(t)) return "代码";
  return t.toUpperCase();
}

function getParseStatusLabel(status) {
  const s = String(status || "").toLowerCase();
  if (s === "success") return { label: "已解析", cls: "ok" };
  if (s === "partial") return { label: "部分解析", cls: "ok" };
  if (s === "parsing") return { label: "解析中", cls: "pending" };
  if (s === "pending") return { label: "等待解析", cls: "pending" };
  if (s === "failed") return { label: "解析失败", cls: "err" };
  return { label: "未解析", cls: "pending" };
}

export default function ProgrammingMaterialsPage({ user, apiBase = "/api", language, onLanguageChange }) {
  const course = (() => {
    try {
      return resolveProgrammingCourse(language);
    } catch {
      return null;
    }
  })();
  const [materials, setMaterials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const fileInputRef = useRef(null);

  const loadMaterials = useCallback(async () => {
    if (!user?.username || !course?.courseId) return;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({
        username: user.username,
        course_id: course.courseId,
        track: "programming",
      });
      const res = await fetch(`${apiBase}/materials?${query.toString()}`, { credentials: "include" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "资料加载失败");
      setMaterials(Array.isArray(data.materials) ? data.materials : []);
    } catch (err) {
      setError(err.message || "资料加载失败");
    } finally {
      setLoading(false);
    }
  }, [apiBase, user?.username, course?.courseId]);

  useEffect(() => {
    loadMaterials();
  }, [loadMaterials]);

  // Poll while any material is still being parsed.
  useEffect(() => {
    const busy = materials.some((m) => {
      const s = String(m.parse_status || "").toLowerCase();
      return s === "parsing" || s === "pending";
    });
    if (!busy) return undefined;
    const timer = setTimeout(loadMaterials, 3000);
    return () => clearTimeout(timer);
  }, [materials, loadMaterials]);

  const handleUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (!files.length || !user?.username || !course?.courseId) return;
    setUploading(true);
    setError("");
    setNotice("");
    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("username", user.username);
        formData.append("course_id", course.courseId);
        formData.append("subject_key", "programming");
        formData.append("subject", "programming");
        formData.append("track", "programming");
        formData.append("save_to_materials", "true");
        const res = await fetch(`${apiBase}/materials/upload`, {
          method: "POST",
          credentials: "include",
          body: formData,
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.detail?.message || data.detail || `上传失败：${file.name}`);
      }
      setNotice("上传成功，正在解析…");
      await loadMaterials();
    } catch (err) {
      setError(err.message || "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (material) => {
    if (!user?.username) return;
    if (!window.confirm(`确认删除「${material.original_filename}」吗？`)) return;
    setError("");
    try {
      const res = await fetch(`${apiBase}/materials/${material.id}?username=${encodeURIComponent(user.username)}`, {
        method: "DELETE",
        credentials: "include",
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "删除失败");
      setMaterials((prev) => prev.filter((m) => m.id !== material.id));
      setNotice("已删除");
    } catch (err) {
      setError(err.message || "删除失败");
    }
  };

  if (!course) {
    return (
      <section className="pm-page">
        <div className="ph-error">未知编程课程，无法加载资料库。</div>
      </section>
    );
  }

  return (
    <section className="pm-page">
      <div className="pm-head">
        <div className="pm-language-tabs" aria-label="编程资料库语言">
          {PROGRAMMING_LANGUAGES.map((item) => (
            <button
              key={item}
              type="button"
              className={language === item ? "is-active" : ""}
              onClick={() => onLanguageChange?.(item)}
            >
              {item}
            </button>
          ))}
        </div>
        <div className="pm-head-actions">
          <button type="button" className="pm-refresh-btn" onClick={loadMaterials} disabled={loading || uploading}>刷新</button>
          <button type="button" className="pm-upload-btn" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
            {uploading ? "上传中…" : "上传资料"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
            onChange={handleUpload}
            style={{ display: "none" }}
          />
        </div>
      </div>

      {error && <div className="ph-error">{error}</div>}
      {notice && <div className="pm-notice">{notice}</div>}

      {loading ? (
        <div className="pm-empty">资料加载中…</div>
      ) : materials.length === 0 ? (
        <div className="pm-empty">
          <p>当前还没有资料</p>
          <p className="pm-empty-sub">上传后即可在 {language} 资料库与 AI 问答中引用。</p>
        </div>
      ) : (
        <div className="pm-list">
          {materials.map((material) => {
            const status = getParseStatusLabel(material.parse_status);
            return (
              <article key={material.id} className="pm-item">
                <div className="pm-item-icon" aria-hidden="true">📄</div>
                <div className="pm-item-body">
                  <strong className="pm-item-name" title={material.original_filename}>{material.original_filename}</strong>
                  <span className="pm-item-meta">
                    {getFileTypeLabel(material.file_type)} · {formatFileSize(material.file_size)}
                    {material.chunk_count > 0 ? ` · ${material.chunk_count} 片段` : ""}
                  </span>
                </div>
                <span className={`pm-status pm-status--${status.cls}`}>{status.label}</span>
                <button type="button" className="pm-delete-btn" onClick={() => handleDelete(material)} title="删除资料">删除</button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
