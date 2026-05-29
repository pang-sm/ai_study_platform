import { useEffect, useCallback } from "react";
import "./MaterialPickerModal.css";

function FileIcon({ fileType }) {
  const t = (fileType || "").toLowerCase();
  if (t === "pdf") {
    return (
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
        <rect x="4" y="2" width="24" height="28" rx="3" fill="#fef2f2" stroke="#fca5a5" strokeWidth="1.2" />
        <text x="16" y="22" textAnchor="middle" fontSize="10" fontWeight="700" fill="#ef4444" fontFamily="system-ui, sans-serif">PDF</text>
      </svg>
    );
  }
  if (t === "docx" || t === "doc" || t === "pptx" || t === "ppt") {
    return (
      <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
        <rect x="4" y="2" width="24" height="28" rx="3" fill="#eff6ff" stroke="#93c5fd" strokeWidth="1.2" />
        <text x="16" y="22" textAnchor="middle" fontSize="9" fontWeight="700" fill="#2563eb" fontFamily="system-ui, sans-serif">{t.toUpperCase()}</text>
      </svg>
    );
  }
  return (
    <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
      <rect x="4" y="2" width="24" height="28" rx="3" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1.2" />
      <path d="M12 12h8M12 17h6M12 22h8" stroke="#94a3b8" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export default function MaterialPickerModal({
  open = false,
  onClose = () => {},
  subjectLabel = "",
  materials = [],
  loading = false,
  searchQuery = "",
  onSearchChange = () => {},
  selectedMaterials = [],
  onToggleMaterial = () => {},
  canReferenceMaterial = () => true,
  getUnreferenceableReason = () => "",
  getFileTypeLabel = (v) => v,
  formatFileSize = (v) => v,
  getParseStatusLabel = (v) => v,
}) {
  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Escape") onClose();
    },
    [onClose]
  );

  useEffect(() => {
    if (!open) return;
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, handleKeyDown]);

  if (!open) return null;

  const searchQueryNorm = (searchQuery || "").trim().toLowerCase();
  const filtered = searchQueryNorm
    ? materials.filter((m) =>
        (m.original_filename || "").toLowerCase().includes(searchQueryNorm)
      )
    : materials;

  const selectedCount = selectedMaterials.length;

  const handleClearSelection = () => {
    selectedMaterials.forEach((m) => onToggleMaterial(m));
  };

  return (
    <div className="material-picker-overlay">
      <div
        className="material-picker-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="material-picker-header">
          <div className="material-picker-header-text">
            <h2 className="material-picker-title">引用当前课程资料</h2>
            <p className="material-picker-subtitle">
              从资料库中选择文件，作为本轮提问的强相关参考资料。
            </p>
          </div>
          <button
            className="material-picker-close"
            onClick={onClose}
            title="关闭"
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* ── Search ── */}
        <div className="material-picker-search-wrap">
          <span className="material-picker-search-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            className="material-picker-search"
            type="text"
            placeholder="搜索资料名称、章节或关键词"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </div>

        {/* ── List ── */}
        <div className="material-picker-list">
          {loading ? (
            <div className="material-picker-empty">
              <div className="material-picker-empty-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <p>资料加载中...</p>
            </div>
          ) : materials.length === 0 ? (
            <div className="material-picker-empty">
              <div className="material-picker-empty-icon">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
                  <polyline points="13 2 13 9 20 9" />
                </svg>
              </div>
              <p className="material-picker-empty-title">暂无课程资料</p>
              <p className="material-picker-empty-hint">请先在资料库上传资料，或在当前对话中上传新文件。</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="material-picker-empty">
              <p>没有匹配的资料。</p>
            </div>
          ) : (
            filtered.map((material) => {
              const canRef = canReferenceMaterial(material);
              const reason = canRef ? "" : getUnreferenceableReason(material);
              const selected = selectedMaterials.some(
                (item) => item.id === material.id
              );
              const chunkCount = Number(material.chunk_count || 0);

              return (
                <div
                  key={material.id}
                  className={`material-picker-item${!canRef ? " material-picker-item--disabled" : ""}${selected ? " material-picker-item--selected" : ""}`}
                  onClick={() => canRef && onToggleMaterial(material)}
                >
                  <div className={`material-picker-item-check${selected ? " material-picker-item-check--on" : ""}`}>
                    {selected && (
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>

                  <div className="material-picker-item-icon">
                    <FileIcon fileType={material.file_type} />
                  </div>

                  <div className="material-picker-item-body">
                    <div className="material-picker-item-name" title={material.original_filename}>
                      {material.original_filename}
                    </div>
                    <div className="material-picker-item-meta">
                      <span className="material-picker-item-type">{getFileTypeLabel(material.file_type)}</span>
                      <span className="material-picker-item-dot">·</span>
                      <span>{formatFileSize(material.file_size)}</span>
                      <span className="material-picker-item-dot">·</span>
                      <span>{getParseStatusLabel(material.parse_status)}</span>
                      {chunkCount > 0 && (
                        <>
                          <span className="material-picker-item-dot">·</span>
                          <span className="material-picker-item-chunks">{chunkCount} 个知识片段</span>
                        </>
                      )}
                      {!canRef && (
                        <span className="material-picker-item-reason">{reason}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* ── Footer ── */}
        <div className="material-picker-footer">
          <div className="material-picker-footer-left">
            <span className="material-picker-footer-count">
              {selectedCount > 0 ? `已选择 ${selectedCount} 项` : "未选择资料"}
            </span>
            {selectedCount > 0 && (
              <button
                className="material-picker-clear"
                type="button"
                onClick={handleClearSelection}
              >
                清空
              </button>
            )}
          </div>
          <div className="material-picker-footer-right">
            <button
              className="material-picker-btn material-picker-btn--cancel"
              type="button"
              onClick={onClose}
            >
              取消
            </button>
            <button
              className={`material-picker-btn material-picker-btn--confirm${selectedCount === 0 ? " material-picker-btn--disabled" : ""}`}
              type="button"
              disabled={selectedCount === 0}
              onClick={onClose}
            >
              确认引用
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
