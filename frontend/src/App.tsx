import { useState } from "react";
import type { ScanRequestBody, ScanResult } from "./types";
import { createScan, getScan, exportScanUrl, ApiError } from "./api";
import SetupForm from "./components/SetupForm";
import TimelineView from "./components/TimelineView";
import MapView from "./components/MapView";
import BudgetBar from "./components/BudgetBar";
import GapList from "./components/GapList";
import GapDetail from "./components/GapDetail";
import HistoryPage from "./components/HistoryPage";

type Screen = "setup" | "loading" | "dashboard" | "history";

export default function App() {
  const [screen, setScreen] = useState<Screen>("setup");
  const [result, setResult] = useState<ScanResult | null>(null);
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revealDone, setRevealDone] = useState(false);

  async function runScan(req: ScanRequestBody) {
    setError(null);
    setScreen("loading");
    setRevealDone(false);
    try {
      const res = await createScan(req);
      setResult(res);
      setSelectedGapId(res.gaps[0]?.gap_id ?? null);
      if (res.status !== "completed") {
        setError(res.warnings.join(" ") || "The scan could not complete.");
      }
    } catch (e) {
      const message = e instanceof ApiError ? e.message : "Something went wrong.";
      setError(message);
      setScreen("setup");
    }
  }

  async function openScan(scanId: string) {
    try {
      const res = await getScan(scanId);
      setResult(res);
      setSelectedGapId(res.gaps[0]?.gap_id ?? null);
      setRevealDone(true);
      setScreen("dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load that scan.");
    }
  }

  if (screen === "setup") {
    return (
      <div className="min-h-screen">
        <SetupForm onSubmit={runScan} />
        {error && <p className="text-center text-sm text-red-600 mt-4">{error}</p>}
        <div className="text-center mt-6">
          <button onClick={() => setScreen("history")} className="text-sm text-slate-400 hover:text-slate-700">
            View past scans →
          </button>
        </div>
      </div>
    );
  }

  if (screen === "history") {
    return <HistoryPage onOpen={openScan} onBack={() => setScreen("setup")} />;
  }

  if (screen === "loading" && result === null) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-pulse text-slate-400 text-sm">Scanning {`\u2026`}</div>
          <div className="mt-4 w-64 h-1.5 bg-slate-200 rounded-full overflow-hidden mx-auto">
            <div className="h-full w-1/2 bg-slate-800 animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  if (result && !revealDone) {
    // Replay the investigation timeline before revealing the full dashboard.
    return (
      <div className="max-w-md mx-auto mt-16 px-4">
        <h2 className="text-lg font-semibold text-slate-900 mb-3">Investigating {result.town_name}</h2>
        <div className="bg-white border border-slate-200 rounded-xl p-4 max-h-[60vh] overflow-y-auto">
          <TimelineView steps={result.timeline} animate onDone={() => setRevealDone(true)} />
        </div>
      </div>
    );
  }

  if (!result) return null;

  const selectedGap = result.gaps.find((g) => g.gap_id === selectedGapId) || null;

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-3 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <span className="font-bold text-slate-900">Nukkad</span>
          <span className="text-slate-400 ml-2">— {result.town_name} ({result.radius_km} km)</span>
        </div>
        <BudgetBar budget={result.budget} />
        <div className="flex gap-3 text-sm">
          <a href={exportScanUrl(result.scan_id)} className="text-slate-500 hover:text-slate-800">
            Export memo
          </a>
          <button onClick={() => setScreen("history")} className="text-slate-500 hover:text-slate-800">
            History
          </button>
          <button onClick={() => setScreen("setup")} className="text-slate-500 hover:text-slate-800">
            New scan
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-amber-50 border-b border-amber-200 text-amber-700 text-sm px-4 py-2">{error}</div>
      )}
      {result.warnings.length > 0 && !error && (
        <div className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs px-4 py-1.5">
          {result.warnings.length} data limitation(s) noted - see individual gaps for details.
        </div>
      )}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[280px_1fr_360px] gap-0 min-h-0">
        <aside className="border-r border-slate-200 bg-white p-4 overflow-y-auto max-h-[calc(100vh-57px)]">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
            Investigation timeline
          </div>
          <TimelineView steps={result.timeline} />
        </aside>

        <main className="p-4 min-h-[400px]">
          <MapView
            centerLat={result.center_lat}
            centerLng={result.center_lng}
            radiusKm={result.radius_km}
            evidence={result.evidence}
            gaps={result.gaps}
            selectedCategory={selectedGap?.category ?? null}
          />
          <div className="mt-4">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
              Opportunity hypotheses
            </div>
            <GapList gaps={result.gaps} selectedGapId={selectedGapId} onSelect={setSelectedGapId} />
          </div>
        </main>

        <aside className="border-l border-slate-200 bg-white p-4 overflow-y-auto max-h-[calc(100vh-57px)]">
          {selectedGap ? (
            <GapDetail gap={selectedGap} evidence={result.evidence} scanId={result.scan_id} />
          ) : (
            <p className="text-sm text-slate-400">Select an opportunity hypothesis to see the evidence behind it.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
