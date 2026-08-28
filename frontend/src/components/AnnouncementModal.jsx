import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import "./AnnouncementModal.css";

function formatDate(value) {
  if (!value) return "";
  const text = String(value).trim();
  const hasTz = /Z$|[+-]\d{2}:?\d{2}$/.test(text);
  const normalized = /^\d{4}-\d{2}-\d{2}T/.test(text) && !hasTz ? `${text}Z` : text;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export default function AnnouncementModal({ announcements = [], onDismiss }) {
  const [index, setIndex] = useState(0);

  // Reset to the first announcement whenever a new batch arrives.
  useEffect(() => {
    setIndex(0);
  }, [announcements]);

  const total = announcements.length;
  if (total === 0) return null;

  const current = announcements[Math.min(index, total - 1)];
  if (!current) return null;

  const isLast = index >= total - 1;

  const advance = async () => {
    await onDismiss?.(current.id);
    if (isLast) {
      // The parent clears the list after the last one is read.
      return;
    }
    setIndex((value) => value + 1);
  };

  const goBack = () => {
    setIndex((value) => Math.max(0, value - 1));
  };

  return createPortal(
    <div className="annm-backdrop" role="presentation">
      <div className="annm-modal" role="dialog" aria-modal="true" aria-label="系统公告">
        <div className="annm-head">
          <span className="annm-badge">系统公告</span>
          {total > 1 && <span className="annm-counter">{index + 1} / {total}</span>}
          <button type="button" className="annm-close" onClick={advance} aria-label="关闭">×</button>
        </div>

        <div className="annm-body">
          <h2 className="annm-title">{current.title}</h2>
          <p className="annm-date">发布时间：{formatDate(current.created_at)}</p>
          <div className="annm-content">{current.content}</div>
        </div>

        <div className="annm-foot">
          {total > 1 && index > 0 && (
            <button type="button" className="annm-ghost" onClick={goBack}>上一条</button>
          )}
          <button type="button" className="annm-primary" onClick={advance}>
            {isLast ? "我知道了" : "下一条"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
