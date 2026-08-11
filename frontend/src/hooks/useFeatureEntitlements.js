import { useCallback, useEffect, useState } from "react";

export const FEATURE_ENTITLEMENTS_UPDATED_EVENT = "membership-entitlements-updated";

export function notifyFeatureEntitlementsUpdated() {
  window.dispatchEvent(new Event(FEATURE_ENTITLEMENTS_UPDATED_EVENT));
}

export function getUpgradeDetail(payload) {
  const detail = payload?.detail;
  return detail && typeof detail === "object" && detail.code === "FEATURE_REQUIRES_UPGRADE"
    ? detail
    : null;
}

export default function useFeatureEntitlements(serviceKey, enabled = true) {
  const [state, setState] = useState({ loading: Boolean(enabled), currentPlan: "free", features: {}, error: "" });

  const refresh = useCallback(async () => {
    if (!enabled || !serviceKey) {
      setState({ loading: false, currentPlan: "free", features: {}, error: "" });
      return null;
    }
    setState((current) => ({ ...current, loading: true, error: "" }));
    try {
      const response = await fetch(`/api/membership/entitlements?service_key=${encodeURIComponent(serviceKey)}`, { credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "权益加载失败");
      const next = { loading: false, currentPlan: payload.current_plan || "free", features: payload.features || {}, error: "" };
      setState(next);
      return next;
    } catch (error) {
      setState((current) => ({ ...current, loading: false, error: error.message || "权益加载失败" }));
      return null;
    }
  }, [enabled, serviceKey]);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    window.addEventListener(FEATURE_ENTITLEMENTS_UPDATED_EVENT, refresh);
    return () => window.removeEventListener(FEATURE_ENTITLEMENTS_UPDATED_EVENT, refresh);
  }, [refresh]);

  return { ...state, refresh };
}
