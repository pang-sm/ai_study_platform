import { useState } from "react";
import { createPortal } from "react-dom";
import "./CourseMaterialsPage.css";

const API_BASE = "/api";

const PAGE_SIZE = 5;

const FILE_TYPES = [
  { value: "all", label: "全部" },
  { value: "pdf", label: "PDF" },
  { value: "image", label: "图片" },
  { value: "word", label: "Word" },
  { value: "ppt", label: "PPT" },
  { value: "txt", label: "TXT" },
  { value: "code", label: "代码" },
];

const INDEX_STATUSES = [
  { value: "all", label: "全部" },
  { value: "indexed", label: "已索引" },
  { value: "parsing", label: "解析中" },
  { value: "failed", label: "解析失败" },
  { value: "unindexed", label: "未索引" },
];

const SORT_OPTIONS = [
  { value: "newest", label: "最新上传" },
  { value: "oldest", label: "最早上传" },
  { value: "nameAsc", label: "文件名↑" },
  { value: "nameDesc", label: "文件名↓" },
  { value: "sizeDesc", label: "大小↓" },
  { value: "sizeAsc", label: "大小↑" },
  { value: "chunksDesc", label: "片段↓" },
  { value: "chunksAsc", label: "片段↑" },
];

function formatDate(value) {
  if (!value) return "";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatFileSize(value) {
  const n = Number(value);
  if (!n || n < 0) return "0 B";
  if (n >= 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
  if (n >= 1024) return (n / 1024).toFixed(1) + " KB";
  return n + " B";
}

function getMaterialFileSize(material) {
  return Number(material?.file_size ?? material?.size ?? material?.fileSize ?? 0) || 0;
}

function getMaterialChunkCount(material) {
  return Number(material?.chunk_count ?? material?.chunks ?? material?.chunkCount ?? 0) || 0;
}

function getMaterialCreatedTime(material) {
  const value = material?.created_at || material?.uploaded_at || material?.upload_time || material?.updated_at || 0;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function getMaterialFilename(material) {
  return String(material?.original_filename || material?.filename || material?.name || "").trim();
}

function sortMaterials(items, sortMode) {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (sortMode === "oldest") return getMaterialCreatedTime(a) - getMaterialCreatedTime(b);
    if (sortMode === "nameAsc") return getMaterialFilename(a).localeCompare(getMaterialFilename(b), "zh-CN");
    if (sortMode === "nameDesc") return getMaterialFilename(b).localeCompare(getMaterialFilename(a), "zh-CN");
    if (sortMode === "sizeDesc") return getMaterialFileSize(b) - getMaterialFileSize(a);
    if (sortMode === "sizeAsc") return getMaterialFileSize(a) - getMaterialFileSize(b);
    if (sortMode === "chunksDesc") return getMaterialChunkCount(b) - getMaterialChunkCount(a);
    if (sortMode === "chunksAsc") return getMaterialChunkCount(a) - getMaterialChunkCount(b);
    return getMaterialCreatedTime(b) - getMaterialCreatedTime(a);
  });
  return sorted;
}

function getMaterialHitSnippet(material) {
  const value =
    material?.matched_snippet ??
    material?.snippet ??
    material?.match_snippet ??
    material?.highlight ??
    material?.content_preview ??
    material?.chunk_text ??
    "";
  if (Array.isArray(value)) return "";
  return typeof value === "string" ? value.trim() : "";
}

function getParseStatusLabel(status) {
  const map = {
    success: "已索引",
    partial: "部分索引",
    parsing: "解析中",
    pending: "等待解析",
    failed: "解析失败",
  };
  return map[status] || "未索引";
}

function getParseStatusHint(material) {
  const s = (material && material.parse_status) || "";
  if (s === "parsing") return "系统正在解析文件内容，解析完成后将生成 AI 知识索引。";
  if (s === "pending") return "文件已上传，等待系统解析。";
  if (s === "failed") return "解析失败，可尝试重新上传或重建索引。";
  if (s === "success") return "解析完成，已生成 AI 知识索引。";
  if (s === "partial") return "部分内容已解析，部分内容未能解析。";
  return "文件尚未开始解析。";
}

function getFileTypeLabel(type) {
  const t = (type || "").toLowerCase();
  const map = {
    pdf: "PDF",
    png: "PNG 图片",
    jpg: "JPG 图片",
    jpeg: "JPEG 图片",
    webp: "WEBP 图片",
    docx: "Word 文档",
    pptx: "PPT 课件",
    txt: "纯文本",
    md: "Markdown",
    markdown: "Markdown",
    py: "Python 代码",
    java: "Java 代码",
    c: "C 代码",
    cpp: "C++ 代码",
    h: "C 头文件",
    hpp: "C++ 头文件",
    js: "JavaScript",
    jsx: "React JSX",
    ts: "TypeScript",
    tsx: "React TSX",
    html: "HTML",
    htm: "HTML",
    css: "CSS",
    json: "JSON",
    xml: "XML",
    yaml: "YAML",
    yml: "YAML",
    sql: "SQL",
    sh: "Shell 脚本",
    bash: "Bash 脚本",
    go: "Go 代码",
    rs: "Rust 代码",
    php: "PHP 代码",
    rb: "Ruby 代码",
  };
  if (map[t]) return map[t];
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(t)) return "图片";
  if (["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql"].includes(t)) return "代码";
  return t.toUpperCase() || "未知";
}

function getFileIconClass(fileType) {
  const t = (fileType || "").toLowerCase();
  if (t === "pdf") return "cmp-file-icon--pdf";
  if (t === "docx") return "cmp-file-icon--word";
  if (t === "pptx") return "cmp-file-icon--ppt";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(t)) return "cmp-file-icon--image";
  if (["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql", "sh", "bash"].includes(t)) return "cmp-file-icon--code";
  return "cmp-file-icon--txt";
}

function getFileIconEmoji(fileType) {
  const t = (fileType || "").toLowerCase();
  if (t === "pdf") return "📄";
  if (t === "docx") return "📝";
  if (t === "pptx") return "📊";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(t)) return "🖼️";
  if (["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql", "sh", "bash"].includes(t)) return "💻";
  return "📃";
}

function getReferenceSnippet(reference) {
  if (!reference) return "";
  const text = reference.text || reference.content || reference.chunk_text || "";
  if (text) return text.slice(0, 80) + (text.length > 80 ? "..." : "");
  if (reference.page) return `第 ${reference.page} 页`;
  return "";
}

function StatCard({ icon, value, label }) {
  return (
    <div className="cmp-stat-card">
      <span className="cmp-stat-icon">{icon}</span>
      <div className="cmp-stat-body">
        <span className="cmp-stat-value">{value}</span>
        <span className="cmp-stat-label">{label}</span>
      </div>
    </div>
  );
}

function MaterialCard({
  material,
  getSubjectLabel,
  onPreview,
  onDownload,
  onDetail,
  onDelete,
  onReparse,
}) {
  const parseStatus = material.parse_status || "unknown";
  const isFailed = parseStatus === "failed";
  const isParsing = parseStatus === "parsing" || parseStatus === "pending";
  const parseError = material.parse_error || "";

  return (
    <div className={`cmp-material-card${isFailed ? " cmp-material-card--failed" : ""}`}>
      <div className="cmp-material-card-top">
        <span className={`cmp-file-icon ${getFileIconClass(material.file_type)}`}>
          {getFileIconEmoji(material.file_type)}
        </span>
        <div className="cmp-material-card-info">
          <span className="cmp-material-card-name" title={material.original_filename}>
            {material.original_filename}
          </span>
          <span className="cmp-material-card-meta">
            {getFileTypeLabel(material.file_type)} · {formatFileSize(material.file_size)}
            {" · "}{getSubjectLabel(material.subject)}
          </span>
          <span className="cmp-material-card-date">{formatDate(material.created_at)}</span>
        </div>
      </div>
      <div className="cmp-material-card-index">
        <span className={`cmp-index-badge cmp-index-badge--${parseStatus}`}>
          {isParsing ? "解析中..." : getParseStatusLabel(parseStatus)}
        </span>
        <span className="cmp-index-chunks">{Number(material.chunk_count || 0)} 个知识片段</span>
        {isParsing && (
          <span className="cmp-index-progress">
            {Number(material.parse_progress || 0)}%
          </span>
        )}
      </div>
      {isFailed && parseError && (
        <div className="cmp-parse-error" title={parseError}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {parseError.length > 80 ? parseError.slice(0, 80) + "..." : parseError}
        </div>
      )}
      <div className="cmp-material-card-actions">
        <button className="cmp-action-btn" title="查看原文件" onClick={() => onPreview(material)} disabled={!material.can_preview}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          查看原文
        </button>
        <button className="cmp-action-btn" title="查看 AI 索引" onClick={() => onDetail(material.id)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          AI 索引
        </button>
        <button className="cmp-action-btn" title="下载" onClick={() => onDownload(material)} disabled={!material.can_download}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          下载
        </button>
        {isFailed && (
          <button className="cmp-action-btn cmp-action-btn--reparse" title="重新解析" onClick={() => onReparse(material.id)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            重新解析
          </button>
        )}
        <button className="cmp-action-btn cmp-action-btn--danger" title="删除" onClick={() => onDelete(material.id)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          删除
        </button>
      </div>
    </div>
  );
}

export default function CourseMaterialsPage({
  user,
  subject,
  courseOptions,
  getSubjectLabel,
  materials = [],
  materialsLoading,
  reindexLoading,
  currentFilterItems = [],
  paginatedFilterItems = [],
  currentFilterTotalPages,
  safeCurrentPage,
  materialSearchQuery,
  handleMaterialSearchChange,
  trimmedMaterialSearchQuery,
  materialSearchTriggered,
  materialSearchLoading,
  materialSearchResults = [],
  paginatedSearchResults = [],
  materialSortMode = "newest",
  setMaterialSortMode,
  safeSearchPage,
  searchTotalPages,
  materialCurrentPage,
  setMaterialCurrentPage,
  selectedMaterialDetail,
  materialsFileInputRef,
  handleFileChange,
  loadMaterials,
  searchMaterials,
  reindexLibrary,
  openMaterialDetail,
  previewMaterial,
  downloadMaterial,
  deleteMaterial,
  reparseMaterial,
  setPage,
}) {
  const [filterType, setFilterType] = useState("all");
  const [filterIndex, setFilterIndex] = useState("all");
  const [searchInput, setSearchInput] = useState("");

  // Knowledge analysis modal
  const [showKnowledgeModal, setShowKnowledgeModal] = useState(false);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState(new Set());
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [expandedModules, setExpandedModules] = useState(new Set());

  // Confirm write state
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState("");
  const [confirmResult, setConfirmResult] = useState(null);

  const courseLabel = getSubjectLabel(subject);

  const courseItems = currentFilterItems;

  // Stats
  const indexedCount = courseItems.filter((m) => m.parse_status === "success" || m.parse_status === "partial").length;
  const totalChunks = courseItems.reduce((sum, m) => sum + Number(m.chunk_count || 0), 0);
  const latestDate = courseItems.length > 0
    ? courseItems.reduce((latest, m) => {
        const d = new Date(m.created_at);
        return d > latest ? d : latest;
      }, new Date(0))
    : null;

  // Frontend filtering
  const displayedItems = (() => {
    let items = [...courseItems];

    // Type filter
    if (filterType !== "all") {
      items = items.filter((m) => {
        const t = (m.file_type || "").toLowerCase();
        if (filterType === "pdf") return t === "pdf";
        if (filterType === "image") return ["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].includes(t);
        if (filterType === "word") return t === "docx";
        if (filterType === "ppt") return t === "pptx";
        if (filterType === "txt") return ["txt", "md", "markdown"].includes(t);
        if (filterType === "code") return ["py", "java", "c", "cpp", "h", "hpp", "js", "jsx", "ts", "tsx", "go", "rs", "php", "rb", "sql", "sh", "bash", "html", "css", "json", "xml", "yaml", "yml"].includes(t);
        return true;
      });
    }

    // Index status filter
    if (filterIndex !== "all") {
      items = items.filter((m) => {
        if (filterIndex === "indexed") return m.parse_status === "success" || m.parse_status === "partial";
        if (filterIndex === "parsing") return m.parse_status === "parsing" || m.parse_status === "pending";
        if (filterIndex === "failed") return m.parse_status === "failed";
        if (filterIndex === "unindexed") return !m.parse_status || m.parse_status === "unknown";
        return true;
      });
    }

    return sortMaterials(items, materialSortMode);
  })();

  const displayTotalPages = Math.max(1, Math.ceil(displayedItems.length / PAGE_SIZE));
  const displayCurrentPage = Math.min(materialCurrentPage, displayTotalPages);
  const paginatedDisplayItems = displayedItems.slice(
    (displayCurrentPage - 1) * PAGE_SIZE,
    displayCurrentPage * PAGE_SIZE
  );

  const handleSearch = () => {
    const q = searchInput.trim();
    handleMaterialSearchChange(q);
    setMaterialCurrentPage(1);
    searchMaterials(q, subject);
  };

  const refreshList = () => {
    setMaterialCurrentPage(1);
    loadMaterials(subject);
  };

  // ── Knowledge Analysis ──

  const openKnowledgeModal = () => {
    setSelectedMaterialIds(new Set());
    setAnalyzeError("");
    setAnalyzeResult(null);
    setExpandedModules(new Set());
    setShowKnowledgeModal(true);
  };

  const closeKnowledgeModal = () => {
    setShowKnowledgeModal(false);
    setAnalyzeResult(null);
    setAnalyzeError("");
    setSelectedMaterialIds(new Set());
  };

  const toggleMaterialSelect = (id) => {
    setSelectedMaterialIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleModuleExpand = (idx) => {
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const handleAnalyzeKnowledge = async () => {
    if (selectedMaterialIds.size === 0) return;
    setAnalyzeLoading(true);
    setAnalyzeError("");
    setAnalyzeResult(null);
    setConfirmResult(null);
    setConfirmError("");
    setExpandedModules(new Set());
    try {
      const res = await fetch(`${API_BASE}/materials/analyze-knowledge-preview`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: subject,
          material_ids: Array.from(selectedMaterialIds),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "分析失败，请稍后重试");
      }
      setAnalyzeResult(data);
      // Auto-expand first 3 modules
      const tree = data.knowledge_tree || [];
      const autoExpand = new Set();
      tree.slice(0, 3).forEach((_, i) => autoExpand.add(i));
      setExpandedModules(autoExpand);
    } catch (e) {
      setAnalyzeError(e.message || "AI 分析失败，请稍后重试。");
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const handleConfirmKnowledgeTree = async () => {
    if (!analyzeResult || !analyzeResult.knowledge_tree) return;
    setConfirmLoading(true);
    setConfirmError("");
    setConfirmResult(null);
    try {
      const res = await fetch(`${API_BASE}/materials/confirm-knowledge-tree`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: user.username,
          course_id: subject,
          material_ids: Array.from(selectedMaterialIds),
          knowledge_tree: analyzeResult.knowledge_tree,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "写入失败，请稍后重试");
      }
      setConfirmResult(data);
    } catch (e) {
      setConfirmError(e.message || "写入知识点树失败，请稍后重试。");
    } finally {
      setConfirmLoading(false);
    }
  };

  const selectedParseStatus = selectedMaterialDetail?.parse_status || "";
  const selectedChunkCount = getMaterialChunkCount(selectedMaterialDetail);
  const selectedDetailNotice = (() => {
    if (!selectedMaterialDetail) return "";
    if (selectedParseStatus === "pending" || selectedParseStatus === "parsing") {
      return "资料正在解析 / 索引中，请稍后刷新。";
    }
    if (selectedParseStatus === "failed") {
      return "解析失败，可尝试重新索引。";
    }
    if (selectedChunkCount === 0) {
      return "暂无知识片段，请点击左侧资料卡片中的 AI 索引。";
    }
    return "";
  })();

  return (
    <div className="cmp-shell">
      {/* ── Title Area ── */}
      <div className="cmp-title-area">
        <div className="cmp-title-left">
          <div className="cmp-title-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          </div>
          <div>
            <h1 className="cmp-title-heading">课程资料 · {courseLabel}</h1>
            <p className="cmp-title-sub">
              管理当前课程的 PDF、图片、Word、PPT、TXT 和代码文件，资料会用于 AI 问答、知识点学习和学习路线生成。
            </p>
          </div>
        </div>
        <div className="cmp-title-actions">
          <button
            className="cmp-btn cmp-btn--primary"
            type="button"
            onClick={() => materialsFileInputRef.current?.click()}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            上传课程资料
          </button>
          <button className="cmp-btn cmp-btn--ghost" type="button" onClick={refreshList}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            刷新
          </button>
          <button
            className="cmp-btn cmp-btn--ghost"
            type="button"
            onClick={reindexLibrary}
            disabled={reindexLoading}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 2a10 10 0 1 0 10 10h-10v-10z" />
            </svg>
            {reindexLoading ? "重建中..." : "重建索引"}
          </button>
          <button
            className="cmp-btn cmp-btn--accent"
            type="button"
            onClick={openKnowledgeModal}
            disabled={courseItems.length === 0}
            title={courseItems.length === 0 ? "当前课程暂无资料" : "从已有资料中提取知识点结构"}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
            从资料生成知识点
          </button>
        </div>
        <input
          ref={materialsFileInputRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
          onChange={handleFileChange}
          className="cmp-hidden-file-input"
        />
      </div>

      {/* ── Stats Cards ── */}
      <div className="cmp-stats-row">
        <StatCard icon="📚" value={courseItems.length} label="资料总数" />
        <StatCard icon="🤖" value={indexedCount} label="已生成 AI 索引" />
        <StatCard icon="🧩" value={totalChunks} label="知识片段数" />
        <StatCard
          icon="🕐"
          value={latestDate ? formatDate(latestDate.toISOString()) : "暂无"}
          label="最近上传时间"
        />
      </div>

      {/* ── Search & Filter Bar ── */}
      <div className="cmp-filter-bar">
        <div className="cmp-filter-search">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            className="cmp-filter-search-input"
            placeholder={`在${courseLabel}资料中搜索文件名、章节或知识点...`}
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              handleMaterialSearchChange(e.target.value);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSearch();
              }
            }}
          />
          <button className="cmp-btn cmp-btn--primary cmp-btn--sm" type="button" onClick={handleSearch} disabled={!searchInput.trim() || materialSearchLoading}>
            搜索
          </button>
        </div>
        <div className="cmp-filter-options">
          <div className="cmp-filter-group">
            <span className="cmp-filter-label">类型</span>
            <div className="cmp-chip-row">
              {FILE_TYPES.map((ft) => (
                <button
                  key={ft.value}
                  type="button"
                  className={`cmp-chip${filterType === ft.value ? " cmp-chip--active" : ""}`}
                  onClick={() => { setFilterType(ft.value); setMaterialCurrentPage(1); }}
                >
                  {ft.label}
                </button>
              ))}
            </div>
          </div>
          <div className="cmp-filter-group">
            <span className="cmp-filter-label">索引状态</span>
            <div className="cmp-chip-row">
              {INDEX_STATUSES.map((is) => (
                <button
                  key={is.value}
                  type="button"
                  className={`cmp-chip${filterIndex === is.value ? " cmp-chip--active" : ""}`}
                  onClick={() => { setFilterIndex(is.value); setMaterialCurrentPage(1); }}
                >
                  {is.label}
                </button>
              ))}
            </div>
          </div>
          <div className="cmp-filter-group">
            <span className="cmp-filter-label">排序</span>
            <div className="cmp-chip-row">
              {SORT_OPTIONS.map((so) => (
                <button
                  key={so.value}
                  type="button"
                  className={`cmp-chip${materialSortMode === so.value ? " cmp-chip--active" : ""}`}
                  onClick={() => {
                    if (setMaterialSortMode) setMaterialSortMode(so.value);
                    setMaterialCurrentPage(1);
                  }}
                >
                  {so.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="cmp-content">
        <div className="cmp-main">
          {trimmedMaterialSearchQuery && materialSearchTriggered ? (
            materialSearchLoading ? (
              <div className="cmp-empty-state">
                <p className="cmp-empty-title">正在搜索...</p>
              </div>
            ) : materialSearchResults.length === 0 ? (
              <div className="cmp-empty-state">
                <div className="cmp-empty-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round">
                    <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                  </svg>
                </div>
                <p className="cmp-empty-title">没有匹配的资料</p>
                <p className="cmp-empty-hint">{courseLabel} 学科下没有匹配的资料。</p>
              </div>
            ) : (
              <div className="cmp-list">
                {paginatedSearchResults.map((item) => {
                  const hitSnippet = getMaterialHitSnippet(item);
                  return (
                  <div key={`${item.material_id}-${item.chunk_id}`} className="cmp-material-card">
                    <div className="cmp-material-card-top">
                      <span className={`cmp-file-icon ${getFileIconClass(item.file_type)}`}>
                        {getFileIconEmoji(item.file_type)}
                      </span>
                      <div className="cmp-material-card-info">
                        <span className="cmp-material-card-name">{item.filename}</span>
                        <span className="cmp-material-card-meta">
                          {getFileTypeLabel(item.file_type)} · {getSubjectLabel(item.subject)}
                        </span>
                        {hitSnippet && (
                          <span className="cmp-material-card-snippet material-hit-snippet">
                            <span>命中片段：</span>
                            <span>{hitSnippet}</span>
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="cmp-material-card-actions">
                      <button className="cmp-action-btn" onClick={() => openMaterialDetail(item.material_id)}>
                        查看详情
                      </button>
                    </div>
                  </div>
                  );
                })}
                <Pagination
                  page={safeSearchPage}
                  totalPages={searchTotalPages}
                  onPrev={() => setMaterialCurrentPage((p) => Math.max(1, p - 1))}
                  onNext={() => setMaterialCurrentPage((p) => Math.min(searchTotalPages, p + 1))}
                />
              </div>
            )
          ) : materialsLoading ? (
            <div className="cmp-empty-state">
              <div className="cmp-loading-spinner" />
              <p className="cmp-empty-title">资料加载中...</p>
            </div>
          ) : courseItems.length === 0 ? (
            /* ── Empty State ── */
            <div className="cmp-empty-state cmp-empty-state--full">
              <div className="cmp-empty-illustration">
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  <line x1="12" y1="11" x2="12" y2="17" />
                  <line x1="9" y1="14" x2="15" y2="14" />
                </svg>
              </div>
              <h3 className="cmp-empty-title">当前课程还没有资料</h3>
              <p className="cmp-empty-desc">
                上传教材、课件、笔记、图片或代码文件后，系统会自动解析内容，生成 AI 知识索引，并用于课程问答和知识点学习。
              </p>
              <button
                className="cmp-btn cmp-btn--primary cmp-btn--lg"
                type="button"
                onClick={() => materialsFileInputRef.current?.click()}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                上传课程资料
              </button>
              <div className="cmp-empty-formats">
                <p className="cmp-empty-formats-title">支持的文件格式</p>
                <div className="cmp-empty-format-list">
                  <span className="cmp-format-tag">📄 PDF 课件 / 教材</span>
                  <span className="cmp-format-tag">🖼️ 图片截图</span>
                  <span className="cmp-format-tag">📝 Word 文档</span>
                  <span className="cmp-format-tag">📊 PPT 课件</span>
                  <span className="cmp-format-tag">📃 TXT / Markdown</span>
                  <span className="cmp-format-tag">💻 C / C++ / Python / Java 等代码文件</span>
                </div>
              </div>
              <div className="cmp-empty-process">
                <p className="cmp-empty-process-title">上传后系统会自动完成：</p>
                <div className="cmp-empty-process-steps">
                  <span className="cmp-process-step"><span className="cmp-process-num">1</span> 保存原文</span>
                  <span className="cmp-process-arrow">→</span>
                  <span className="cmp-process-step"><span className="cmp-process-num">2</span> 提取文本</span>
                  <span className="cmp-process-arrow">→</span>
                  <span className="cmp-process-step"><span className="cmp-process-num">3</span> 生成知识片段</span>
                  <span className="cmp-process-arrow">→</span>
                  <span className="cmp-process-step"><span className="cmp-process-num">4</span> 建立 AI 索引</span>
                  <span className="cmp-process-arrow">→</span>
                  <span className="cmp-process-step"><span className="cmp-process-num">5</span> 支持问答引用</span>
                </div>
              </div>
            </div>
          ) : displayedItems.length === 0 ? (
            /* ── Filtered empty ── */
            <div className="cmp-empty-state">
              <div className="cmp-empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round">
                  <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
                </svg>
              </div>
              <p className="cmp-empty-title">没有符合条件的资料</p>
              <p className="cmp-empty-hint">尝试调整筛选条件查看其他资料。</p>
            </div>
          ) : (
            /* ── Material List ── */
            <div className="cmp-list">
              {paginatedDisplayItems.map((material) => (
                <MaterialCard
                  key={material.id}
                  material={material}
                  getSubjectLabel={getSubjectLabel}
                  onPreview={previewMaterial}
                  onDownload={downloadMaterial}
                  onDetail={openMaterialDetail}
                  onDelete={deleteMaterial}
                  onReparse={reparseMaterial}
                />
              ))}
              {displayTotalPages > 1 && (
                <Pagination
                  page={displayCurrentPage}
                  totalPages={displayTotalPages}
                  onPrev={() => setMaterialCurrentPage((p) => Math.max(1, p - 1))}
                  onNext={() => setMaterialCurrentPage((p) => Math.min(displayTotalPages, p + 1))}
                />
              )}
            </div>
          )}
        </div>

        {/* ── Right Sidebar: Material Detail ── */}
        <aside className="cmp-sidebar">
          <div className="cmp-detail-card">
            <div className="cmp-detail-card-header">
              <h3 className="cmp-detail-card-title">资料详情</h3>
            </div>
            {!selectedMaterialDetail ? (
              <div className="cmp-detail-empty">
                {courseItems.length === 0 ? (
                  <>
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <h4>选择资料查看详情</h4>
                    <p>上传资料后，可在这里查看原文、解析摘要和 AI 索引详情。</p>
                    <p>资料生成知识片段后，即可在 AI 问答中引用。</p>
                  </>
                ) : (
                  <>
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" strokeLinecap="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <h4>选择资料查看详情</h4>
                    <p>点击左侧资料卡片可查看原文、索引状态和知识片段。</p>
                    <p>如果该资料还没有生成知识片段，请先点击左侧资料卡片中的 AI 索引，索引完成后即可在 AI 问答中引用该资料。</p>
                  </>
                )}
              </div>
            ) : (
              <div className="cmp-detail-body">
                <div className="cmp-detail-filename">{selectedMaterialDetail.original_filename}</div>
                <div className="cmp-detail-meta">
                  <span>{getFileTypeLabel(selectedMaterialDetail.file_type)}</span>
                  <span>{formatFileSize(selectedMaterialDetail.file_size)}</span>
                  <span>{formatDate(selectedMaterialDetail.created_at)}</span>
                  <span>{getSubjectLabel(selectedMaterialDetail.subject)}</span>
                </div>
                <div className="cmp-detail-status">
                  <span className={`cmp-index-badge cmp-index-badge--${selectedMaterialDetail.parse_status || "unknown"}`}>
                    {getParseStatusLabel(selectedMaterialDetail.parse_status)}
                  </span>
                  <span>{selectedChunkCount} 个知识片段</span>
                </div>
                <div className="cmp-detail-hint">{getParseStatusHint(selectedMaterialDetail)}</div>
                {selectedDetailNotice && (
                  <div className="cmp-detail-callout">{selectedDetailNotice}</div>
                )}
                <div className="cmp-detail-actions">
                  <button className="cmp-action-btn" onClick={() => previewMaterial(selectedMaterialDetail)} disabled={!selectedMaterialDetail.can_preview}>
                    查看原文件
                  </button>
                  <button className="cmp-action-btn" onClick={() => downloadMaterial(selectedMaterialDetail)} disabled={!selectedMaterialDetail.can_download}>
                    下载原文件
                  </button>
                </div>
                {selectedMaterialDetail.summary && (
                  <div className="cmp-detail-section">
                    <strong>摘要</strong>
                    <p>{selectedMaterialDetail.summary}</p>
                  </div>
                )}
                {selectedMaterialDetail.extracted_text && (
                  <div className="cmp-detail-section">
                    <strong>AI 知识索引文本</strong>
                    <pre className="cmp-detail-pre">{selectedMaterialDetail.extracted_text}</pre>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quick link to AI */}
          <button
            className="cmp-btn cmp-btn--ghost cmp-btn--block"
            type="button"
            onClick={() => setPage("chat")}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            前往 AI 问答引用资料
          </button>
        </aside>
      </div>

      {/* ── Knowledge Analysis Modal (Portal) ── */}
      {showKnowledgeModal && createPortal(
        <div className="kam-overlay" onClick={(e) => { if (e.target === e.currentTarget) closeKnowledgeModal(); }}>
          <div className="kam-modal">
            <button className="kam-close" onClick={closeKnowledgeModal} aria-label="关闭">×</button>
            <div className="kam-body">
              <h2 className="kam-title">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0 }}>
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
                从资料生成知识点
              </h2>

              {/* ── Step 1: Select Materials ── */}
              {!analyzeResult && !analyzeLoading && (
                <>
                  <p className="kam-step-label">步骤 1：选择要分析的资料（可多选）</p>
                  {courseItems.length === 0 ? (
                    <div className="kam-empty">
                      <p>当前课程暂无资料，请先上传资料。</p>
                      <button className="cmp-btn cmp-btn--primary" type="button" onClick={() => { closeKnowledgeModal(); materialsFileInputRef.current?.click(); }}>
                        上传课程资料
                      </button>
                    </div>
                  ) : (
                    <div className="kam-material-list">
                      {courseItems.map((mat) => {
                        const isSelected = selectedMaterialIds.has(mat.id);
                        // Allow selection unless we're certain there's no analysable text
                        // (materials with chunks, extracted_text, or even failed-but-parsed may still have content)
                        const hasChunks = (mat.parse_status === "success" || mat.parse_status === "partial") && Number(mat.chunk_count || 0) > 0;
                        const mayHaveText = mat.parse_status === "success" || mat.parse_status === "partial" || mat.parse_status === "failed" || !mat.parse_status || mat.parse_status === "unknown";
                        const disabled = false; // let backend decide — materials without content will get an error from the server
                        return (
                          <div
                            key={mat.id}
                            className={`kam-material-item ${isSelected ? "kam-material-item--selected" : ""}`}
                            onClick={() => toggleMaterialSelect(mat.id)}
                          >
                            <div className="kam-material-check">
                              {isSelected ? "☑" : "☐"}
                            </div>
                            <div className="kam-material-info">
                              <span className="kam-material-name">
                                <span>{getFileIconEmoji(mat.file_type)}</span>
                                {" "}{mat.original_filename}
                              </span>
                              <span className="kam-material-meta">
                                {getFileTypeLabel(mat.file_type)} · {formatFileSize(mat.file_size)} · {formatDate(mat.created_at)}
                                {" · "}{Number(mat.chunk_count || 0)} 个知识片段
                                {!hasChunks && mayHaveText && " · 文本模式（无片段）"}
                                {!hasChunks && !mayHaveText && " · 暂无可用文本"}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  <div className="kam-footer">
                    <span className="kam-footer-hint">
                      {selectedMaterialIds.size === 0
                        ? "请至少选择一份已完成 AI 索引的资料"
                        : `已选择 ${selectedMaterialIds.size} 份资料`}
                    </span>
                    <button
                      className="cmp-btn cmp-btn--primary"
                      type="button"
                      onClick={handleAnalyzeKnowledge}
                      disabled={selectedMaterialIds.size === 0}
                    >
                      开始分析
                    </button>
                  </div>
                </>
              )}

              {/* ── Loading ── */}
              {analyzeLoading && (
                <div className="kam-loading">
                  <div className="cmp-loading-spinner" />
                  <p>正在分析资料结构...</p>
                  <p className="kam-loading-hint">AI 正在读取资料内容并提取知识点，请稍候。</p>
                </div>
              )}

              {/* ── Error ── */}
              {analyzeError && !analyzeLoading && (
                <div className="kam-error">
                  <p>{analyzeError}</p>
                  <div className="kam-error-actions">
                    <button className="cmp-btn cmp-btn--ghost" type="button" onClick={() => { setAnalyzeError(""); }}>
                      返回重新选择
                    </button>
                    <button className="cmp-btn cmp-btn--primary" type="button" onClick={handleAnalyzeKnowledge}>
                      重试
                    </button>
                  </div>
                </div>
              )}

              {/* ── Result: Knowledge Tree Preview ── */}
              {analyzeResult && !analyzeLoading && (
                <>
                  {/* ── Confirm Loading ── */}
                  {confirmLoading && (
                    <div className="kam-confirm-loading">
                      <div className="cmp-loading-spinner" />
                      <p>正在写入知识点树...</p>
                    </div>
                  )}

                  {/* ── Confirm Error ── */}
                  {confirmError && !confirmLoading && (
                    <div className="kam-error">
                      <p>{confirmError}</p>
                      <div className="kam-error-actions">
                        <button className="cmp-btn cmp-btn--ghost" type="button" onClick={() => setConfirmError("")}>
                          关闭
                        </button>
                        <button className="cmp-btn cmp-btn--primary" type="button" onClick={handleConfirmKnowledgeTree}>
                          重试
                        </button>
                      </div>
                    </div>
                  )}

                  {/* ── Confirm Success ── */}
                  {confirmResult && !confirmLoading && (
                    <div className="kam-confirm-success">
                      <div className="kam-confirm-success-icon">✅</div>
                      <h3 className="kam-confirm-success-title">知识点已成功写入</h3>
                      <div className="kam-confirm-stats">
                        <div className="kam-confirm-stat">
                          <span className="kam-confirm-stat-value">{confirmResult.created_modules}</span>
                          <span className="kam-confirm-stat-label">新增大模块</span>
                        </div>
                        <div className="kam-confirm-stat">
                          <span className="kam-confirm-stat-value">{confirmResult.created_points}</span>
                          <span className="kam-confirm-stat-label">新增小知识点</span>
                        </div>
                        <div className="kam-confirm-stat">
                          <span className="kam-confirm-stat-value">{confirmResult.skipped_duplicates}</span>
                          <span className="kam-confirm-stat-label">跳过重复</span>
                        </div>
                      </div>
                      <p className="kam-confirm-success-hint">
                        知识点已写入，可在任务绑定知识点和练习筛选中使用。
                      </p>
                      <div className="kam-confirm-success-actions">
                        <button className="cmp-btn cmp-btn--ghost" type="button" onClick={closeKnowledgeModal}>
                          关闭
                        </button>
                      </div>
                    </div>
                  )}

                  {/* ── Tree preview (hidden after confirm success but shown during normal preview/error) ── */}
                  {!confirmResult && !confirmLoading && (
                    <>
                      <div className="kam-result-header">
                        <span className="kam-step-label">知识点树预览</span>
                        <span className="kam-result-stats">
                          共 {(analyzeResult.knowledge_tree || []).length} 个大模块，
                          {(() => { let c = 0; (analyzeResult.knowledge_tree || []).forEach(m => { c += (m.children || []).length; }); return c; })()} 个知识点
                        </span>
                      </div>

                      {(analyzeResult.knowledge_tree || []).length === 0 ? (
                        <div className="kam-empty">
                          <p>未能从资料中提取有效知识点。</p>
                          <p className="kam-empty-hint">请确认所选资料内容与课程相关，或尝试选择更多资料后重试。</p>
                        </div>
                      ) : (
                        <div className="kam-tree">
                          {(analyzeResult.knowledge_tree || []).map((module, idx) => {
                            const isExpanded = expandedModules.has(idx);
                            return (
                              <div key={idx} className="kam-tree-module">
                                <button
                                  className="kam-tree-module-header"
                                  onClick={() => toggleModuleExpand(idx)}
                                  type="button"
                                >
                                  <span className={`kam-tree-arrow ${isExpanded ? "kam-tree-arrow--open" : ""}`}>▶</span>
                                  <div className="kam-tree-module-info">
                                    <span className="kam-tree-module-title">{module.title}</span>
                                    {module.description && (
                                      <span className="kam-tree-module-desc">{module.description}</span>
                                    )}
                                  </div>
                                  <span className="kam-tree-module-count">{module.children ? module.children.length : 0} 项</span>
                                </button>
                                {isExpanded && module.children && module.children.length > 0 && (
                                  <div className="kam-tree-children">
                                    {module.children.map((child, cidx) => (
                                      <div key={cidx} className="kam-tree-child">
                                        <div className="kam-tree-child-dot" />
                                        <div className="kam-tree-child-info">
                                          <span className="kam-tree-child-title">{child.title}</span>
                                          {child.description && (
                                            <span className="kam-tree-child-desc">{child.description}</span>
                                          )}
                                          {child.source_material_titles && child.source_material_titles.length > 0 && (
                                            <span className="kam-tree-child-source">
                                              来源：{child.source_material_titles.join("、")}
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {!confirmError && (
                        <div className="kam-footer">
                          <span className="kam-footer-hint kam-footer-hint--preview">
                            ⚠️ 当前仅为预览，点击确认后写入知识点树。
                          </span>
                          <div className="kam-footer-actions">
                            <button className="cmp-btn cmp-btn--ghost" type="button" onClick={() => { setAnalyzeResult(null); setAnalyzeError(""); setConfirmResult(null); }}>
                              返回重新选择
                            </button>
                            <button
                              className="cmp-btn cmp-btn--primary"
                              type="button"
                              onClick={handleConfirmKnowledgeTree}
                              disabled={confirmLoading}
                            >
                              {confirmLoading ? "写入中..." : "确认写入知识点树"}
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

function Pagination({ page, totalPages, onPrev, onNext }) {
  return (
    <div className="cmp-pagination">
      <button className="cmp-pagination-btn" disabled={page <= 1} onClick={onPrev}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        上一页
      </button>
      <span className="cmp-pagination-info">{page} / {totalPages}</span>
      <button className="cmp-pagination-btn" disabled={page >= totalPages} onClick={onNext}>
        下一页
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <polyline points="9 18 15 12 9 6" />
        </svg>
      </button>
    </div>
  );
}
