import { useState } from "react";
import { resolveMediaUrl } from "../utils/mediaUrl.js";

/**
 * Shared real-user avatar. Reuses `user.avatar_url` (the same field the
 * profile page serves). Falls back to the nickname's first character only when
 * there is no avatar URL or the image fails to load.
 */
export default function UserAvatar({ user, name = "", className = "", imgClassName = "" }) {
  const [failed, setFailed] = useState(false);
  const src = user?.avatar_url ? resolveMediaUrl(user.avatar_url) : "";
  if (src && !failed) {
    return (
      <img
        className={`${className} ${imgClassName}`.trim()}
        src={src}
        alt={name || "头像"}
        onError={() => setFailed(true)}
      />
    );
  }
  return <span className={className}>{(name || "").charAt(0)}</span>;
}
