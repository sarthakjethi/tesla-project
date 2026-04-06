"""
app.py — Flask web frontend for the Tesla TPM Dashboard.

Routes:
    GET /                         Home page with date picker + version compare inputs
    GET /snapshot?date=YYYY-MM-DD Program state on a specific date (6 dashboard views)
    GET /compare?v1=X&v2=Y        Comparison between two versions or date strings
"""

import sys
import os
from pathlib import Path
from collections import defaultdict

# ── path / cwd setup ─────────────────────────────────────────────────────────
# loader.py resolves DATA_DIR = Path("data") relative to CWD, so CWD must be
# the project root.  tracker.py / loader.py use bare imports, so src/ must be
# on sys.path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, render_template, request, redirect, url_for
import loader
import tracker

app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static"),
)

# ── load data once at startup ─────────────────────────────────────────────────
DATA = loader.load_all()


# ── helper utilities ──────────────────────────────────────────────────────────

def _is_version(s: str) -> bool:
    """True for Tesla version strings like 2024.26 or 2024.26.3."""
    return "." in s and "-" not in s


def _version_to_date(version: str) -> str | None:
    """Return YYYY-MM-DD for a release version, or None if not found."""
    for rel in DATA["releases"]:
        if rel["version"] == version:
            dt = rel.get("_release_dt")
            if dt:
                return dt.strftime("%Y-%m-%d")
    return None


def _stats() -> dict:
    return {
        "versions":  len(DATA["releases"]),
        "features":  len(DATA["features"]),
        "engineers": len(DATA["engineers"]),
        "risks":     len(DATA["risks"]),
    }


def _build_feature_tree(snap: dict) -> list:
    """
    Build a sorted group → subgroup tree from snapshot features.

    Returns list of dicts, each with:
        id, name, total, released, rc, fc, dev, planned,
        subgroups: [{id, name, total, statuses}]
    """
    tree: dict = {}
    for f in snap["features"]:
        gid  = f["group_id"]
        sgid = f["subgroup_id"]
        st   = f["snap_status"]

        if gid not in tree:
            tree[gid] = {
                "id":       gid,
                "name":     snap["g_names"].get(gid, f"Group {gid}"),
                "total":    snap["group_counts"].get(gid, {}).get("total", 0),
                "subgroups": {},
            }
        sg_map = tree[gid]["subgroups"]
        if sgid not in sg_map:
            sg_map[sgid] = {
                "id":       sgid,
                "name":     snap["sg_names"].get(sgid, f"Sub {sgid}"),
                "statuses": defaultdict(int),
            }
        sg_map[sgid]["statuses"][st] += 1

    result = []
    for gid in sorted(tree.keys()):
        g  = tree[gid]
        subgroups = []
        for sgid in sorted(g["subgroups"].keys()):
            sg = g["subgroups"][sgid]
            subgroups.append({
                "id":       sg["id"],
                "name":     sg["name"],
                "total":    sum(sg["statuses"].values()),
                "statuses": dict(sg["statuses"]),
            })

        # Group-level status totals (sum of subgroups)
        def _gs(key):
            return sum(sg["statuses"].get(key, 0) for sg in subgroups)

        result.append({
            "id":        g["id"],
            "name":      g["name"],
            "total":     g["total"],
            "released":  _gs("released"),
            "rc":        _gs("release_complete"),
            "fc":        _gs("feature_complete"),
            "dev":       _gs("in_development"),
            "planned":   _gs("planned"),
            "subgroups": subgroups,
        })
    return result


def _build_engineer_loads(snap: dict) -> dict:
    """
    Returns {engineer_id: {status: [features]}} for the full roster.
    Used to populate the Team View table.
    """
    loads: dict = defaultdict(lambda: defaultdict(list))
    for f in snap["features"]:
        loads[f["engineer_id"]][f["snap_status"]].append(f)
    return {eid: dict(d) for eid, d in loads.items()}


def _build_hw_stats(snap: dict) -> dict:
    """Pre-compute hardware gap numbers and sample lists."""
    released = [f for f in snap["features"] if f["snap_status"] == "released"]
    both, hw4_only, hw3_only, no_hw = [], [], [], []
    for f in released:
        hw = f.get("hw_requirement") or f.get("hardware") or ""
        h3, h4 = "HW3" in hw, "HW4" in hw
        if h3 and h4:
            both.append(f)
        elif h4:
            hw4_only.append(f)
        elif h3:
            hw3_only.append(f)
        else:
            no_hw.append(f)

    by_group: dict = defaultdict(int)
    for f in hw4_only:
        gname = snap["g_names"].get(f["group_id"], str(f["group_id"]))
        by_group[gname] += 1

    return {
        "total":       len(released),
        "both":        len(both),
        "hw4_only":    len(hw4_only),
        "hw3_only":    len(hw3_only),
        "no_hw":       len(no_hw),
        "hw4_by_group": sorted(by_group.items(), key=lambda x: -x[1]),
        "hw4_sample":  hw4_only[:10],
    }


def _build_velocity_stats(snap: dict) -> dict:
    """Pre-compute top releases and category breakdown for Velocity view."""
    _shipped = {"released", "release_complete"}
    ver_feats: dict = defaultdict(list)
    cycle_by_ver: dict = defaultdict(list)
    for f in snap["features"]:
        if f["snap_status"] in _shipped:
            ver_feats[f["version"]].append(f)
            ds = f.get("_dev_start_dt")
            rc = f.get("_release_complete_dt")
            if ds and rc:
                cycle_by_ver[f["version"]].append((rc - ds).days)

    rel_dict = {r["version"]: r for r in snap["released_versions"]}

    top_10 = []
    for ver, feats in sorted(ver_feats.items(), key=lambda x: -len(x[1]))[:10]:
        cy  = cycle_by_ver.get(ver, [])
        rel = rel_dict.get(ver, {})
        top_10.append({
            "version":   ver,
            "count":     len(feats),
            "avg_cycle": round(sum(cy) / len(cy), 1) if cy else 0.0,
            "date":      rel.get("release_date", ""),
        })

    recent_15 = []
    for rel in snap["released_versions"][-15:]:
        ver = rel["version"]
        recent_15.append({
            "version": ver,
            "count":   len(ver_feats.get(ver, [])),
            "date":    rel.get("release_date", ""),
        })

    cat_counts: dict = defaultdict(int)
    for f in snap["features"]:
        if f["snap_status"] == "released":
            cat_counts[f["category"]] += 1
    total_cat = sum(cat_counts.values())
    categories = [
        {
            "name":  cat,
            "count": n,
            "pct":   round(n / total_cat * 100, 1) if total_cat else 0,
        }
        for cat, n in sorted(cat_counts.items(), key=lambda x: -x[1])
    ]

    return {
        "top_10":     top_10,
        "recent_15":  recent_15,
        "categories": categories,
    }


def _build_comparison_display(comp: dict) -> dict:
    """Flatten comparison data into template-friendly structures."""
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    eng_list = [
        {
            "name":  comp["eng_map"].get(eid, {"name": eid})["name"],
            "count": cnt,
        }
        for eid, cnt in sorted(comp["eng_counts"].items(), key=lambda x: -x[1])
    ]

    group_list = [
        {
            "name":  comp["g_names"].get(gid, f"Group {gid}"),
            "count": comp["group_counts"][gid],
        }
        for gid in sorted(comp["group_counts"].keys())
    ]

    wfpm, ofpm = comp["window_fpm"], comp["overall_fpm"]
    if ofpm > 0:
        ratio = wfpm / ofpm
        pace  = "faster" if ratio > 1.1 else ("slower" if ratio < 0.9 else "on-pace")
    else:
        pace = "N/A"

    open_risks = sorted(
        [r for r in comp["risks"] if r.get("status", "open") == "open"],
        key=lambda x: sev_order.get(x["severity"], 9),
    )

    return {
        "eng_list":   eng_list,
        "group_list": group_list,
        "pace":       pace,
        "open_risks": open_risks,
    }


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", stats=_stats())


@app.route("/snapshot")
def snapshot():
    date = request.args.get("date", "").strip()
    if not date:
        return redirect(url_for("index"))

    try:
        snap = tracker.get_snapshot(date, DATA)
    except Exception as exc:
        return render_template("index.html", stats=_stats(), error=str(exc))

    status_order = [
        "released", "release_complete", "feature_complete",
        "in_development", "planned",
    ]

    return render_template(
        "snapshot.html",
        snap=snap,
        feature_tree=_build_feature_tree(snap),
        eng_loads=_build_engineer_loads(snap),
        hw_stats=_build_hw_stats(snap),
        vel_stats=_build_velocity_stats(snap),
        status_order=status_order,
    )


@app.route("/compare")
def compare():
    v1 = request.args.get("v1", "").strip()
    v2 = request.args.get("v2", "").strip()
    if not v1 or not v2:
        return redirect(url_for("index"))

    date1 = _version_to_date(v1) if _is_version(v1) else v1
    date2 = _version_to_date(v2) if _is_version(v2) else v2

    if not date1:
        return render_template(
            "index.html", stats=_stats(),
            error=f"Version '{v1}' not found in releases data.",
        )
    if not date2:
        return render_template(
            "index.html", stats=_stats(),
            error=f"Version '{v2}' not found in releases data.",
        )

    try:
        comp = tracker.get_comparison(date1, date2, DATA)
    except Exception as exc:
        return render_template("index.html", stats=_stats(), error=str(exc))

    return render_template(
        "compare.html",
        comp=comp,
        v1=v1,
        v2=v2,
        display=_build_comparison_display(comp),
    )


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
