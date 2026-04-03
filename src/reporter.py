"""
reporter.py — six dashboard views built from tracker snapshot output.
All functions return a list of strings (lines) for the caller to print.
"""

from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Shared formatting helpers
# ---------------------------------------------------------------------------

W = 72  # total width


def _box(title: str) -> list[str]:
    bar = "+" + "-" * (W - 2) + "+"
    pad = (W - 2 - len(title)) // 2
    return [bar, "|" + " " * pad + title + " " * (W - 2 - pad - len(title)) + "|", bar]


def _section(title: str) -> list[str]:
    return ["", "  " + title, "  " + "-" * (W - 4)]


def _bar(label: str, value: int, total: int, width: int = 28) -> str:
    pct  = value / total if total else 0
    fill = int(pct * width)
    bar  = "#" * fill + "-" * (width - fill)
    return f"  {label:<26} [{bar}] {value:4d}  ({pct*100:4.1f}%)"


def _status_symbol(status: str) -> str:
    return {
        "released":         "[DONE]",
        "release_complete": "[RC]  ",
        "feature_complete": "[FC]  ",
        "in_development":   "[DEV] ",
        "planned":          "[PLAN]",
    }.get(status, "[?]   ")


# ---------------------------------------------------------------------------
# 1. Release Roadmap
# ---------------------------------------------------------------------------

def release_roadmap(snap: dict) -> list[str]:
    lines = _box("  RELEASE ROADMAP  --  snapshot: " + snap["date_str"])

    # Released versions (last 8 + all active + next 8 upcoming)
    released  = snap["released_versions"][-8:]
    active    = snap["active_versions"]
    upcoming  = snap["upcoming_versions"][:8]

    def _rel_line(rel: dict, tag: str) -> str:
        ver   = rel["version"]
        dt    = rel.get("release_date") or "TBD"
        fsd   = rel.get("fsd_version") or ""
        cnt   = rel.get("feature_count") or 0
        fsd_s = f"  FSD:{fsd}" if fsd else ""
        return f"  {tag}  {ver:<18} {dt:<22} {str(cnt)+'f':>5}{fsd_s}"

    lines += _section("Recently Released")
    for r in released:
        lines.append(_rel_line(r, "[DONE]"))

    if active:
        lines += _section("In Flight")
        for r in active:
            lines.append(_rel_line(r, "[DEV] "))

    if upcoming:
        lines += _section("Upcoming")
        for r in upcoming:
            lines.append(_rel_line(r, "[PLAN]"))

    v = snap["velocity"]
    lines += _section("Velocity Summary")
    lines.append(f"  Versions released by {snap['date_str']:<12}: {v['versions_released']}")
    lines.append(f"  Features released                     : {v['features_released']}")
    lines.append(f"  Avg features per release              : {v['avg_features_per_release']}")
    lines.append(f"  Avg cycle time (dev_start to release) : {v['avg_cycle_days']} days")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# 2. Feature Explorer
# ---------------------------------------------------------------------------

def feature_explorer(snap: dict, group_filter: int | None = None) -> list[str]:
    title = "FEATURE EXPLORER"
    if group_filter:
        gname = snap["g_names"].get(group_filter, str(group_filter))
        title += f"  --  group: {gname}"
    title += "  --  snapshot: " + snap["date_str"]
    lines = _box(title)

    features = snap["features"]
    if group_filter:
        features = [f for f in features if f["group_id"] == group_filter]

    # Group -> subgroup -> status counts
    tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for f in features:
        tree[f["group_id"]][f["subgroup_id"]][f["snap_status"]] += 1

    total_feats = len(features)
    status_order = ["released", "release_complete", "feature_complete",
                    "in_development", "planned"]

    for gid in sorted(tree.keys()):
        gname = snap["g_names"].get(gid, f"Group {gid}")
        gc    = snap["group_counts"].get(gid, {})
        gtotal = gc.get("total", 0)
        lines.append(f"\n  [{gid}] {gname.upper():<20}  ({gtotal} features)")
        for sgid in sorted(tree[gid].keys()):
            sgname = snap["sg_names"].get(sgid, f"Sub {sgid}")
            sc     = tree[gid][sgid]
            sgtot  = sum(sc.values())
            parts  = []
            for st in status_order:
                n = sc.get(st, 0)
                if n:
                    sym = _status_symbol(st).strip()
                    parts.append(f"{sym}:{n}")
            lines.append(f"    {sgname:<28} {sgtot:3d}  " + "  ".join(parts))

    lines += _section("Status Legend")
    lines.append("  [DONE]=released  [RC]=release_complete  [FC]=feature_complete")
    lines.append("  [DEV]=in_development  [PLAN]=planned")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# 3. Team View
# ---------------------------------------------------------------------------

def team_view(snap: dict) -> list[str]:
    lines = _box("  TEAM VIEW  --  snapshot: " + snap["date_str"])

    eng_map     = snap["eng_map"]
    active_eng  = snap["active_engineers"]
    all_feats   = snap["features"]

    # Build full load per engineer (all statuses)
    eng_all: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for f in all_feats:
        eng_all[f["engineer_id"]][f["snap_status"]].append(f)

    lines += _section("Active Engineers (have in_development or feature_complete work)")

    if not active_eng:
        lines.append("  -- No engineers have active work on this date --")
    else:
        for eid in sorted(active_eng.keys()):
            eng  = eng_map.get(eid, {"name": eid, "team": "?", "seniority": "?"})
            afs  = active_eng[eid]
            dev  = [f for f in afs if f["snap_status"] == "in_development"]
            fc   = [f for f in afs if f["snap_status"] == "feature_complete"]
            lines.append(
                f"\n  {eng['name']:<18} [{eng['seniority']:<6}]  "
                f"team:{eng['team']}"
            )
            lines.append(
                f"  {'':18}  DEV:{len(dev):2d}  FC:{len(fc):2d}  "
                f"total active:{len(afs):2d}"
            )
            # Show up to 5 in-development features
            for f in dev[:5]:
                gname = snap["g_names"].get(f["group_id"], "")
                lines.append(f"    [DEV]  {f['feature_name'][:42]:<42}  ({gname})")
            if len(dev) > 5:
                lines.append(f"    ... and {len(dev)-5} more in development")
            for f in fc[:3]:
                gname = snap["g_names"].get(f["group_id"], "")
                lines.append(f"    [FC]   {f['feature_name'][:42]:<42}  ({gname})")
            if len(fc) > 3:
                lines.append(f"    ... and {len(fc)-3} more feature_complete")

    lines += _section("Full Engineer Roster")
    lines.append(f"  {'ID':<5} {'Name':<18} {'Seniority':<8} {'Team':<14} "
                 f"{'Released':>8} {'Active':>7} {'Planned':>7}")
    lines.append("  " + "-" * (W - 4))
    for eng in snap["engineers"]:
        eid   = eng["engineer_id"]
        eload = eng_all[eid]
        rel   = len(eload.get("released", []))
        act   = len(eload.get("in_development", [])) + len(eload.get("feature_complete", []))
        pln   = len(eload.get("planned", []))
        lines.append(
            f"  {eid:<5} {eng['name']:<18} {eng['seniority']:<8} "
            f"{eng['team']:<14} {rel:>8} {act:>7} {pln:>7}"
        )
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# 4. Risk Register
# ---------------------------------------------------------------------------

def risk_register(snap: dict) -> list[str]:
    lines = _box("  RISK REGISTER  --  snapshot: " + snap["date_str"])

    risks = snap["risks"]
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_risks = sorted(risks, key=lambda r: (order.get(r["severity"], 9),
                                                order.get(r["probability"], 9)))

    sev_counts: dict[str, int] = defaultdict(int)
    for r in risks:
        sev_counts[r["severity"]] += 1

    lines += _section("Summary")
    for sev in ["critical", "high", "medium", "low"]:
        n = sev_counts.get(sev, 0)
        if n:
            lines.append(f"  {sev.upper():<10} {n} risk(s)")

    prev_sev = None
    for r in sorted_risks:
        if r["severity"] != prev_sev:
            lines += _section(r["severity"].upper() + " SEVERITY")
            prev_sev = r["severity"]
        lines.append(f"  [{r['risk_id']}] {r['title']}")
        lines.append(f"       Prob:{r['probability']:<7} Impact:{r['impact']:<7} "
                     f"Team:{r['owner_team']}")
        # Word-wrap description to W-10
        desc = r["description"]
        while len(desc) > W - 10:
            cut = desc[:W - 10].rfind(" ")
            if cut == -1:
                cut = W - 10
            lines.append(f"       {desc[:cut]}")
            desc = desc[cut:].lstrip()
        if desc:
            lines.append(f"       {desc}")
        lines.append(f"       Mitigation: {r['mitigation'][:W - 22]}")
        lines.append("")

    return lines


# ---------------------------------------------------------------------------
# 5. Hardware Gap Analysis
# ---------------------------------------------------------------------------

def hardware_gap(snap: dict) -> list[str]:
    lines = _box("  HARDWARE GAP ANALYSIS  --  snapshot: " + snap["date_str"])

    released = [f for f in snap["features"] if f["snap_status"] == "released"]

    hw3_only, hw4_only, both_hw, no_hw = [], [], [], []
    for f in released:
        hw = f.get("hw_requirement") or f.get("hardware", "")
        has3 = "HW3" in hw
        has4 = "HW4" in hw
        if has3 and has4:
            both_hw.append(f)
        elif has3:
            hw3_only.append(f)
        elif has4:
            hw4_only.append(f)
        else:
            no_hw.append(f)

    total = len(released)
    lines += _section("Released Feature Distribution (by hardware tag)")
    lines.append(_bar("HW3 + HW4 (both)",    len(both_hw),  total))
    lines.append(_bar("HW4 only",             len(hw4_only), total))
    lines.append(_bar("HW3 only",             len(hw3_only), total))
    lines.append(_bar("No HW restriction",    len(no_hw),    total))

    lines += _section("HW4-Exclusive Features by Group (gap exposure)")
    if hw4_only:
        by_group: dict[int, list] = defaultdict(list)
        for f in hw4_only:
            by_group[f["group_id"]].append(f)
        for gid, feats in sorted(by_group.items(), key=lambda x: -len(x[1])):
            gname = snap["g_names"].get(gid, str(gid))
            lines.append(f"  {gname:<20} {len(feats):3d} HW4-only features")
        lines.append("")
        lines += _section("Sample HW4-Only Features")
        for f in hw4_only[:10]:
            lines.append(f"  {f['version']:<18} {f['feature_name'][:44]}")
    else:
        lines.append("  No HW4-exclusive features tagged in dataset.")
        lines.append("  Note: hardware tags are sparse in source data.")
        lines.append("  Features with no tag are assumed to run on all hardware.")

    lines += _section("Risk Context")
    lines.append("  R01 [CRITICAL] HW3 vs HW4 Feature Gap — see Risk Register for detail.")
    lines.append(f"  Released features on snap date       : {total}")
    lines.append(f"  Features with HW4-only tag           : {len(hw4_only)}")
    lines.append(f"  Features with no HW restriction tag  : {len(no_hw)}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# 6. Velocity Report
# ---------------------------------------------------------------------------

def velocity_report(snap: dict) -> list[str]:
    lines = _box("  VELOCITY REPORT  --  snapshot: " + snap["date_str"])

    released_vers = snap["released_versions"]
    features      = snap["features"]

    # Map version -> features  (released OR release_complete count as shipped)
    _shipped = {"released", "release_complete"}
    ver_feats: dict[str, list] = defaultdict(list)
    for f in features:
        if f["snap_status"] in _shipped:
            ver_feats[f["version"]].append(f)

    # Cycle time per feature
    cycle_by_ver: dict[str, list[int]] = defaultdict(list)
    for f in features:
        if f["snap_status"] in _shipped:
            ds = f.get("_dev_start_dt")
            rc = f.get("_release_complete_dt")
            if ds and rc:
                cycle_by_ver[f["version"]].append((rc - ds).days)

    lines += _section("Velocity Summary")
    v = snap["velocity"]
    lines.append(f"  Versions released        : {v['versions_released']}")
    lines.append(f"  Features released        : {v['features_released']}")
    lines.append(f"  Avg features / release   : {v['avg_features_per_release']}")
    lines.append(f"  Avg cycle time           : {v['avg_cycle_days']} days")

    # Feature count per release — last 15 and top 5
    by_count = sorted(ver_feats.items(), key=lambda x: -len(x[1]))

    lines += _section("Top 10 Releases by Feature Count")
    lines.append(f"  {'Version':<20} {'Features':>8}  {'Avg Cycle':>10}  Release Date")
    lines.append("  " + "-" * (W - 4))
    for ver, feats in by_count[:10]:
        rel = next((r for r in released_vers if r["version"] == ver), {})
        rdt = rel.get("release_date", "")
        cy  = cycle_by_ver.get(ver, [])
        avg_cy = round(sum(cy) / len(cy), 1) if cy else 0.0
        lines.append(f"  {ver:<20} {len(feats):>8}  {avg_cy:>9.1f}d  {rdt}")

    lines += _section("Last 15 Releases (chronological)")
    lines.append(f"  {'Version':<20} {'Features':>8}  Release Date")
    lines.append("  " + "-" * (W - 4))
    for rel in released_vers[-15:]:
        ver  = rel["version"]
        n    = len(ver_feats.get(ver, []))
        rdt  = rel.get("release_date", "")
        lines.append(f"  {ver:<20} {n:>8}  {rdt}")

    # Category breakdown
    cat_counts: dict[str, int] = defaultdict(int)
    for f in features:
        if f["snap_status"] == "released":
            cat_counts[f["category"]] += 1

    lines += _section("Released Features by Category")
    total_rel = sum(cat_counts.values())
    for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
        lines.append(_bar(cat, n, total_rel))
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# 7. Comparison Report
# ---------------------------------------------------------------------------

def comparison_report(comp: dict) -> list[str]:
    """Format a get_comparison() result into printable lines."""
    d1, d2, days = comp["date1_str"], comp["date2_str"], comp["days"]
    g_names = comp["g_names"]
    eng_map = comp["eng_map"]

    lines = _box(f"  COMPARISON REPORT: {d1} -> {d2}  ({days} days)")

    # ── WHAT SHIPPED ─────────────────────────────────────────────────────────
    lines += _section("WHAT SHIPPED IN THIS WINDOW")
    released = comp["released_in_window"]
    versions = comp["versions_in_window"]

    lines.append(f"  Total features released : {len(released)}")
    lines.append(f"  New versions shipped    : {len(versions)}")
    if versions:
        ver_list = ", ".join(v["version"] for v in versions)
        # wrap at ~60 chars
        chunk, buf = [], ""
        for tok in ver_list.split(", "):
            if len(buf) + len(tok) > 58:
                chunk.append(buf.rstrip(", "))
                buf = ""
            buf += tok + ", "
        if buf:
            chunk.append(buf.rstrip(", "))
        for i, c in enumerate(chunk):
            prefix = "    Versions: " if i == 0 else "              "
            lines.append(prefix + c)

    fsd_s = comp["fsd_at_start"] or "N/A"
    fsd_e = comp["fsd_at_end"]   or "N/A"
    lines.append(f"  FSD                    : {fsd_s} -> {fsd_e}")

    lines.append("  Features by group:")
    # Use known group ordering from g_names
    for gid in sorted(comp["group_counts"].keys()):
        cnt   = comp["group_counts"][gid]
        gname = g_names.get(gid, f"Group {gid}")
        lines.append(f"    {gname:<28} {cnt:4d}")

    # ── PROGRESS MADE ─────────────────────────────────────────────────────────
    lines += _section("PROGRESS MADE (features that moved status)")
    trans_labels = {
        "planned":          "Planned          -> Released",
        "in_development":   "In Development   -> Released",
        "feature_complete": "Feature Complete -> Released",
        "release_complete": "Release Complete -> Released",
    }
    for key in ["planned", "in_development", "feature_complete", "release_complete"]:
        n = comp["transitions"].get(key, 0)
        if n:
            lines.append(f"  {trans_labels[key]}: {n}")

    # ── ENGINEER PRODUCTIVITY ─────────────────────────────────────────────────
    lines += _section("ENGINEER PRODUCTIVITY IN WINDOW")
    eng_counts = comp["eng_counts"]
    if eng_counts:
        top_eid = max(eng_counts, key=lambda e: eng_counts[e])
        top_name = eng_map.get(top_eid, {"name": top_eid})["name"]
        lines.append(f"  Most active engineer: {top_name} ({eng_counts[top_eid]} features shipped)")
        lines.append("")
        lines.append(f"  {'Engineer':<20} {'Shipped':>7}")
        lines.append("  " + "-" * 30)
        for eid, cnt in sorted(eng_counts.items(), key=lambda x: -x[1]):
            name = eng_map.get(eid, {"name": eid})["name"]
            lines.append(f"  {name:<20} {cnt:>7}")
    else:
        lines.append("  No engineer activity recorded in this window.")

    # ── VELOCITY ──────────────────────────────────────────────────────────────
    lines += _section("VELOCITY IN WINDOW vs OVERALL")
    wfpm = comp["window_fpm"]
    ofpm = comp["overall_fpm"]
    lines.append(f"  Features per month in window  : {wfpm:.1f}")
    lines.append(f"  Overall avg features per month: {ofpm:.1f}")
    if ofpm > 0:
        ratio = wfpm / ofpm
        pace = "faster" if ratio > 1.1 else ("slower" if ratio < 0.9 else "same")
    else:
        pace = "N/A"
    lines.append(f"  Pace                          : {pace}")

    # ── RISKS ─────────────────────────────────────────────────────────────────
    lines += _section("RISKS ACTIVE DURING WINDOW")
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    open_risks = [r for r in comp["risks"] if r.get("status", "open") == "open"]
    for r in sorted(open_risks, key=lambda x: sev_order.get(x["severity"], 9)):
        lines.append(f"  [{r['severity'].upper():<8}] {r['title']:<40}  owner: {r['owner_team']}")

    lines.append("")
    return lines
