export const AVATAR_FALLBACKS = [
  { id: "avatar_1", label: "A1", background: "#2563eb" },
  { id: "avatar_2", label: "A2", background: "#059669" },
  { id: "avatar_3", label: "A3", background: "#7c3aed" },
  { id: "avatar_4", label: "A4", background: "#db2777" },
  { id: "avatar_5", label: "A5", background: "#ea580c" },
  { id: "avatar_6", label: "A6", background: "#0f766e" },
];

export function getAvatarFallback(avatarId) {
  return AVATAR_FALLBACKS.find((avatar) => avatar.id === avatarId) || AVATAR_FALLBACKS[0];
}
