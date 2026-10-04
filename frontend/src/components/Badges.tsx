import type { ConfidenceLevel, GapType } from "../types";

const GAP_LABEL: Record<GapType, string> = {
  ABSENCE: "Absence gap",
  QUALITY: "Quality gap",
  SERVICE_WINDOW: "Service-window gap",
};

export function GapTypeBadge({ type }: { type: GapType }) {
  return (
    <span className={`gap-badge-${type} inline-block px-2 py-0.5 rounded-full text-xs font-medium text-white`}>
      {GAP_LABEL[type]}
    </span>
  );
}

const CONF_STYLE: Record<ConfidenceLevel, string> = {
  HIGH: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  LOW: "bg-slate-200 text-slate-600",
};

export function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${CONF_STYLE[level]}`}>
      {level} confidence
    </span>
  );
}
