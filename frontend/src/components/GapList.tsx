import type { Gap } from "../types";
import { GapTypeBadge, ConfidenceBadge } from "./Badges";

export default function GapList({
  gaps,
  selectedGapId,
  onSelect,
}: {
  gaps: Gap[];
  selectedGapId: string | null;
  onSelect: (gapId: string) => void;
}) {
  if (gaps.length === 0) {
    return (
      <div className="text-sm text-slate-500 p-4 border border-dashed border-slate-300 rounded-lg">
        No opportunity hypotheses met the evidence thresholds for this scan. Try a wider radius, or a town
        with more listed businesses.
      </div>
    );
  }

  const sorted = [...gaps].sort((a, b) => b.strength - a.strength);

  return (
    <div className="space-y-2">
      {sorted.map((gap) => (
        <button
          key={gap.gap_id}
          onClick={() => onSelect(gap.gap_id)}
          className={`w-full text-left p-3 rounded-lg border transition ${
            selectedGapId === gap.gap_id
              ? "border-slate-800 bg-slate-50 shadow-sm"
              : "border-slate-200 hover:border-slate-400 bg-white"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-slate-900 truncate">{gap.category}</span>
            <ConfidenceBadge level={gap.confidence} />
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <GapTypeBadge type={gap.gap_type} />
            {gap.conflicts.length > 0 && (
              <span className="text-xs text-amber-600 font-medium">⚠ Signals disagree</span>
            )}
          </div>
          {gap.why_we_think_this[0] && (
            <p className="mt-1.5 text-xs text-slate-500 line-clamp-2">{gap.why_we_think_this[0].text}</p>
          )}
        </button>
      ))}
    </div>
  );
}
