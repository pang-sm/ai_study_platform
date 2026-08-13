import { lazy, Suspense } from "react";
import useFirstTimeGuide from "../hooks/useFirstTimeGuide.js";

const FirstTimeGuide = lazy(() => import("./FirstTimeGuide.jsx"));

export default function FirstTimeGuideLauncher({ serviceKey, serviceLabel, steps, ready, replayToken, apiBase }) {
  const { open, complete, skip } = useFirstTimeGuide({ serviceKey, apiBase, ready, replayToken });
  if (!open) return null;
  return (
    <Suspense fallback={null}>
      <FirstTimeGuide
        serviceLabel={serviceLabel}
        steps={steps}
        onComplete={complete}
        onSkip={skip}
        onClose={close}
      />
    </Suspense>
  );
}
