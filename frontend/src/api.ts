import type { ScanRequestBody, ScanResult, ScanListItem } from "./types";

// Set VITE_API_BASE_URL in frontend/.env if the backend runs somewhere
// other than http://localhost:8000 (see .env.example).
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch {
    throw new ApiError(0, "Could not reach the Nukkad backend. Is it running on " + BASE_URL + "?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* response wasn't JSON - keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export function getHealth() {
  return request<{ status: string; serpapi_configured: boolean; gemini_configured: boolean }>("/api/health");
}

export function getBudgetPresets() {
  return request<{ presets: { preset: string; max_credits: number }[]; daily_cap: number }>("/api/budget/presets");
}

export function geocodeTown(town_name: string) {
  return request<{ lat: number; lng: number; cache_hit: boolean }>("/api/geocode", {
    method: "POST",
    body: JSON.stringify({ town_name }),
  });
}

export function createScan(body: ScanRequestBody) {
  return request<ScanResult>("/api/scans", { method: "POST", body: JSON.stringify(body) });
}

export function getScan(scanId: string) {
  return request<ScanResult>(`/api/scans/${scanId}`);
}

export function listScans() {
  return request<{ scans: ScanListItem[] }>("/api/scans");
}

export function exportScanUrl(scanId: string) {
  return `${BASE_URL}/api/scans/${scanId}/export?format=md`;
}

export function saveGap(scan_id: string, gap_id: string, note: string) {
  return request<{ saved: boolean }>("/api/saved", {
    method: "POST",
    body: JSON.stringify({ scan_id, gap_id, note }),
  });
}
