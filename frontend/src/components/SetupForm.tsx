import { useEffect, useState } from "react";
import type { ScanPreset, ScanRequestBody } from "../types";
import { getBudgetPresets, getHealth } from "../api";

const EXAMPLES = ["Bhopal, Madhya Pradesh", "Indore, Madhya Pradesh"];

export default function SetupForm({ onSubmit }: { onSubmit: (req: ScanRequestBody) => void }) {
  const [town, setTown] = useState("");
  const [radius, setRadius] = useState(3);
  const [preset, setPreset] = useState<ScanPreset>("standard");
  const [presetCredits, setPresetCredits] = useState<Record<string, number>>({});
  const [health, setHealth] = useState<{ serpapi_configured: boolean; gemini_configured: boolean } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBudgetPresets()
      .then((r) => setPresetCredits(Object.fromEntries(r.presets.map((p) => [p.preset, p.max_credits]))))
      .catch(() => {});
    getHealth()
      .then(setHealth)
      .catch(() => setError("Could not reach the Nukkad backend. Make sure it is running on port 8000."));
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!town.trim()) {
      setError("Enter a town name.");
      return;
    }
    setError(null);
    onSubmit({ town_name: town.trim(), radius_km: radius, preset, mode: "live" });
  }

  return (
    <div className="max-w-xl mx-auto mt-10 px-4">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-slate-900">Nukkad</h1>
        <p className="text-slate-500 mt-2">Find what your town is searching for but can't find.</p>
        <div className="flex justify-center gap-6 mt-5 text-xs text-slate-400">
          <span>① Select town</span>
          <span>② Scan local market</span>
          <span>③ Discover gaps</span>
          <span>④ Inspect evidence</span>
        </div>
      </div>

      {health && !health.serpapi_configured && (
        <div className="mb-4 text-sm bg-amber-50 border border-amber-200 text-amber-700 rounded-lg p-3">
          <strong>SERPAPI_API_KEY is not set.</strong> Add it to backend/.env and restart the backend before
          running a scan.
        </div>
      )}
      {health && !health.gemini_configured && (
        <div className="mb-4 text-sm bg-slate-50 border border-slate-200 text-slate-600 rounded-lg p-3">
          Gemini is not configured - Nukkad will still work, using deterministic summaries instead of
          LLM-written narration. Add GEMINI_API_KEY and GEMINI_MODEL to backend/.env to enable it.
        </div>
      )}

      <form onSubmit={submit} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Town</label>
          <input
            value={town}
            onChange={(e) => setTown(e.target.value)}
            placeholder="e.g. Bhopal, Madhya Pradesh"
            className="w-full border border-slate-300 rounded-lg px-3 py-2"
          />
          <div className="flex gap-2 mt-2 flex-wrap">
            {EXAMPLES.map((ex) => (
              <button
                type="button"
                key={ex}
                onClick={() => setTown(ex)}
                className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600 hover:bg-slate-200"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Radius</label>
            <select
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="w-full border border-slate-300 rounded-lg px-3 py-2"
            >
              <option value={1}>1 km</option>
              <option value={3}>3 km</option>
              <option value={5}>5 km</option>
              <option value={10}>10 km</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Scan depth</label>
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value as ScanPreset)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2"
            >
              <option value="lite">Lite (~{presetCredits.lite ?? 40} searches)</option>
              <option value="standard">Standard (~{presetCredits.standard ?? 90} searches)</option>
              <option value="deep">Deep (~{presetCredits.deep ?? 150} searches)</option>
            </select>
          </div>
        </div>

        {error && <div className="text-sm text-red-600">{error}</div>}

        <button
          type="submit"
          className="w-full bg-slate-900 text-white rounded-lg py-2.5 font-medium hover:bg-slate-800 transition"
        >
          Scan local market
        </button>
      </form>
    </div>
  );
}