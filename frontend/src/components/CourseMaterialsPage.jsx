import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import "./CourseMaterialsPage.css";

const API_BASE = "/api";
const PAGE_SIZE = 10;

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
  { value: "nameAsc", label: "文件名 ↑" },
  { value: "nameDesc", label: "文件名 ↓" },
  { value: "sizeAsc", label: "大小 ↑" },
  { value: "sizeDesc", label: "大小 ↓" },
  { value: "chunksAsc", label: "片段 ↑" },
  { value: "chunksDesc", label: "片段 ↓" },
];

function getCourseDisplay(subject, getSubjectLabel, isCourseMode = false) {
  const raw = String(subject || "").trim();
  if (isCourseMode) {
    // course_learning: use raw course name directly — no alias mapping
    return { title: raw || "当前课程", course: raw || "当前课程" };
  }
  const withoutPrefix = raw.replace(/^11408\s*/, "").trim();
  const label = raw.startsWith("11408 ")
    ? withoutPrefix
    : (getSubjectLabel?.(withoutPrefix) || withoutPrefix || getSubjectLabel?.(raw) || raw);
  return {
    title: label || "当前科目",
    course: raw.startsWith("11408 ") ? raw : `11408 ${label || raw}`,
  };
}

function formatDateTime(value) {
  if (!value) return "-";
  const text = String(value).trim();
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(text)
    ? `${text}Z`
    : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatFileSize(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function filenameOf(material) {
  return String(material?.original_filename || material?.filename || material?.name || "").trim();
}

function fileSizeOf(material) {
  return Number(material?.file_size ?? material?.size ?? material?.fileSize ?? 0) || 0;
}

function chunkCountOf(material) {
  return Number(material?.chunk_count ?? material?.chunks ?? material?.chunkCount ?? 0) || 0;
}

function createdTimeOf(material) {
  const value = material?.created_at || material?.uploaded_at || material?.upload_time || material?.updated_at || 0;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function normalizeFileType(type) {
  return String(type || "").toLowerCase();
}

function getTypeGroup(material) {
  const t = normalizeFileType(material?.file_type || material?.type);
  if (t.includes("pdf")) return "pdf";
  if (["png", "jpg", "jpeg", "webp", "gif", "bmp", "svg"].some((x) => t.includes(x)) || t.includes("image")) return "image";
  if (t.includes("docx") || t.includes("word")) return "word";
  if (t.includes("pptx") || t.includes("ppt") || t.includes("powerpoint")) return "ppt";
  if (["txt", "text", "md", "markdown"].some((x) => t.includes(x))) return "txt";
  if (["py", "java", "c++", "cpp", " js", "javascript", "ts", "tsx", "jsx", "html", "css", "json", "xml", "yaml", "yml", "sql", "sh", "bash", "go", "rs", "php", "rb", "code"].some((x) => t.includes(x))) return "code";
  return t || "txt";
}

function getFileTypeLabel(type) {
  const group = getTypeGroup({ file_type: type });
  if (group === "image") return "图片";
  if (group === "word") return "Word";
  if (group === "ppt") return "PPT";
  if (group === "txt") return "TXT";
  if (group === "code") return "代码";
  if (group === "pdf") return "PDF";
  return String(type || "未知").toUpperCase();
}

function getFileIcon(material) {
  const group = getTypeGroup(material);
  if (group === "pdf") return { text: "PDF", cls: "pdf" };
  if (group === "word") return { text: "W", cls: "word" };
  if (group === "ppt") return { text: "PPT", cls: "ppt" };
  if (group === "image") return { text: "IMG", cls: "image" };
  if (group === "code") return { text: "</>", cls: "code" };
  return { text: "TXT", cls: "txt" };
}

function getStatusKind(status) {
  const s = String(status || "").trim();
  if (s === "success" || s === "partial") return "indexed";
  if (s === "parsing" || s === "pending") return "parsing";
  if (s === "failed") return "failed";
  return "unindexed";
}

function getStatusLabel(status) {
  const kind = getStatusKind(status);
  if (kind === "indexed") return "已索引";
  if (kind === "parsing") return "解析中";
  if (kind === "failed") return "解析失败";
  return "未索引";
}

function getSummary(material) {
  const text =
    material?.summary ||
    material?.content_summary ||
    material?.abstract ||
    material?.description ||
    material?.extracted_text ||
    "";
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!clean) return "暂无内容摘要。完成解析后，这里会展示资料摘要和可引用内容。";
  return clean.length > 180 ? `${clean.slice(0, 180)}...` : clean;
}

function isReferenceMetadata(material) {
  return material?.source_type === "reference_metadata" || material?.visibility === "system_public_metadata";
}

function getSourceMeta(material) {
  if (isReferenceMetadata(material)) {
    return {
      label: "官方参考",
      detail: "仅目录索引",
      className: "reference",
      notice: "官方参考资料仅包含目录、章节定位和知识点索引，不包含第三方资料正文，不提供原文下载。",
    };
  }
  return {
    label: "我的上传",
    detail: "仅自己可见",
    className: "private",
    notice: "该资料由你上传，仅你可见。请确保你拥有该资料的合法使用权。系统仅用于个人学习、AI 问答和知识点整理。",
  };
}

function sortMaterials(items, sortMode) {
  const sorted = [...items];
  sorted.sort((a, b) => {
    if (sortMode === "oldest") return createdTimeOf(a) - createdTimeOf(b);
    if (sortMode === "nameAsc") return filenameOf(a).localeCompare(filenameOf(b), "zh-CN");
    if (sortMode === "nameDesc") return filenameOf(b).localeCompare(filenameOf(a), "zh-CN");
    if (sortMode === "sizeAsc") return fileSizeOf(a) - fileSizeOf(b);
    if (sortMode === "sizeDesc") return fileSizeOf(b) - fileSizeOf(a);
    if (sortMode === "chunksAsc") return chunkCountOf(a) - chunkCountOf(b);
    if (sortMode === "chunksDesc") return chunkCountOf(b) - chunkCountOf(a);
    return createdTimeOf(b) - createdTimeOf(a);
  });
  return sorted;
}

function StatCard({ icon, value, label }) {
  return (
    <div className="cmp-stat-card">
      <span className="cmp-stat-icon">{icon}</span>
      <div>
        <div className="cmp-stat-value">{value}</div>
        <div className="cmp-stat-label">{label}</div>
      </div>
    </div>
  );
}

function ChipGroup({ label, options, value, onChange }) {
  return (
    <div className="cmp-filter-group">
      <span className="cmp-filter-label">{label}</span>
      <div className="cmp-chip-row">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`cmp-chip${value === option.value ? " cmp-chip--active" : ""}`}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function MaterialIcon({ material, large = false }) {
  const icon = getFileIcon(material);
  return <span className={`cmp-file-icon cmp-file-icon--${icon.cls}${large ? " cmp-file-icon--large" : ""}`}>{icon.text}</span>;
}

export default function CourseMaterialsPage({
  user,
  subject,
  getSubjectLabel,
  mode = "exam_11408",         // "exam_11408" | "course_learning"
  courseName = "",              // used in course_learning mode
  materials = [],
  materialsLoading,
  reindexLoading,
  materialSortMode = "newest",
  setMaterialSortMode,
  materialCurrentPage,
  setMaterialCurrentPage,
  materialSearchLoading,
  materialSearchResults = [],
  selectedMaterialDetail,
  materialsFileInputRef,
  handleFileChange,
  loadMaterials,
  searchMaterials,
  reindexLibrary,
  openMaterialDetail,
  previewMaterial,
  downloadMaterial,
  reparseMaterial,
  setPage,
  onQuoteMaterial,
  initialSearchQuery = "",
  examCramMode = false,
}) {
  const isCourseMode = mode === "course_learning";
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showSummary, setShowSummary] = useState(false);
  const [showKnowledgeModal, setShowKnowledgeModal] = useState(false);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState(new Set());
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeError, setAnalyzeError] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState("");
  const [confirmResult, setConfirmResult] = useState(null);
  const [expandedModules, setExpandedModules] = useState(new Set());
  const appliedInitialSearchRef = useRef("");

  const course = getCourseDisplay(subject, getSubjectLabel, isCourseMode);
  const rawItems = Array.isArray(materials) ? materials : [];
  // In course_learning mode, filter to current course + exclude 11408 reference metadata
  const currentItems = useMemo(() => {
    if (!isCourseMode) return rawItems;
    const courseSubject = String(subject || "").trim();
    return rawItems.filter((item) => {
      if (isReferenceMetadata(item)) return false;
      if (!courseSubject) return true;
      const itemSubject = String(item.subject || item.course_id || item.course_name || "").trim();
      // 11408 materials use "11408 " prefix — exclude them
      if (itemSubject.startsWith("11408 ")) return false;
      return itemSubject === courseSubject;
    });
  }, [rawItems, isCourseMode, subject]);

  const matchedMaterialIds = useMemo(() => {
    if (!query.trim()) return new Set();
    return new Set(
      (materialSearchResults || [])
        .map((item) => item.material_id || item.id)
        .filter(Boolean)
        .map(String)
    );
  }, [materialSearchResults, query]);

  const stats = useMemo(() => {
    const latest = currentItems.reduce((acc, item) => Math.max(acc, createdTimeOf(item)), 0);
    return {
      total: currentItems.length,
      indexed: currentItems.filter((item) => getStatusKind(item.parse_status) === "indexed").length,
      chunks: currentItems.reduce((sum, item) => sum + chunkCountOf(item), 0),
      latest: latest ? formatDateTime(latest) : "-",
    };
  }, [currentItems]);

  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    let items = currentItems.filter((item) => {
      if (typeFilter !== "all" && getTypeGroup(item) !== typeFilter) return false;
      if (statusFilter !== "all" && getStatusKind(item.parse_status) !== statusFilter) return false;
      if (!needle) return true;
      const localText = [
        filenameOf(item),
        item.subject,
        item.chapter,
        item.knowledge_point,
        item.summary,
        item.content_summary,
        item.parse_error,
      ].filter(Boolean).join(" ").toLowerCase();
      return localText.includes(needle) || matchedMaterialIds.has(String(item.id));
    });
    items = sortMaterials(items, materialSortMode);
    return items;
  }, [currentItems, matchedMaterialIds, materialSortMode, query, statusFilter, typeFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const currentPage = Math.min(Math.max(1, materialCurrentPage || 1), totalPages);
  const paginatedItems = filteredItems.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  useEffect(() => {
    setMaterialCurrentPage(1);
  }, [subject, query, typeFilter, statusFilter, materialSortMode, setMaterialCurrentPage]);

  useEffect(() => {
    const nextQuery = String(initialSearchQuery || "").trim();
    if (!nextQuery) return;
    if (appliedInitialSearchRef.current === `${subject}:${nextQuery}`) return;
    appliedInitialSearchRef.current = `${subject}:${nextQuery}`;
    setQuery(nextQuery);
    setMaterialCurrentPage(1);
    searchMaterials?.(nextQuery, subject);
  }, [initialSearchQuery, searchMaterials, setMaterialCurrentPage, subject]);

  useEffect(() => {
    setShowSummary(false);
  }, [selectedMaterialDetail?.id]);

  const runSearch = () => {
    setMaterialCurrentPage(1);
    if (query.trim()) searchMaterials?.(query.trim(), subject);
  };

  const refreshAll = async () => {
    setMaterialCurrentPage(1);
    await loadMaterials?.(subject);
    if (selectedMaterialDetail?.id) {
      await openMaterialDetail?.(selectedMaterialDetail.id);
    }
    if (query.trim()) searchMaterials?.(query.trim(), subject);
  };

  const handleReindex = async () => {
    await reindexLibrary?.(subject);
    await loadMaterials?.(subject);
  };

  const openKnowledgeModal = () => {
    setSelectedMaterialIds(new Set());
    setAnalyzeError("");
    setAnalyzeResult(null);
    setConfirmError("");
    setConfirmResult(null);
    setExpandedModules(new Set());
    setShowKnowledgeModal(true);
  };

  const closeKnowledgeModal = () => {
    setShowKnowledgeModal(false);
    setAnalyzeError("");
    setAnalyzeResult(null);
    setConfirmError("");
    setConfirmResult(null);
    setSelectedMaterialIds(new Set());
  };

  const toggleMaterialSelect = (id) => {
    setSelectedMaterialIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleModuleExpand = (index) => {
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const handleAnalyzeKnowledge = async () => {
    if (!user?.username || selectedMaterialIds.size === 0) return;
    setAnalyzeLoading(true);
    setAnalyzeError("");
    setAnalyzeResult(null);
    setConfirmError("");
    setConfirmResult(null);
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
        setAnalyzeError(data.detail || "从资料生成知识点失败。");
        return;
      }
      setAnalyzeResult(data);
      setExpandedModules(new Set([0]));
    } catch (error) {
      console.error("Failed to analyze materials:", error);
      setAnalyzeError("暂时无法分析资料，请稍后重试。");
    } finally {
      setAnalyzeLoading(false);
    }
  };

  const handleConfirmKnowledgeTree = async () => {
    if (!user?.username || !analyzeResult) return;
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
          knowledge_tree: analyzeResult.knowledge_tree || [],
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setConfirmError(data.detail || "写入知识点失败。");
        return;
      }
      setConfirmResult(data);
    } catch (error) {
      console.error("Failed to confirm knowledge tree:", error);
      setConfirmError("暂时无法写入知识点，请稍后重试。");
    } finally {
      setConfirmLoading(false);
    }
  };

  const selected = selectedMaterialDetail;
  const selectedPages = selected?.page_count || selected?.pages || selected?.total_pages;
  const fullSummary = String(selected?.summary || selected?.content_summary || selected?.extracted_text || "").trim();
  const selectedSourceMeta = selected ? getSourceMeta(selected) : null;
  const selectedCanModify = selected ? !isReferenceMetadata(selected) : false;

  return (
    <div className="cmp-shell">
      <section className="cmp-main-panel">
        <header className="cmp-header">
          <div>
            {(!isCourseMode || examCramMode) && <h1>{examCramMode ? course.title : `资料库 · ${course.title}`}</h1>}
            <p>{examCramMode ? "考试突击 · 复习资料管理" : (isCourseMode ? "课程资料管理" : `当前课程：${course.course}`)}</p>
          </div>
          <div className="cmp-header-actions">
            <button className="cmp-btn cmp-btn--primary" type="button" onClick={() => materialsFileInputRef.current?.click()}>
              {examCramMode ? "上传复习资料" : "上传课程资料"}
            </button>
            <button className="cmp-btn cmp-btn--ghost" type="button" onClick={refreshAll} disabled={materialsLoading}>
              刷新
            </button>
            <button className="cmp-btn cmp-btn--ghost" type="button" onClick={handleReindex} disabled={reindexLoading}>
              {reindexLoading ? "重建中..." : "重建索引"}
            </button>
          </div>
          <input
            ref={materialsFileInputRef}
            className="cmp-hidden-file-input"
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.pptx,.txt,.md,.markdown,.py,.java,.c,.cpp,.h,.hpp,.js,.jsx,.ts,.tsx,.html,.htm,.css,.json,.xml,.yaml,.yml,.sql,.sh,.bash,.go,.rs,.php,.rb"
            onChange={handleFileChange}
          />
        </header>
        <div className="cmp-upload-notice">
          {examCramMode ? (
            <span>优先上传复习范围、往年题、重点 PPT 和课堂笔记，便于 AI 提炼考试重点。</span>
          ) : (
            <>
              <span>请上传你拥有合法使用权的学习资料。上传内容仅用于你的个人学习、AI 问答和知识点整理，不会公开给其他用户。</span>
              <span>支持较大 PDF 上传；文本型 PDF 会尽量全文解析，扫描型 PDF 的 OCR 页数按套餐控制，普通套餐默认最多识别 20 页，全程考包支持更大规模 OCR。</span>
            </>
          )}
        </div>

        <div className="cmp-stats-row">
          <StatCard icon="▣" value={stats.total} label="资料总数" />
          <StatCard icon="AI" value={stats.indexed} label="已生成 AI 索引" />
          <StatCard icon="◆" value={stats.chunks.toLocaleString("zh-CN")} label="知识片段数" />
          <StatCard icon="◴" value={stats.latest} label="最近上传时间" />
        </div>

        <div className="cmp-filter-card">
          <div className="cmp-search-row">
            <div className="cmp-search-box">
              <span>⌕</span>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") runSearch();
                }}
                placeholder={examCramMode ? "搜索文件名、章节或考试范围…" : "在当前科目中搜索文件名、章节或知识点…"}
              />
            </div>
            <button className="cmp-btn cmp-btn--primary" type="button" onClick={runSearch} disabled={materialSearchLoading}>
              {materialSearchLoading ? "搜索中..." : "搜索"}
            </button>
          </div>
          <ChipGroup label="类型" options={FILE_TYPES} value={typeFilter} onChange={setTypeFilter} />
          <ChipGroup label="索引状态" options={INDEX_STATUSES} value={statusFilter} onChange={setStatusFilter} />
          <div className="cmp-filter-group">
            <span className="cmp-filter-label">排序</span>
            <select className="cmp-sort-select" value={materialSortMode} onChange={(event) => setMaterialSortMode(event.target.value)}>
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="cmp-table-card">
          <table className="cmp-material-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>来源</th>
                <th>类型</th>
                <th>大小</th>
                <th>上传时间</th>
                <th>索引状态</th>
                <th>片段数</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {materialsLoading ? (
                <tr><td colSpan="8"><div className="cmp-empty-inline">正在加载当前科目资料...</div></td></tr>
              ) : paginatedItems.length === 0 ? (
                <tr>
                  <td colSpan="8">
                    <div className="cmp-empty-state">
                      <div className="cmp-empty-mark">▣</div>
                      <h3>{currentItems.length === 0 ? "当前科目还没有资料" : "没有符合条件的资料"}</h3>
                      <p>上传课程资料后，可用于 AI 问答引用和学习。</p>
                      <p className="cmp-empty-note">请上传你拥有合法使用权的学习资料；较大 PDF 会先入库，再由后台分批解析。</p>
                      <button className="cmp-btn cmp-btn--primary" type="button" onClick={() => materialsFileInputRef.current?.click()}>
                        上传课程资料
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedItems.map((material) => {
                  const sourceMeta = getSourceMeta(material);
                  return (
                  <tr
                    key={material.id}
                    className={selected?.id === material.id ? "cmp-row-selected" : ""}
                    onClick={() => openMaterialDetail?.(material.id)}
                  >
                    <td>
                      <div className="cmp-file-cell">
                        <MaterialIcon material={material} />
                        <span title={filenameOf(material)}>{filenameOf(material)}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`cmp-source-badge cmp-source-badge--${sourceMeta.className}`}>
                        <strong>{sourceMeta.label}</strong>
                        <small>{sourceMeta.detail}</small>
                      </span>
                    </td>
                    <td>{getFileTypeLabel(material.file_type)}</td>
                    <td>{formatFileSize(material.file_size)}</td>
                    <td>{formatDateTime(material.created_at)}</td>
                    <td><span className={`cmp-status cmp-status--${getStatusKind(material.parse_status)}`}>{getStatusLabel(material.parse_status)}</span></td>
                    <td>{chunkCountOf(material).toLocaleString("zh-CN")}</td>
                    <td>
                      <div className="cmp-table-actions" onClick={(event) => event.stopPropagation()}>
                        <button type="button" onClick={() => openMaterialDetail?.(material.id)}>查看</button>
                        <button type="button" onClick={() => onQuoteMaterial?.(material)}>引用</button>
                        <button type="button" title="查看原文" onClick={() => previewMaterial?.(material)} disabled={!material.can_preview}>···</button>
                      </div>
                    </td>
                  </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {filteredItems.length > 0 && (
            <div className="cmp-pagination">
              <span>共 {filteredItems.length} 条</span>
              <div className="cmp-page-buttons">
                <button type="button" disabled={currentPage <= 1} onClick={() => setMaterialCurrentPage(currentPage - 1)}>‹</button>
                <span>{currentPage} / {totalPages}</span>
                <button type="button" disabled={currentPage >= totalPages} onClick={() => setMaterialCurrentPage(currentPage + 1)}>›</button>
              </div>
            </div>
          )}
        </div>
      </section>

      <aside className="cmp-detail-panel">
        <div className="cmp-detail-header">
          <h2>资料详情</h2>
          <span>⌃</span>
        </div>
        {!selected ? (
          <div className="cmp-detail-empty">
            <div className="cmp-empty-mark">▣</div>
            <h3>{examCramMode ? "推荐优先复习" : "请选择资料查看详情"}</h3>
            {examCramMode ? (
              <div className="cmp-cram-recommend-list">
                <span>复习范围说明或考试大纲</span>
                <span>近年真题与参考答案</span>
                <span>重点 PPT 和课堂笔记</span>
              </div>
            ) : (
              <p>上传资料后可用于 AI 问答引用和学习。</p>
            )}
          </div>
        ) : (
          <>
            <div className="cmp-detail-file-card">
              <MaterialIcon material={selected} large />
              <strong title={filenameOf(selected)}>{filenameOf(selected)}</strong>
              <span>{getFileTypeLabel(selected.file_type)} · {formatFileSize(selected.file_size)}</span>
            </div>
            <dl className="cmp-detail-meta">
              <div><dt>上传时间</dt><dd>{formatDateTime(selected.created_at)}</dd></div>
              <div><dt>索引状态</dt><dd><span className={`cmp-status cmp-status--${getStatusKind(selected.parse_status)}`}>{getStatusLabel(selected.parse_status)}</span></dd></div>
              <div><dt>片段数量</dt><dd>{chunkCountOf(selected).toLocaleString("zh-CN")}</dd></div>
              {selectedPages ? <div><dt>文件页数</dt><dd>{selectedPages} 页</dd></div> : null}
              {selected.ocr_required ? <div><dt>OCR 页数上限</dt><dd>{selected.ocr_page_limit || 20} 页</dd></div> : null}
              {selected.parsed_pages > 0 ? <div><dt>已解析页</dt><dd>{selected.parsed_pages} 页{selected.ocr_required ? "（含 OCR）" : ""}</dd></div> : null}
              {selected.is_partial_index ? <div><dt>解析状态</dt><dd><span className="cmp-status cmp-status--partial">已部分索引</span></dd></div> : null}
              <div><dt>来源</dt><dd>{selectedSourceMeta?.label} · {selectedSourceMeta?.detail}</dd></div>
            </dl>
            <div className={`cmp-permission-notice cmp-permission-notice--${selectedSourceMeta?.className}`}>
              {selectedSourceMeta?.notice}
            </div>
            {selected.is_partial_index && (
              <div className="cmp-permission-notice cmp-permission-notice--partial">
                {selected.partial_index_reason || "该资料的扫描页因 OCR 页数限制暂未全部识别，文本部分已正常解析。"}
              </div>
            )}
            <div className="cmp-summary-block">
              <div className="cmp-summary-title">
                <strong>内容摘要</strong>
                <span>基于 AI 提取</span>
              </div>
              <p>{showSummary && fullSummary ? fullSummary : getSummary(selected)}</p>
              {fullSummary.length > 180 && (
                <button type="button" className="cmp-link-btn" onClick={() => setShowSummary((v) => !v)}>
                  {showSummary ? "收起摘要" : "查看完整摘要"}
                </button>
              )}
            </div>
            <div className="cmp-detail-actions">
              <button className="cmp-btn cmp-btn--primary cmp-btn--block" type="button" onClick={() => onQuoteMaterial?.(selected)}>
                前往 AI 问答引用资料
              </button>
              <button className="cmp-btn cmp-btn--ghost cmp-btn--block" type="button" onClick={() => previewMaterial?.(selected)} disabled={!selected.can_preview || !selectedCanModify}>
                查看原文
              </button>
              <button className="cmp-btn cmp-btn--ghost cmp-btn--block" type="button" onClick={() => reparseMaterial?.(selected.id)} disabled={!selectedCanModify}>
                重新解析
              </button>
              {selected.can_download && selectedCanModify && (
                <button className="cmp-btn cmp-btn--ghost cmp-btn--block" type="button" onClick={() => downloadMaterial?.(selected)}>
                  下载原文
                </button>
              )}
            </div>
          </>
        )}
      </aside>

      {showKnowledgeModal && createPortal(
        <div className="kam-overlay" onClick={(event) => { if (event.target === event.currentTarget) closeKnowledgeModal(); }}>
          <div className="kam-modal">
            <button className="kam-close" type="button" onClick={closeKnowledgeModal} aria-label="关闭">×</button>
            <div className="kam-body">
              <h2 className="kam-title">从资料生成知识点</h2>

              {!analyzeResult && !analyzeLoading && (
                <>
                  <p className="kam-step-label">选择要分析的当前科目资料</p>
                  {currentItems.length === 0 ? (
                    <div className="kam-empty">
                      <p>当前科目暂无资料，请先上传课程资料。</p>
                      <button className="cmp-btn cmp-btn--primary" type="button" onClick={() => { closeKnowledgeModal(); materialsFileInputRef.current?.click(); }}>
                        上传课程资料
                      </button>
                    </div>
                  ) : (
                    <div className="kam-material-list">
                      {currentItems.map((material) => {
                        const selectedItem = selectedMaterialIds.has(material.id);
                        return (
                          <button
                            key={material.id}
                            type="button"
                            className={`kam-material-item${selectedItem ? " kam-material-item--selected" : ""}`}
                            onClick={() => toggleMaterialSelect(material.id)}
                          >
                            <span className="kam-material-check">{selectedItem ? "✓" : ""}</span>
                            <span className="kam-material-info">
                              <strong>{filenameOf(material)}</strong>
                              <small>{getFileTypeLabel(material.file_type)} · {formatFileSize(material.file_size)} · {chunkCountOf(material)} 个片段</small>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {analyzeError && <div className="kam-error"><p>{analyzeError}</p></div>}
                  <div className="kam-footer">
                    <span>{selectedMaterialIds.size ? `已选择 ${selectedMaterialIds.size} 份资料` : "请至少选择一份资料"}</span>
                    <button className="cmp-btn cmp-btn--primary" type="button" onClick={handleAnalyzeKnowledge} disabled={selectedMaterialIds.size === 0}>
                      开始分析
                    </button>
                  </div>
                </>
              )}

              {analyzeLoading && (
                <div className="kam-loading">
                  <div className="cmp-loading-spinner" />
                  <p>正在分析资料结构...</p>
                </div>
              )}

              {analyzeResult && !analyzeLoading && (
                <>
                  {confirmResult ? (
                    <div className="kam-confirm-success">
                      <div className="kam-confirm-success-icon">✓</div>
                      <h3>知识点已写入当前科目</h3>
                      <p>新增模块 {confirmResult.created_modules || 0} 个，新增知识点 {confirmResult.created_points || 0} 个。</p>
                      <div className="kam-confirm-success-actions">
                        <button className="cmp-btn cmp-btn--ghost" type="button" onClick={closeKnowledgeModal}>关闭</button>
                        <button className="cmp-btn cmp-btn--primary" type="button" onClick={() => { closeKnowledgeModal(); setPage?.("knowledgeLearning"); }}>查看知识点</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="kam-result-header">
                        <span>知识点树预览</span>
                        <span>{(analyzeResult.knowledge_tree || []).length} 个模块</span>
                      </div>
                      <div className="kam-tree">
                        {(analyzeResult.knowledge_tree || []).map((module, index) => {
                          const open = expandedModules.has(index);
                          return (
                            <div key={`${module.title}-${index}`} className="kam-tree-module">
                              <button type="button" className="kam-tree-module-header" onClick={() => toggleModuleExpand(index)}>
                                <span className={`kam-tree-arrow${open ? " kam-tree-arrow--open" : ""}`}>›</span>
                                <span>
                                  <strong>{module.title}</strong>
                                  {module.description && <small>{module.description}</small>}
                                </span>
                                <em>{(module.children || []).length} 项</em>
                              </button>
                              {open && (
                                <div className="kam-tree-children">
                                  {(module.children || []).map((child, childIndex) => (
                                    <div key={`${child.title}-${childIndex}`} className="kam-tree-child">
                                      <strong>{child.title}</strong>
                                      {child.description && <small>{child.description}</small>}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      {confirmError && <div className="kam-error"><p>{confirmError}</p></div>}
                      <div className="kam-footer">
                        <span>确认后会写入：{course.course}</span>
                        <div className="kam-footer-actions">
                          <button className="cmp-btn cmp-btn--ghost" type="button" onClick={() => setAnalyzeResult(null)}>返回重选</button>
                          <button className="cmp-btn cmp-btn--primary" type="button" onClick={handleConfirmKnowledgeTree} disabled={confirmLoading}>
                            {confirmLoading ? "写入中..." : "确认写入知识点"}
                          </button>
                        </div>
                      </div>
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
