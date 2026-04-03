"""
tracker.py — time-travel engine.

Core API:
    snapshot = get_snapshot("2024-09-01", loader_data)

Returns a rich dict describing the state of the entire program on that date.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from loader import group_name_map, subgroup_name_map, engineer_map


# ---------------------------------------------------------------------------
# Status computation
# ---------------------------------------------------------------------------

def _status_on(feature: dict, snap: datetime) -> str:
    """
    Compute a feature's lifecycle status on a given snapshot date.

    Timeline per feature:
        dev_start  ──► in_development
        feature_complete  ──► feature_complete
        release_complete  ──► release_complete  (within 14 days)
        release_complete + 14d  ──► released
        before dev_start  ──► planned
    """
    ds = feature.get("_dev_start_dt")
    fc = feature.get("_feature_complete_dt")
    rc = feature.get("_release_complete_dt")

    if rc and snap >= rc + timedelta(days=14):
        return "released"
    if rc and snap >= rc:
        return "release_complete"
    if fc and snap >= fc:
        return "feature_complete"
    if ds and snap >= ds:
        return "in_development"
    return "planned"


# ---------------------------------------------------------------------------
# Main snapshot function
# ---------------------------------------------------------------------------

def get_snapshot(date_str: str, data: dict) -> dict:
    """
    Return the complete program state on date_str (YYYY-MM-DD).

    Snapshot structure:
    {
      "date":          datetime,
      "date_str":      "2024-09-01",

      "features":      [ {**original_feature, "snap_status": str}, ... ],

      "status_counts": {"planned": N, "in_development": N, ...},
      "group_counts":  {group_id: {"total": N, status: N, ...}, ...},

      "active_features":    [...],   # in_development or feature_complete
      "active_engineers":   { engineer_id: [features], ... },

      "released_versions":  [release_row, ...],   # released before snap
      "active_versions":    [release_row, ...],   # in-flight on snap date
      "upcoming_versions":  [release_row, ...],   # not yet released

      "velocity": {
          "versions_released":  N,
          "features_released":  N,
          "avg_features_per_release": float,
          "avg_cycle_days":     float,
      },

      "risks":    [...],   # all risks (static)
      "groups":   [...],
      "subgroups":[...],
      "engineers":[...],
    }
    """
    snap = datetime.strptime(date_str, "%Y-%m-%d")

    g_names  = group_name_map(data)
    sg_names = subgroup_name_map(data)
    eng_map  = engineer_map(data)

    # ── per-feature snapshot ─────────────────────────────────────────────────
    enriched_features = []
    status_counts     = defaultdict(int)
    group_counts      = defaultdict(lambda: defaultdict(int))

    for f in data["features"]:
        status = _status_on(f, snap)
        row = {**f, "snap_status": status}
        enriched_features.append(row)
        status_counts[status] += 1
        group_counts[f["group_id"]]["total"] += 1
        group_counts[f["group_id"]][status]  += 1

    # ── active work (in_development + feature_complete) ──────────────────────
    active_features = [
        f for f in enriched_features
        if f["snap_status"] in ("in_development", "feature_complete")
    ]

    active_engineers: dict[str, list] = defaultdict(list)
    for f in active_features:
        active_engineers[f["engineer_id"]].append(f)

    # ── release timeline ─────────────────────────────────────────────────────
    released_versions  = []
    active_versions    = []
    upcoming_versions  = []

    for rel in data["releases"]:
        rdt = rel.get("_release_dt")
        if rdt is None:
            upcoming_versions.append(rel)
            continue
        if rdt <= snap:
            released_versions.append(rel)
        else:
            # Check if any features for this version are in active work on snap
            ver_active = any(
                f["version"] == rel["version"] and
                f["snap_status"] in ("in_development", "feature_complete")
                for f in enriched_features
            )
            if ver_active:
                active_versions.append(rel)
            else:
                upcoming_versions.append(rel)

    # ── velocity metrics (over released versions) ────────────────────────────
    _shipped = {"released", "release_complete"}
    released_feature_rows = [
        f for f in enriched_features if f["snap_status"] in _shipped
    ]
    cycle_days = []
    for f in released_feature_rows:
        ds = f.get("_dev_start_dt")
        rc = f.get("_release_complete_dt")
        if ds and rc:
            cycle_days.append((rc - ds).days)

    n_rel_versions = len(released_versions)
    velocity = {
        "versions_released":       n_rel_versions,
        "features_released":       len(released_feature_rows),
        "avg_features_per_release": (
            round(len(released_feature_rows) / n_rel_versions, 1)
            if n_rel_versions else 0.0
        ),
        "avg_cycle_days": (
            round(sum(cycle_days) / len(cycle_days), 1)
            if cycle_days else 0.0
        ),
    }

    return {
        "date":              snap,
        "date_str":          date_str,
        "features":          enriched_features,
        "status_counts":     dict(status_counts),
        "group_counts":      {k: dict(v) for k, v in group_counts.items()},
        "active_features":   active_features,
        "active_engineers":  dict(active_engineers),
        "released_versions": released_versions,
        "active_versions":   active_versions,
        "upcoming_versions": upcoming_versions,
        "velocity":          velocity,
        "risks":             data["risks"],
        "groups":            data["groups"],
        "subgroups":         data["subgroups"],
        "engineers":         data["engineers"],
        "g_names":           g_names,
        "sg_names":          sg_names,
        "eng_map":           eng_map,
    }
