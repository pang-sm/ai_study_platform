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
  if (!open) return null;

  const searchQueryNorm = (searchQuery || "").trim().toLowerCase();
  const filtered = searchQueryNorm
    ? materials.filter((m) =>
        (m.original_filename || "").toLowerCase().includes(searchQueryNorm)
      )
    : materials;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-card library-ref-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3>引用当前课程资料</h3>
          <button
            className="modal-close"
            onClick={onClose}
            title="关闭"
          >
            &times;
          </button>
        </div>
        <p className="muted-text" style={{ marginBottom: 12 }}>
          选择资料库中的文件，作为本轮提问的强相关参考资料。
        </p>

        <input
          className="field"
          placeholder="在当前课程资料中搜索..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />

        <div className="library-ref-list">
          {loading ? (
            <div className="empty-inline">资料加载中...</div>
          ) : materials.length === 0 ? (
            <div className="empty-inline">
              <p>当前课程还没有可引用资料。</p>
              <p className="muted-text">
                请先在资料库上传资料，或在当前对话中上传新文件。
              </p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="empty-inline">没有匹配的资料。</div>
          ) : (
            filtered.map((material) => {
              const canRef = canReferenceMaterial(material);
              const reason = canRef ? "" : getUnreferenceableReason(material);
              const selected = selectedMaterials.some(
                (item) => item.id === material.id
              );
              return (
                <div
                  key={material.id}
                  className={`library-ref-item ${!canRef ? "library-ref-item--disabled" : ""} ${selected ? "library-ref-item--selected" : ""}`}
                  onClick={() => canRef && onToggleMaterial(material)}
                >
                  <div className="library-ref-item-check">
                    {selected && <span className="library-ref-check-mark">&#10003;</span>}
                  </div>
                  <div className="library-ref-item-info">
                    <div className="library-ref-item-name">
                      {material.original_filename}
                    </div>
                    <div className="library-ref-item-meta">
                      <span>{getFileTypeLabel(material.file_type)}</span>
                      <span>{formatFileSize(material.file_size)}</span>
                      <span>{getParseStatusLabel(material.parse_status)}</span>
                      <span>{Number(material.chunk_count || 0)} 个知识片段</span>
                      {!canRef && (
                        <span className="library-ref-item-reason">{reason}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="modal-actions">
          <button
            className="ghost-button compact"
            onClick={onClose}
          >
            取消
          </button>
          <button
            className="primary-button compact"
            onClick={onClose}
          >
            确认引用
          </button>
        </div>
      </div>
    </div>
  );
}
