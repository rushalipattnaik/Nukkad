import { MapContainer, TileLayer, CircleMarker, Popup, Circle } from "react-leaflet";
import type { EvidenceItem, Gap } from "../types";

const GAP_COLOR: Record<string, string> = {
  ABSENCE: "#b45309",
  QUALITY: "#6d28d9",
  SERVICE_WINDOW: "#0e7490",
};
const NEUTRAL = "#64748b";

export default function MapView({
  centerLat,
  centerLng,
  radiusKm,
  evidence,
  gaps,
  selectedCategory,
}: {
  centerLat: number;
  centerLng: number;
  radiusKm: number;
  evidence: Record<string, EvidenceItem>;
  gaps: Gap[];
  selectedCategory: string | null;
}) {
  const gapTypeByCategory: Record<string, string> = {};
  for (const gap of gaps) {
    const existing = gapTypeByCategory[gap.category];
    if (!existing) gapTypeByCategory[gap.category] = gap.gap_type;
  }

  const places = Object.values(evidence).filter((e) => e.kind === "PLACE" && e.lat != null && e.lng != null);

  return (
    <MapContainer
      center={[centerLat, centerLng]}
      zoom={13}
      scrollWheelZoom
      style={{ height: "100%", width: "100%", minHeight: 320 }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle
        center={[centerLat, centerLng]}
        radius={radiusKm * 1000}
        pathOptions={{ color: "#94a3b8", fillOpacity: 0.03, weight: 1, dashArray: "4 4" }}
      />
      {places.map((p) => {
        const category = (p.category as string) || "";
        const dimmed = selectedCategory && category !== selectedCategory;
        const color = gapTypeByCategory[category] ? GAP_COLOR[gapTypeByCategory[category]] : NEUTRAL;
        return (
          <CircleMarker
            key={p.evidence_id}
            center={[p.lat as number, p.lng as number]}
            radius={dimmed ? 4 : 7}
            pathOptions={{ color, fillColor: color, fillOpacity: dimmed ? 0.25 : 0.85, weight: 1 }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{p.title}</div>
                <div className="text-slate-500">{category}</div>
                {typeof p.data.rating === "number" && (
                  <div>★ {p.data.rating} ({typeof p.data.reviews === "number" ? p.data.reviews : "?"} reviews)</div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
