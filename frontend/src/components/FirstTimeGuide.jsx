import { useEffect, useLayoutEffect, useState } from "react";
import "./FirstTimeGuide.css";

function getTarget(selector) {
  if (!selector) return null;
  try {
    return document.querySelector(selector);
  } catch {
    return null;
  }
}

function getPlacement(rect) {
  const space = {
    top: rect.top,
    right: window.innerWidth - rect.right,
    bottom: window.innerHeight - rect.bottom,
    left: rect.left,
  };
  return Object.entries(space).sort((a, b) => b[1] - a[1])[0][0];
}

export default function FirstTimeGuide({ serviceLabel, steps, initialIndex = 0, onComplete, onSkip, onStepChange }) {
  const [index, setIndex] = useState(() => Math.min(Math.max(initialIndex, 0), Math.max(steps.length - 1, 0)));
  const [rect, setRect] = useState(null);
  const step = steps[index];
  const [target, setTarget] = useState(null);

  useLayoutEffect(() => {
    const updateTarget = () => setTarget(getTarget(step?.selector));
    const frame = window.requestAnimationFrame(updateTarget);
    const retry = window.setTimeout(updateTarget, 120);
    const observer = new MutationObserver(updateTarget);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-tour", "class"] });
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(retry);
      observer.disconnect();
    };
  }, [index, step?.selector]);

  useEffect(() => {
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = oldOverflow; };
  }, []);

  useLayoutEffect(() => {
    const update = () => setRect(target ? target.getBoundingClientRect() : null);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    const timer = window.setTimeout(update, target ? 260 : 0);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [index, target]);

  if (!step) return null;
  const move = (nextIndex) => {
    if (nextIndex < 0 || nextIndex >= steps.length) return;
    onStepChange?.(nextIndex, steps[nextIndex], nextIndex > index ? "next" : "previous");
    setIndex(nextIndex);
  };
  const placement = rect ? getPlacement(rect) : "bottom";
  const tooltipStyle = rect
    ? { "--guide-target-top": `${Math.max(12, rect.top)}px`, "--guide-target-left": `${Math.max(12, rect.left)}px`, "--guide-target-width": `${Math.max(1, rect.width)}px`, "--guide-target-height": `${Math.max(1, rect.height)}px` }
    : undefined;

  return (
    <div className="first-time-guide" role="dialog" aria-modal="true" aria-label={`${serviceLabel} 新手引导`}>
      <div className="first-time-guide__backdrop" />
      {rect && <div className="first-time-guide__spotlight" style={tooltipStyle} aria-hidden="true" />}
      <section className={`first-time-guide__card first-time-guide__card--${placement}${rect ? "" : " first-time-guide__card--center"}`} style={tooltipStyle}>
        <div className="first-time-guide__topline">
          <span>{serviceLabel} · 新手引导</span>
          <span>{index + 1} / {steps.length}</span>
        </div>
        <h2>{step.title}</h2>
        <p>{step.description}</p>
        {!target && <p className="first-time-guide__fallback">当前入口暂未显示，仍可继续查看下一项。</p>}
        <div className="first-time-guide__actions">
          <button type="button" className="first-time-guide__skip" onClick={onSkip}>跳过</button>
          <span className="first-time-guide__spacer" />
          {index > 0 && <button type="button" className="first-time-guide__secondary" onClick={() => move(index - 1)}>上一步</button>}
          {index < steps.length - 1 ? (
            <button type="button" className="first-time-guide__primary" onClick={() => move(index + 1)}>下一步</button>
          ) : (
            <button type="button" className="first-time-guide__primary" onClick={onComplete}>开始学习</button>
          )}
        </div>
      </section>
    </div>
  );
}
