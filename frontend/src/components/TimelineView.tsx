import { useEffect, useState } from "react";
import type { TimelineStep } from "../types";

const PHASE_LABELS: Record<string, string> = {
  SCOPING: "Scoping",
  SEARCH: "Search",
  "EVIDENCE EXTRACTION": "Evidence extraction",
  REASONING: "Reasoning",
  VERIFICATION: "Verification",
};

const STATUS_ICON: Record<TimelineStep["status"], string> = {
  ok: "●",
  empty: "○",
  error: "!",
  budget_exceeded: "⛔",
};

const STATUS_COLOR: Record<TimelineStep["status"], string> = {
  ok: "text-emerald-600",
  empty: "text-slate-400",
  error: "text-red-500",
  budget_exceeded: "text-amber-500",
};

/**
 * `animate=true` reveals steps one at a time on the loading screen, so the
 * investigation feels live even though the backend already has the full
 * result (the API call isn't streamed - see orchestrator.py).
 */
export default function TimelineView({
  steps,
  animate = false,
  onDone,
}: {
  steps: TimelineStep[];
  animate?: boolean;
  onDone?: () => void;
}) {
  const [visibleCount, setVisibleCount] = useState(animate ? 0 : steps.length);

  useEffect(() => {
    if (!animate) {
      setVisibleCount(steps.length);
      return;
    }
    setVisibleCount(0);
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      setVisibleCount(i);
      if (i >= steps.length) {
        clearInterval(interval);
        onDone?.();
      }
    }, 220);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [animate, steps.length]);

  const visible = steps.slice(0, visibleCount);
  let lastPhase = "";

  return (
    <div className="space-y-1">
      {visible.map((step) => {
        const showPhaseHeader = step.phase !== lastPhase;
        lastPhase = step.phase;
        return (
          <div key={step.seq}>
            {showPhaseHeader && (
              <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 mt-3 mb-1 first:mt-0">
                {PHASE_LABELS[step.phase] || step.phase}
              </div>
            )}
            <div className="flex items-start gap-2 text-sm py-1">
              <span className={`mt-0.5 ${STATUS_COLOR[step.status]}`}>{STATUS_ICON[step.status]}</span>
              <div className="flex-1 min-w-0">
                <div className="text-slate-800">{step.label}</div>
                {step.result_count != null && (
                  <div className="text-xs text-slate-400">{step.result_count} result(s)</div>
                )}
                {step.detail && step.status !== "ok" && (
                  <div className="text-xs text-slate-400 truncate">{step.detail}</div>
                )}
              </div>
            </div>
          </div>
        );
      })}
      {animate && visibleCount < steps.length && (
        <div className="text-sm text-slate-400 italic pt-1">Investigating…</div>
      )}
    </div>
  );
}
