import { useState } from "react";
import { resolveMediaUrl } from "../utils/mediaUrl.js";
import { getAvatarFallback } from "../utils/avatarFallback.js";
import "./ProgrammingProfileTrigger.css";

function AvatarVisual({ avatarSrc, fallback, name }) {
  const [avatarAvailable, setAvatarAvailable] = useState(Boolean(avatarSrc));

  if (avatarAvailable) return <img src={avatarSrc} alt="" onError={() => setAvatarAvailable(false)} />;
  return (
    <span className="programming-profile-trigger__fallback" style={{ background: fallback.background }} aria-hidden="true">
      {name.charAt(0).toUpperCase()}
    </span>
  );
}

export default function ProgrammingProfileTrigger({ user, apiBase = "/api", onClick, className = "" }) {
  const name = user?.nickname || user?.username || "同学";
  const avatarSrc = resolveMediaUrl(user?.avatar_url, apiBase);
  const fallback = getAvatarFallback(user?.avatar);

  return (
    <button
      type="button"
      className={`programming-profile-trigger ${className}`.trim()}
      aria-label="个人主页"
      onClick={onClick}
    >
      <AvatarVisual key={avatarSrc || "fallback"} avatarSrc={avatarSrc} fallback={fallback} name={name} />
      <strong title={name}>{name}</strong>
    </button>
  );
}
