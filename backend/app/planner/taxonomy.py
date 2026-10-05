"""
Hand-picked business categories for small Indian towns, each with a
need-window (used by the service-window gap) and a seed phrase for the
Autocomplete need-signal search. Kept short on purpose - a generic
category list would pull in a lot of categories that don't apply to a
small town and burn through the credit budget for no benefit.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDef:
    key: str
    maps_query: str
    label: str
    need_window: str  # human label, e.g. "after 9 PM"
    need_hours: tuple[int, int]  # (start_hour, end_hour), 24h clock, may wrap past midnight
    need_days: tuple[str, ...] = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    autocomplete_seed: str = ""


DEFAULT_TAXONOMY: list[CategoryDef] = [
    CategoryDef("medical_store", "medical store", "Medical store / pharmacy", "after 9 PM", (21, 6)),
    CategoryDef("dentist", "dentist", "Dentist", "weekends", (9, 20), need_days=("saturday", "sunday")),
    CategoryDef("gym", "gym", "Gym / fitness centre", "early morning", (5, 8)),
    CategoryDef("diagnostic_lab", "diagnostic lab", "Diagnostic lab", "weekday mornings", (7, 10)),
    CategoryDef("coaching_centre", "coaching classes", "Coaching / tuition centre", "evenings", (17, 21)),
    CategoryDef("salon", "salon", "Salon / barber", "evenings", (17, 21)),
    CategoryDef("tailor", "tailor", "Tailor", "weekday evenings", (18, 20)),
    CategoryDef("laundry", "laundry", "Laundry / dry cleaner", "any time", (0, 23)),
    CategoryDef("cafe", "cafe", "Cafe", "evenings", (18, 22)),
    CategoryDef("bakery", "bakery", "Bakery", "early morning", (6, 9)),
    CategoryDef("hardware_store", "hardware store", "Hardware store", "weekday", (9, 19)),
    CategoryDef("ev_charging", "ev charging station", "EV charging station", "any time", (0, 23)),
    CategoryDef("cold_storage", "cold storage", "Cold storage", "weekday", (9, 18)),
    CategoryDef("vet_clinic", "veterinary clinic", "Veterinary clinic", "weekends", (9, 18), need_days=("saturday", "sunday")),
    CategoryDef("stationery_shop", "stationery shop", "Stationery / photocopy shop", "evenings", (17, 20)),
]

BY_KEY: dict[str, CategoryDef] = {c.key: c for c in DEFAULT_TAXONOMY}


def resolve_categories(requested: list[str] | None) -> list[CategoryDef]:
    if not requested:
        return list(DEFAULT_TAXONOMY)
    out = []
    for name in requested:
        key = name.strip().lower().replace(" ", "_").replace("/", "_")
        if key in BY_KEY:
            out.append(BY_KEY[key])
        else:
            # Unknown category typed by the user - still usable, just with a
            # generic all-day need window (no service-window gap for it).
            out.append(CategoryDef(key=key, maps_query=name.strip(), label=name.strip(),
                                    need_window="any time", need_hours=(0, 23)))
    return out