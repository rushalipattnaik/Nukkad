import { useEffect, useState } from "react";
import type { ScanListItem } from "../types";
import { listScans } from "../api";

export default function HistoryPage({ onOpen, onBack }: { onOpen: (scanId: string) => void; onBack: () => void }) {
  const [scans, setScans] = useState<ScanListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listScans()
      .then((r) => setScans(r.scans))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-xl mx-auto mt-10 px-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold text-slate-900">Scan history</h1>
        <button onClick={onBack} className="text-sm text-slate-500 hover:text-slate-800">
          ← New scan
        </button>
      </div>
      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {!loading && scans.length === 0 && <p className="text-sm text-slate-400">No scans yet.</p>}
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
