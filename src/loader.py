"""
loader.py — loads all 7 Phase-2 CSVs into memory.
Returns typed dicts with integer IDs and parsed dates where relevant.
"""

import csv
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")

_DATE_FMTS = [
    "%Y-%m-%d",        # ISO  — dev/complete dates
    "%B %d, %Y",       # "April 10, 2023"
    "%B %Y",           # "April 2023"  (rare)
]


def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _read(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_all() -> dict:
    """
    Load every data file and return a dict:
      {
        "releases":    [...],   # one row per version
        "features":    [...],   # one row per feature (enriched)
        "groups":      [...],
        "subgroups":   [...],
        "engineers":   [...],
        "assignments": [...],
        "risks":       [...],
      }
    Integer fields are cast to int; known date fields are parsed to datetime.
    """

    # ── raw loads ────────────────────────────────────────────────────────────
    releases    = _read("releases.csv")
    features    = _read("features.csv")
    groups      = _read("feature_groups.csv")
    subgroups   = _read("feature_subgroups.csv")
    engineers   = _read("engineers.csv")
    assignments = _read("assignments.csv")
    risks       = _read("risks.csv")

    # ── coerce releases ───────────────────────────────────────────────────────
    for r in releases:
        r["feature_count"] = int(r["feature_count"]) if r.get("feature_count") else 0
        r["_release_dt"]   = _parse_date(r.get("release_date", ""))

    # ── coerce features ───────────────────────────────────────────────────────
    for f in features:
        f["group_id"]    = int(f["group_id"])
        f["subgroup_id"] = int(f["subgroup_id"])
        f["_release_dt"]          = _parse_date(f.get("release_date", ""))
        f["_dev_start_dt"]        = _parse_date(f.get("dev_start_date", ""))
        f["_feature_complete_dt"] = _parse_date(f.get("feature_complete_date", ""))
        f["_release_complete_dt"] = _parse_date(f.get("release_complete_date", ""))

    # ── coerce groups / subgroups ─────────────────────────────────────────────
    for g in groups:
        g["group_id"] = int(g["group_id"])
    for sg in subgroups:
        sg["subgroup_id"] = int(sg["subgroup_id"])
        sg["group_id"]    = int(sg["group_id"])

    # ── coerce risks ─────────────────────────────────────────────────────────
    for r in risks:
        r["_raised_dt"]   = _parse_date(r.get("raised_date", ""))
        r["_resolved_dt"] = _parse_date(r.get("resolved_date", ""))

    # ── coerce assignments ────────────────────────────────────────────────────
    for a in assignments:
        a["group_id"]     = int(a["group_id"])
        a["progress_pct"] = int(a["progress_pct"])

    return {
        "releases":    releases,
        "features":    features,
        "groups":      groups,
        "subgroups":   subgroups,
        "engineers":   engineers,
        "assignments": assignments,
        "risks":       risks,
    }


# ── convenience look-up helpers ──────────────────────────────────────────────

def group_name_map(data: dict) -> dict[int, str]:
    return {g["group_id"]: g["group_name"] for g in data["groups"]}


def subgroup_name_map(data: dict) -> dict[int, str]:
    return {sg["subgroup_id"]: sg["subgroup_name"] for sg in data["subgroups"]}


def engineer_map(data: dict) -> dict[str, dict]:
    return {e["engineer_id"]: e for e in data["engineers"]}
