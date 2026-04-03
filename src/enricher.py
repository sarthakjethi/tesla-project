"""
Tesla TPM Dashboard — Phase 2 Data Enricher
Reads features_raw.csv and produces:
  data/features.csv     — enriched feature records
  data/assignments.csv  — engineer-per-feature assignments with progress
"""

import csv
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)   # reproducible

DATA_DIR   = Path("data")
TODAY      = datetime(2026, 4, 2)

# ---------------------------------------------------------------------------
# Keyword taxonomy
# Each entry: (group_id, subgroup_id, [keywords])
# Evaluated top-to-bottom; first match wins.
# Keywords are matched case-insensitively against the feature name.
# ---------------------------------------------------------------------------

TAXONOMY = [
    # ── Autopilot ──────────────────────────────────────────────────────────
    # Neural Network  (most specific — FSD version strings)
    (1, 104, ["fsd beta", "fsd (supervised)", "fsd (beta)", "full self-driving",
              "fsd version", "fsd strikes", "fsd visualizations", "fsd guide",
              "fsd supervised", "neural", "end-to-end"]),
    # Parking & Summon
    (1, 103, ["summon", "autopark", "park assist", "vision park", "smart summon",
              "a.s.s.", "ass "]),
    # Lane Management
    (1, 102, ["lane departure", "lane change", "cancel lane", "autopilot",
              "single pull", "steer-by-wire", "go on green", "curve assist",
              "trail assist", "comfort drive mode", "comfort braking",
              "standard ride", "improved ride", "ride and handling",
              "removal of tacc"]),
    # Speed Control
    (1, 101, ["speed assist", "speed offset", "speed profile", "speed camera",
              "cruise control", "stopping mode", "average speed", "traffic-aware",
              "tacc"]),

    # ── Safety ─────────────────────────────────────────────────────────────
    # Collision Detection
    (2, 203, ["emergency braking", "blind spot", "forward collision",
              "rear cross", "faster hazard", "collision warning",
              "brake confirm", "tow limit", "automatic 911", "turn off 911",
              "frontal airbag", "ota recall", "over-the-air recall",
              "vehicle alarm"]),
    # Child & Pet Safety
    (2, 202, ["dog mode", "child left alone", "cabin sensing", "cabin overheat",
              "pet"]),
    # Driver Monitoring
    (2, 201, ["drowsiness", "attention warning", "cabin camera",
              "vision-based attention", "vision attention", "green dot",
              "orange dot", "monitoring is active", "sentry mode",
              "sentry video", "sentry light", "sentry recording",
              "preview of sentry", "new lock alert", "pin to drive"]),

    # ── Connectivity ───────────────────────────────────────────────────────
    # AI Assistant
    (6, 601, ["grok", "voice assistant", "voice recognition", "voice command",
              "handwriting", "dictate", "improved voice", "thai voice",
              "hebrew language", "language support", "new language",
              "keyboard language", "slovak", "pinyin"]),
    # App Integration
    (6, 602, ["apple watch", "bluetooth", "wifi", "wi-fi", "phone key",
              "phone call", "zoom meeting", "zoom ", "location sharing",
              "ultra-wideband", "wechat", "mobile access",
              "improved transition to cellular", "connectivity icon",
              "new bluetooth", "switch to bluetooth", "improved phone",
              "tesla app command", "app displays"]),

    # ── Navigation ─────────────────────────────────────────────────────────
    # Supercharger
    (4, 401, ["supercharger", "supercharging", "v4 supercharger",
              "destination charging", "third-party fast charger",
              "dc fast charging", "trailer-friendly supercharger"]),
    # Trip Planning
    (4, 402, ["trip planner", "trip planning", "set arrival energy",
              "arrival energy", "alternative trip", "arrival options",
              "schedule charge", "schedule preconditioning",
              "one-time charge limit", "daily charge limit",
              "save charge limit", "charge on solar", "preconditioning",
              "time until charging", "more efficient charging",
              "reminder to plug", "show next preconditioning",
              "more charging information"]),
    # Maps
    (4, 403, ["navigation", "nav improvement", "map", "satellite view",
              "points of interest", "favorites on map", "search along route",
              "search this area", "search menu", "hov lane", "toll road",
              "express lane", "avoid highway", "alternate route",
              "better route", "construction on", "danger zone",
              "automatic navigation", "predictive text for nav",
              "navigate to sub", "u-turn", "trip progress",
              "precipitation map", "weather at destination",
              "weather forecast", "traffic visualization"]),

    # ── Media ──────────────────────────────────────────────────────────────
    # Music Streaming
    (5, 501, ["spotify", "apple music", "tidal", "youtube music", "siriusxm",
              "tunein", "amazon music", "audible", "apple podcast",
              "radio favorite", "radio traffic", "liveone", "slacker",
              "equalizer", "audio balance", "audio setting",
              "favoriting song", "hide music", "explicit content",
              "volume indicator", "new media player", "bluetooth player"]),
    # Entertainment
    (5, 502, ["theater", "game", "beach buggy", "vampire survivor",
              "boomerang fu", "castle doombad", "mahjong", "spacex",
              "photobooth", "light show", "light sync", "rave cave",
              "tron mode", "santa mode", "paint shop", "rear screen",
              "full screen", "mango tv", "vohico", "arcade",
              "atari", "fart on sit", "multiplayer", "cybertruck colorizer",
              "ambient lighting easter"]),

    # ── Hardware ───────────────────────────────────────────────────────────
    # Lights
    (7, 701, ["headlight", "adaptive high beam", "turn signal", "ambient light",
              "light pulsing", "sentry mode light", "light sync",
              "new ambient light", "warmer display"]),
    # Suspension
    (7, 702, ["suspension", "air suspension", "ride height", "off-road",
              "locking differential", "terrain option", "baja mode",
              "towing", "trailer profile", "improved turning circle"]),
    # Cameras
    (7, 703, ["reverse camera", "side camera", "front camera", "live camera",
              "view cabin camera", "view all camera", "more camera",
              "improved camera", "camera update", "camera view",
              "camera visibility", "camera app", "camera clarity",
              "dashcam", "improved reverse", "improved front camera"]),

    # ── UI (catch broad display / settings items after specific checks) ─────
    # Dashcam Viewer
    (3, 301, ["dashcam viewer", "mobile app dashcam"]),
    # Visualizations
    (3, 302, ["visualization", "3d building", "unreal engine", "new map icon",
              "smoother visual", "steering angle", "parked visual",
              "driving visual", "vehicle visual", "charger visual",
              "improved visual", "new visual", "visual update"]),
    # Themes
    (3, 303, ["transparency effect", "card transparency", "warmer display",
              "status bar", "speedometer font", "larger speedometer",
              "speedometer", "text size", "display color", "seat heater icon",
              "climate icon", "connectivity icon", "charging icon",
              "wrap & license", "updated apps badge"]),
]

# Group/subgroup fallback for anything not matched above
DEFAULT_GROUP    = 3   # UI
DEFAULT_SUBGROUP = 302  # Visualizations

# ---------------------------------------------------------------------------
# Engineer assignments per group
# Each group maps to a list of engineer_ids; we round-robin per feature.
# ---------------------------------------------------------------------------

GROUP_ENGINEERS = {
    1: ["E01", "E02"],   # Autopilot → Alice, Bob
    2: ["E03", "E07"],   # Safety    → Priya, Maya
    3: ["E04"],          # UI        → James
    4: ["E05"],          # Nav       → Sara
    5: ["E04"],          # Media     → James (also owns UI)
    6: ["E06"],          # Connectivity → Liam
    7: ["E08"],          # Hardware  → Noah
}
_eng_counters = {g: 0 for g in GROUP_ENGINEERS}


def assign_engineer(group_id: int) -> str:
    pool = GROUP_ENGINEERS.get(group_id, ["E04"])
    idx  = _eng_counters[group_id] % len(pool)
    _eng_counters[group_id] += 1
    return pool[idx]


# ---------------------------------------------------------------------------
# Taxonomy lookup
# ---------------------------------------------------------------------------

def classify(feature_name: str) -> tuple[int, int]:
    """Return (group_id, subgroup_id) for a feature name."""
    name_lower = feature_name.lower()
    for group_id, subgroup_id, keywords in TAXONOMY:
        if any(kw in name_lower for kw in keywords):
            return group_id, subgroup_id
    return DEFAULT_GROUP, DEFAULT_SUBGROUP


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

_DATE_FMTS = ["%B %d, %Y", "%B %Y"]

def parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def fmt(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def lifecycle_status(release_dt: datetime | None) -> str:
    if release_dt is None:
        return "planned"
    delta = (TODAY - release_dt).days
    if delta >= 14:
        return "released"
    if delta >= 0:
        return "release_complete"
    if delta >= -7:
        return "feature_complete"
    return "in_development"


def progress_pct(status: str) -> int:
    return {
        "released":          100,
        "release_complete":  100,
        "feature_complete":   90,
        "in_development":    random.randint(30, 70),
        "planned":           random.randint(0,  15),
    }[status]


# ---------------------------------------------------------------------------
# Main enrichment logic
# ---------------------------------------------------------------------------

def enrich() -> None:
    raw_path = DATA_DIR / "features_raw.csv"
    out_path = DATA_DIR / "features.csv"
    asg_path = DATA_DIR / "assignments.csv"

    with raw_path.open(encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))

    features   = []
    assignments = []
    feature_id  = 1

    # Tracking for summary
    group_counts    = {}
    subgroup_counts = {}
    status_counts   = {}
    unmatched       = []

    for row in raw_rows:
        name         = row["feature_name"]
        release_date = parse_date(row["release_date"])
        group_id, subgroup_id = classify(name)

        # Track unmatched (fell through to default)
        if (group_id, subgroup_id) == (DEFAULT_GROUP, DEFAULT_SUBGROUP):
            unmatched.append(name)

        engineer_id = assign_engineer(group_id)
        status      = lifecycle_status(release_date)

        # Generate work dates relative to release date
        if release_date:
            dev_start        = release_date - timedelta(days=random.randint(42, 56))
            feature_complete = release_date - timedelta(days=random.randint(7, 14))
            release_complete = release_date
        else:
            dev_start = feature_complete = release_complete = None

        fid = f"F{feature_id:04d}"
        feature_id += 1

        features.append({
            "feature_id":            fid,
            "version":               row["version"],
            "release_date":          row["release_date"],
            "feature_name":          name,
            "category":              row["category"],
            "group_id":              group_id,
            "subgroup_id":           subgroup_id,
            "engineer_id":           engineer_id,
            "models":                row.get("models", ""),
            "hardware":              row.get("hardware", ""),
            "description":           row.get("description", ""),
            "dev_start_date":        fmt(dev_start),
            "feature_complete_date": fmt(feature_complete),
            "release_complete_date": fmt(release_complete),
            "lifecycle_status":      status,
        })

        pct = progress_pct(status)
        assignments.append({
            "assignment_id": f"A{feature_id - 1:04d}",
            "feature_id":    fid,
            "engineer_id":   engineer_id,
            "version":       row["version"],
            "feature_name":  name,
            "group_id":      group_id,
            "lifecycle_status": status,
            "progress_pct":  pct,
        })

        group_counts[group_id]       = group_counts.get(group_id, 0) + 1
        subgroup_counts[subgroup_id] = subgroup_counts.get(subgroup_id, 0) + 1
        status_counts[status]        = status_counts.get(status, 0) + 1

    # Write features.csv
    feat_fields = [
        "feature_id", "version", "release_date", "feature_name", "category",
        "group_id", "subgroup_id", "engineer_id", "models", "hardware",
        "description", "dev_start_date", "feature_complete_date",
        "release_complete_date", "lifecycle_status",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=feat_fields)
        w.writeheader()
        w.writerows(features)

    # Write assignments.csv
    asg_fields = [
        "assignment_id", "feature_id", "engineer_id", "version",
        "feature_name", "group_id", "lifecycle_status", "progress_pct",
    ]
    with asg_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=asg_fields)
        w.writeheader()
        w.writerows(assignments)

    # ── Summary ─────────────────────────────────────────────────────────────
    GROUP_NAMES = {
        1: "Autopilot", 2: "Safety", 3: "UI",
        4: "Navigation", 5: "Media", 6: "Connectivity", 7: "Hardware",
    }
    SUBGROUP_NAMES = {
        101: "Speed Control",       102: "Lane Management",
        103: "Parking & Summon",    104: "Neural Network",
        201: "Driver Monitoring",   202: "Child & Pet Safety",
        203: "Collision Detection", 301: "Dashcam Viewer",
        302: "Visualizations",      303: "Themes",
        401: "Supercharger",        402: "Trip Planning",
        403: "Maps",                501: "Music Streaming",
        502: "Entertainment",       601: "AI Assistant",
        602: "App Integration",     701: "Lights",
        702: "Suspension",          703: "Cameras",
    }

    print(f"\n{'='*55}")
    print(f"  Tesla TPM Enricher — Summary")
    print(f"{'='*55}")
    print(f"  Total features enriched : {len(features)}")
    print(f"  Assignments generated   : {len(assignments)}")
    print(f"  Written -> {out_path}")
    print(f"  Written -> {asg_path}")

    print(f"\n  Features by group:")
    for gid, count in sorted(group_counts.items()):
        print(f"    {GROUP_NAMES.get(gid, gid):<18} {count:4d}")

    print(f"\n  Features by subgroup (top 10):")
    top_sub = sorted(subgroup_counts.items(), key=lambda x: -x[1])[:10]
    for sid, count in top_sub:
        print(f"    {SUBGROUP_NAMES.get(sid, sid):<22} {count:4d}")

    print(f"\n  Lifecycle status breakdown:")
    for st, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"    {st:<22} {count:4d}")

    default_pct = len(unmatched) / len(features) * 100
    print(f"\n  Keyword match rate      : {100 - default_pct:.1f}%")
    print(f"  Fell to default (UI/Viz): {len(unmatched):4d}  ({default_pct:.1f}%)")
    if unmatched[:5]:
        print(f"  Sample unmatched        : {unmatched[:5]}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    enrich()
