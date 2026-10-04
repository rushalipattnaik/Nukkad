import { useState } from "react";
import type { EvidenceItem } from "../types";

const ENGINE_LABEL: Record<string, string> = {
  google_maps: "Google Maps",
  google_maps_reviews: "Google Maps Reviews",
  google_trends: "Google Trends",
  google_autocomplete: "Google Autocomplete",
  google_news: "Google News",
  nukkad_compute: "Computed by Nukkad",
};

function SourceModal({ item, onClose }: { item: EvidenceItem; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl max-w-md w-full p-5 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-slate-400 font-medium">
              {ENGINE_LABEL[item.engine] || item.engine}
            </div>
            <h3 className="font-semibold text-slate-900 mt-0.5">{item.title || item.evidence_id}</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-lg leading-none">
            ×
          </button>
        </div>
        <div className="mt-3 text-sm text-slate-600">
          Retrieved {new Date(item.retrieved_at).toLocaleString()}
          {item.cache_hit && <span className="text-slate-400"> · served from cache</span>}
        </div>
        {item.category && <div className="text-sm text-slate-500 mt-1">Category: {item.category}</div>}
        <pre className="mt-3 text-xs bg-slate-50 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words">
          {JSON.stringify(item.data, null, 2)}
        </pre>
        {item.source_ref && (
          <a
            href={item.source_ref}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block text-sm text-blue-600 hover:underline"
          >
            Open original source ↗
          </a>
        )}
        {item.derived_from.length > 0 && (
          <div className="mt-3 text-xs text-slate-400">
            Derived from {item.derived_from.length} underlying evidence item(s).
          </div>
        )}
      </div>
    </div>
  );
}

export default function EvidenceChips({
  evidenceIds,
  evidence,
}: {
  evidenceIds: string[];
  evidence: Record<string, EvidenceItem>;
}) {
  const [open, setOpen] = useState<EvidenceItem | null>(null);
  return (
    <span className="inline-flex flex-wrap gap-1 ml-1 align-middle">
      {evidenceIds.map((id, i) => {
        const item = evidence[id];
        if (!item) return null;
        return (
          <button
            key={id}
            onClick={() => setOpen(item)}
            title={item.title}
            className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 hover:bg-slate-800 hover:text-white transition"
          >
            E{i + 1}
          </button>
        );
      })}
      {open && <SourceModal item={open} onClose={() => setOpen(null)} />}
    </span>
  );
}
