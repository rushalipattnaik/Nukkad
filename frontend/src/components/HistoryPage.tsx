import { useEffect, useState } from "react";
import type { ScanListItem } from "../types";
import { clearHistory, listScans } from "../api";

export default function HistoryPage({ onOpen, onBack }: { onOpen: (scanId: string) => void; onBack: () => void }) {
  const [scans, setScans] = useState<ScanListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    listScans()
      .then((r) => setScans(r.scans))
      .finally(() => setLoading(false));
  }, []);

  async function handleClear() {
    setClearing(true);
    try {
      await clearHistory();
      setScans([]);
    } finally {
      setClearing(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto mt-10 px-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold text-slate-900">Scan history</h1>
        <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-800">
          ← New scan
        </button>
      </div>
      <p className="text-xs text-slate-400 mb-4">
        Stored on this machine's backend, not in your browser - incognito mode won't hide or clear it.
      </p>
      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {!loading && scans.length === 0 && <p className="text-sm text-slate-400">No scans yet.</p>}
      {!loading && scans.length > 0 && (
        <button
          onClick={handleClear}
          disabled={clearing}
          className="mb-4 text-xs px-3 py-1.5 rounded-full border border-slate-300 text-slate-600 hover:border-red-300 hover:text-red-600 disabled:opacity-50"
        >
          {clearing ? "Clearing…" : "Clear all history"}
        </button>
      )}
      <div className="space-y-2">
        {scans.map((s) => (
          <button
            key={s.scan_id}
            onClick={() => onOpen(s.scan_id)}
            className="w-full text-left bg-white border border-slate-200 rounded-lg p-3 hover:border-slate-400"
          >
            <div className="flex justify-between">
              <span className="font-medium text-slate-800">{s.town_name}</span>
              <span className={`text-xs ${s.status === "completed" ? "text-emerald-600" : "text-red-500"}`}>
                {s.status}
              </span>
            </div>
            <div className="text-xs text-slate-400 mt-0.5">
              {s.preset} · {new Date(s.created_at).toLocaleString()}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
