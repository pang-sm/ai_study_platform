import { useCallback, useEffect, useRef, useState } from "react";

/** Server-backed guide status. A completed guide never auto-opens again. */
export default function useFirstTimeGuide({ serviceKey, apiBase = "/api", ready, replayToken }) {
  const [guide, setGuide] = useState(null);
  const [open, setOpen] = useState(false);
  const autoAttemptedRef = useRef(false);

  const load = useCallback(async (signal) => {
    try {
      const response = await fetch(`${apiBase}/me/guides`, { signal });
      const data = await response.json().catch(() => ({}));
      if (response.ok) setGuide(data?.guides?.[serviceKey] || null);
    } catch (error) {
      if (error?.name !== "AbortError") setGuide(null);
    }
  }, [apiBase, serviceKey]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => { void load(controller.signal); }, 0);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [load]);

  useEffect(() => {
    if (!ready || autoAttemptedRef.current || !guide?.eligible || guide.completed) return;
    autoAttemptedRef.current = true;
    const timer = window.setTimeout(() => setOpen(true), 180);
    return () => window.clearTimeout(timer);
  }, [guide?.completed, guide?.eligible, ready]);

  useEffect(() => {
    if (!replayToken) return;
    const timer = window.setTimeout(() => setOpen(true), 0);
    return () => window.clearTimeout(timer);
  }, [replayToken]);

  const persist = useCallback(async (skipped) => {
    try {
      const response = await fetch(`${apiBase}/me/guides/${serviceKey}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ skipped }),
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data.guide) setGuide(data.guide);
    } finally {
      setOpen(false);
    }
  }, [apiBase, serviceKey]);

  return {
    open,
    close: () => setOpen(false),
    complete: () => persist(false),
    skip: () => persist(true),
  };
}
