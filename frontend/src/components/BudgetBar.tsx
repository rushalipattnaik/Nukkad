import type { BudgetStatus } from "../types";

export default function BudgetBar({ budget }: { budget: BudgetStatus }) {
  const pct = budget.cap > 0 ? Math.min(100, (budget.counted_spent / budget.cap) * 100) : 0;
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="font-medium text-slate-700 whitespace-nowrap">SerpApi budget</span>
      <div className="w-40 h-2.5 rounded-full bg-slate-200 overflow-hidden">
        <div
          className={`h-full rounded-full ${pct > 90 ? "bg-red-500" : pct > 70 ? "bg-amber-500" : "bg-emerald-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-slate-600 whitespace-nowrap">
        {budget.counted_spent} / {budget.cap} searches
        {budget.cache_hits > 0 && <span className="text-slate-400"> · {budget.cache_hits} cached</span>}
      </span>
      {budget.refused_calls > 0 && (
        <span className="text-amber-600 text-xs">({budget.refused_calls} skipped - cap reached)</span>
      )}
    </div>
  );
}
