import { lazy, Suspense, useEffect, useState } from "react";
import useFirstTimeGuide from "../hooks/useFirstTimeGuide.js";

const FirstTimeGuide = lazy(() => import("./FirstTimeGuide.jsx"));

const ACTIVE_GUIDE_PREFIX = "first-time-guide-active:";

function readActiveGuide(serviceKey, steps) {
  try {
    const active = JSON.parse(sessionStorage.getItem(`${ACTIVE_GUIDE_PREFIX}${serviceKey}`) || "null");
    if (!active || !Number.isInteger(active.index) || active.index < 0 || active.index >= steps.length) return null;
    return active;
  } catch {
    return null;
  }
}

export default function FirstTimeGuideLauncher({ serviceKey, serviceLabel, steps, ready, replayToken, apiBase, onStepChange }) {
  const { open, complete, skip } = useFirstTimeGuide({ serviceKey, apiBase, ready, replayToken });
  const [activeGuide, setActiveGuide] = useState(() => readActiveGuide(serviceKey, steps));
  // When the guide resumes across a page navigation (home → dashboard), the
  // resumed step's panel/page must already match the highlighted target, so the
  // background never lags behind the guide copy.
  useEffect(() => {
    if (activeGuide && activeGuide.index > 0) {
      onStepChange?.(activeGuide.index, steps[activeGuide.index], "next");
    }
  }, [activeGuide?.index]);
  const isOpen = open || Boolean(activeGuide);
  if (!isOpen) return null;
  const persistActiveStep = (index) => {
    const next = { index };
    try { sessionStorage.setItem(`${ACTIVE_GUIDE_PREFIX}${serviceKey}`, JSON.stringify(next)); } catch { /* ignore */ }
    setActiveGuide(next);
  };
  const finish = async (handler) => {
    await handler();
    try { sessionStorage.removeItem(`${ACTIVE_GUIDE_PREFIX}${serviceKey}`); } catch { /* ignore */ }
    setActiveGuide(null);
  };
  return (
    <Suspense fallback={null}>
      <FirstTimeGuide
        serviceLabel={serviceLabel}
        steps={steps}
        initialIndex={activeGuide?.index || 0}
        onStepChange={(index, step, direction) => {
          persistActiveStep(index);
          onStepChange?.(index, step, direction);
        }}
        onComplete={() => finish(complete)}
        onSkip={() => finish(skip)}
      />
    </Suspense>
  );
}
