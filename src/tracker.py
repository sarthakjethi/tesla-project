"""
tracker.py — time-travel engine.

Core API:
    snapshot = get_snapshot("2024-09-01", loader_data)
    comparison = get_comparison("2024-07-01", "2025-04-01", loader_data)

Returns rich dicts describing program state on a date or across a window.
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


# ---------------------------------------------------------------------------
# Comparison function
# ---------------------------------------------------------------------------

def get_comparison(date1_str: str, date2_str: str, data: dict) -> dict:
    """
    Return a comparison dict describing what changed between two dates.

    Comparison structure:
    {
      "date1_str":           str,
      "date2_str":           str,
      "days":                int,

      "released_in_window":  [ {**feature, "prev_status": str}, ... ],
      "versions_in_window":  [ release_row, ... ],

      "fsd_at_start":        str | None,
      "fsd_at_end":          str | None,

      "group_counts":        { group_id: int },      # features released in window
      "transitions":         { prev_status: int },   # how they got to released
      "eng_counts":          { engineer_id: int },   # features shipped per eng

      "window_fpm":          float,   # features per month in window
      "overall_fpm":         float,   # features per month overall (to date2)

      "risks":               [...],
      "g_names":             { group_id: str },
      "eng_map":             { engineer_id: dict },
    }
    """
    snap1 = get_snapshot(date1_str, data)
    snap2 = get_snapshot(date2_str, data)

    dt1 = datetime.strptime(date1_str, "%Y-%m-%d")
    dt2 = datetime.strptime(date2_str, "%Y-%m-%d")
    days_in_window = (dt2 - dt1).days

    _shipped = {"released", "release_complete"}

    # Status of every feature at date1 (keyed by feature_id)
    snap1_status = {f["feature_id"]: f["snap_status"] for f in snap1["features"]}

    # Features that crossed into shipped status during the window
    released_in_window = []
    for f in snap2["features"]:
        if f["snap_status"] in _shipped:
            prev = snap1_status.get(f["feature_id"], "planned")
            if prev not in _shipped:
                released_in_window.append({**f, "prev_status": prev})

    # Versions that shipped during the window
    snap1_ver_set = {r["version"] for r in snap1["released_versions"]}
    versions_in_window = [
        r for r in snap2["released_versions"]
        if r["version"] not in snap1_ver_set
    ]

    # Most recent FSD version at each boundary
    def _latest_fsd(released_vers: list) -> str | None:
        fsd = None
        for r in released_vers:
            if r.get("fsd_version"):
                fsd = r["fsd_version"]
        return fsd

    fsd_at_start = _latest_fsd(snap1["released_versions"])
    fsd_at_end   = _latest_fsd(snap2["released_versions"])

    # Group / transition / engineer breakdowns for window features
    group_counts: dict[int, int] = defaultdict(int)
    transitions:  dict[str, int] = defaultdict(int)
    eng_counts:   dict[str, int] = defaultdict(int)

    for f in released_in_window:
        group_counts[f["group_id"]] += 1
        transitions[f["prev_status"]] += 1
        eng_counts[f["engineer_id"]] += 1

    # Velocity comparison
    months_in_window = days_in_window / 30.44
    window_fpm = len(released_in_window) / months_in_window if months_in_window > 0 else 0.0

    total_released_date2 = snap2["velocity"]["features_released"]
    all_release_dates = [r["_release_dt"] for r in data["releases"] if r.get("_release_dt")]
    if all_release_dates and total_released_date2:
        first_dt = min(all_release_dates)
        overall_months = (dt2 - first_dt).days / 30.44
        overall_fpm = total_released_date2 / overall_months if overall_months > 0 else 0.0
    else:
        overall_fpm = 0.0

    return {
        "date1_str":          date1_str,
        "date2_str":          date2_str,
        "days":               days_in_window,
        "released_in_window": released_in_window,
        "versions_in_window": versions_in_window,
        "fsd_at_start":       fsd_at_start,
        "fsd_at_end":         fsd_at_end,
        "group_counts":       dict(group_counts),
        "transitions":        dict(transitions),
        "eng_counts":         dict(eng_counts),
        "window_fpm":         window_fpm,
        "overall_fpm":        overall_fpm,
        "risks":              data["risks"],
        "g_names":            snap2["g_names"],
        "eng_map":            snap2["eng_map"],
    }
