"""
main.py — Tesla TPM Dashboard CLI

Usage:
    python src/main.py 2024-09-01              # Mode 1: single date snapshot
    python src/main.py 2024.26 2025.14         # Mode 2: version-to-version comparison
    python src/main.py 2024-07-01 2025-04-01   # Mode 3: date-range comparison
    python src/main.py 2023-06-01 --group 1    # Mode 1 with group filter
    python src/main.py                         # Mode 1: defaults to today
"""

import sys
import os
from datetime import datetime

# Make sure src/ is on the path when running from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import loader
import tracker
import reporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_lines(lines: list[str]) -> None:
    for line in lines:
        print(line)


def _is_date(s: str) -> bool:
    """True if s looks like YYYY-MM-DD."""
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _is_version(s: str) -> bool:
    """True if s looks like a Tesla version (contains dots, e.g. 2024.26)."""
    return "." in s and "-" not in s


def _version_to_date(version: str, data: dict) -> str | None:
    """Return YYYY-MM-DD for a release version, or None if not found."""
    for rel in data["releases"]:
        if rel["version"] == version:
            dt = rel.get("_release_dt")
            if dt:
                return dt.strftime("%Y-%m-%d")
    return None


def _parse_args():
    """
    Detect input mode and return a tagged tuple:
        ("snapshot",    date_str, group_filter)
        ("comparison",  date1_str, date2_str)
        ("v_comparison", version1, version2)
    """
    raw  = sys.argv[1:]
    # pull out --group N first
    group_filter = None
    positional   = []
    i = 0
    while i < len(raw):
        if raw[i] == "--group" and i + 1 < len(raw):
            try:
                group_filter = int(raw[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            positional.append(raw[i])
            i += 1

    if len(positional) == 0:
        return ("snapshot", datetime.today().strftime("%Y-%m-%d"), group_filter)

    if len(positional) == 1:
        # Mode 1: single date
        return ("snapshot", positional[0], group_filter)

    if len(positional) >= 2:
        a1, a2 = positional[0], positional[1]
        if _is_version(a1) and _is_version(a2):
            # Mode 2: version-to-version
            return ("v_comparison", a1, a2)
        if _is_date(a1) and _is_date(a2):
            # Mode 3: date range
            return ("comparison", a1, a2)

    # Fallback: treat first date-like arg as Mode 1
    date_str = next(
        (a for a in positional if _is_date(a)),
        datetime.today().strftime("%Y-%m-%d"),
    )
    return ("snapshot", date_str, group_filter)


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------

def _run_snapshot(date_str: str, group_filter: int | None, data: dict) -> None:
    if not _is_date(date_str):
        print(f"ERROR: invalid date '{date_str}' — expected YYYY-MM-DD")
        sys.exit(1)

    print(f"Computing snapshot for {date_str}...", flush=True)
    snap = tracker.get_snapshot(date_str, data)

    print()
    print("=" * 72)
    print(f"  TESLA TPM DASHBOARD  --  snapshot date: {date_str}")
    print(f"  {len(data['features'])} features across "
          f"{len(data['releases'])} versions  |  "
          f"{len(data['engineers'])} engineers  |  "
          f"{len(data['risks'])} risks tracked")
    print("=" * 72)

    sc    = snap["status_counts"]
    order = ["released", "release_complete", "feature_complete",
             "in_development", "planned"]
    print()
    print("  SNAPSHOT STATUS COUNTS:")
    for st in order:
        n = sc.get(st, 0)
        if n:
            sym = reporter._status_symbol(st)
            print(f"    {sym}  {st:<22}  {n:4d}")

    print()
    print("  Active engineers on this date:", len(snap["active_engineers"]))
    print("  In-flight versions:           ", len(snap["active_versions"]))
    print("  Released versions:            ", len(snap["released_versions"]))
    print()

    _print_lines(reporter.release_roadmap(snap))
    _print_lines(reporter.feature_explorer(snap, group_filter=group_filter))
    _print_lines(reporter.team_view(snap))
    _print_lines(reporter.risk_register(snap))
    _print_lines(reporter.hardware_gap(snap))
    _print_lines(reporter.velocity_report(snap))

    print("=" * 72)
    print(f"  End of dashboard  --  {date_str}")
    print("=" * 72)
    print()


def _run_comparison(date1: str, date2: str, data: dict, label: str = "") -> None:
    print(f"Computing comparison {date1} -> {date2}...{label}", flush=True)
    comp = tracker.get_comparison(date1, date2, data)
    _print_lines(reporter.comparison_report(comp))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parsed = _parse_args()
    mode   = parsed[0]

    print(f"\nLoading data...", flush=True)
    data = loader.load_all()

    if mode == "snapshot":
        _, date_str, group_filter = parsed
        _run_snapshot(date_str, group_filter, data)

    elif mode == "v_comparison":
        _, v1, v2 = parsed
        date1 = _version_to_date(v1, data)
        date2 = _version_to_date(v2, data)
        if not date1:
            print(f"ERROR: version '{v1}' not found in releases.csv")
            sys.exit(1)
        if not date2:
            print(f"ERROR: version '{v2}' not found in releases.csv")
            sys.exit(1)
        print(f"  {v1} released on {date1}")
        print(f"  {v2} released on {date2}")
        _run_comparison(date1, date2, data, label=f"  ({v1} -> {v2})")

    elif mode == "comparison":
        _, date1, date2 = parsed
        _run_comparison(date1, date2, data)


if __name__ == "__main__":
    main()
