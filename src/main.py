"""
main.py — Tesla TPM Dashboard CLI

Usage:
    python src/main.py 2024-09-01
    python src/main.py 2023-06-01 --group 1
    python src/main.py              (defaults to today)
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


def _parse_args() -> tuple[str, int | None]:
    """Return (date_str, group_filter_or_None)."""
    date_str     = datetime.today().strftime("%Y-%m-%d")
    group_filter = None

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--group" and i + 1 < len(args):
            try:
                group_filter = int(args[i + 1])
            except ValueError:
                pass
        elif arg.count("-") == 2 and not arg.startswith("--"):
            date_str = arg

    return date_str, group_filter


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Ensure stdout handles UTF-8 (Windows workaround)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    date_str, group_filter = _parse_args()

    # Validate date
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"ERROR: invalid date '{date_str}' — expected YYYY-MM-DD")
        sys.exit(1)

    # Load & snapshot
    print(f"\nLoading data...", flush=True)
    data = loader.load_all()
    print(f"Computing snapshot for {date_str}...", flush=True)
    snap = tracker.get_snapshot(date_str, data)

    # Header banner
    print()
    print("=" * 72)
    print(f"  TESLA TPM DASHBOARD  --  snapshot date: {date_str}")
    print(f"  {len(data['features'])} features across "
          f"{len(data['releases'])} versions  |  "
          f"{len(data['engineers'])} engineers  |  "
          f"{len(data['risks'])} risks tracked")
    print("=" * 72)

    # Status quick-stats
    sc = snap["status_counts"]
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

    # ── 6 views ─────────────────────────────────────────────────────────────
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


if __name__ == "__main__":
    main()
