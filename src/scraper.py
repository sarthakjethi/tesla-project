"""
Tesla Software Update Scraper
Collects release notes from notateslaapp.com for all versions 2023+
"""

import json
import csv
import time
import re
import logging
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://www.notateslaapp.com"
HISTORY_URL = f"{BASE_URL}/software-updates/history/"
SCRAPED_DIR = Path("data/scraped")
DATA_DIR = Path("data")
SLEEP_SECONDS = 1.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TeslaDashboardScraper/1.0; "
        "research use only)"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get(url: str) -> BeautifulSoup | None:
    """Fetch URL and return a BeautifulSoup object, or None on error."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        log.error("Failed to fetch %s — %s", url, exc)
        return None


def version_year(version: str) -> int | None:
    """Return the year prefix of a version string like '2023.44.25'."""
    match = re.match(r"(\d{4})\.", version)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Step 1 — scrape history page for version list
# ---------------------------------------------------------------------------

def fetch_version_list() -> list[dict]:
    """
    Parse the history page and return a list of
    {"version": "2024.44.25", "url": "https://..."} dicts for 2023+.
    """
    log.info("Fetching history page …")
    soup = get(HISTORY_URL)
    if soup is None:
        raise RuntimeError("Could not fetch history page — aborting.")

    versions = []
    seen = set()

    # Each sub-version is linked via an <a> whose href matches the pattern
    # /software-updates/version/{VERSION}/release-notes
    pattern = re.compile(r"/software-updates/version/([^/]+)/release-notes")

    for a in soup.find_all("a", href=pattern):
        href = a["href"]
        m = pattern.search(href)
        if not m:
            continue
        version = m.group(1)
        if version in seen:
            continue
        year = version_year(version)
        if year is None or year < 2023:
            continue
        seen.add(version)
        full_url = href if href.startswith("http") else BASE_URL + href
        versions.append({"version": version, "url": full_url})

    # Sort oldest → newest
    versions.sort(key=lambda v: v["version"])
    log.info("Found %d versions from 2023 onwards", len(versions))
    return versions


# ---------------------------------------------------------------------------
# Step 2 — scrape a single release notes page
# ---------------------------------------------------------------------------

def parse_release_notes(version: str, url: str) -> dict | None:
    """
    Scrape a release notes page and return a structured dict.

    Page structure (verified from live HTML):
      - Overview features: <a class="mod-update-overview-feature">
            <h3 class="mod-update-overview-feature-heading">NAME</h3>
            <div class="mod-update-overview-feature-description">CATEGORY</div>
      - FSD Version / Release Date: standalone <h3> followed by
            <div class="mod-update-overview-feature-description">VALUE</div>
            (appears twice on the page — take first occurrence)
      - Feature details: <div class="mod-update-feature">
            .mod-update-feature-heading  → name (matches overview)
            .mod-update-feature-content  → description prose
            .requirements-models parent  → models string
            .requirements-features       → HW3 / HW4 chip tags
    """
    soup = get(url)
    if soup is None:
        return None

    data: dict = {
        "version": version,
        "url": url,
        "release_date": None,
        "fsd_version": None,
        "features": [],
    }

    # ── 1. Overview feature list (name + category) ───────────────────────────
    # Skip FSD version-history rows like "Update 2026.4.5 — FSD Supervised …"
    _fsd_history = re.compile(r"^Update \d{4}\.")

    for a in soup.find_all("a", class_="mod-update-overview-feature"):
        name_el = a.find(class_="mod-update-overview-feature-heading")
        cat_el  = a.find(class_="mod-update-overview-feature-description")
        if not name_el:
            continue
        name = name_el.get_text(strip=True)
        if _fsd_history.match(name):
            continue
        data["features"].append({
            "name":        name,
            "category":    cat_el.get_text(strip=True) if cat_el else None,
            "models":      None,
            "hardware":    [],
            "description": "",
        })

    # ── 2. FSD Version + Release Date ────────────────────────────────────────
    # Both appear as bare <h3> tags (outside the feature wrappers) with a
    # <div class="mod-update-overview-feature-description"> sibling.
    # They are duplicated in a sidebar — stop after the first of each.
    for h3 in soup.find_all("h3"):
        if data["fsd_version"] and data["release_date"]:
            break
        title = h3.get_text(strip=True)
        if title == "FSD Version" and not data["fsd_version"]:
            sib = h3.find_next_sibling("div")
            if sib:
                data["fsd_version"] = sib.get_text(strip=True)
        elif title == "Release Date" and not data["release_date"]:
            sib = h3.find_next_sibling("div")
            if sib:
                data["release_date"] = sib.get_text(strip=True)

    # ── 3. Feature details (description, models, hardware) ───────────────────
    feature_map = {f["name"]: f for f in data["features"]}

    for detail in soup.find_all(class_="mod-update-feature"):
        heading_el = detail.find(class_="mod-update-feature-heading")
        if not heading_el:
            continue
        feat = feature_map.get(heading_el.get_text(strip=True))
        if feat is None:
            continue

        # Description prose
        content_el = detail.find(class_="mod-update-feature-content")
        if content_el:
            feat["description"] = content_el.get_text(separator=" ", strip=True)

        # Models — label div is .requirements-models; value is rest of parent block
        models_label = detail.find(class_="requirements-models")
        if models_label:
            block_text = models_label.parent.get_text(separator=" ", strip=True)
            models_val = re.sub(r"^Models:\s*", "", block_text).strip()
            feat["models"] = models_val or None

        # Hardware chips — each has class requirements-features
        hw = []
        for hw_el in detail.find_all(class_="requirements-features"):
            chip = hw_el.get_text(strip=True)
            if chip and chip not in hw:
                hw.append(chip)
        feat["hardware"] = hw

    return data


# ---------------------------------------------------------------------------
# Step 3 — save per-version JSON
# ---------------------------------------------------------------------------

def save_json(data: dict) -> None:
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRAPED_DIR / f"{data['version']}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Step 4 — build CSVs
# ---------------------------------------------------------------------------

def build_csvs(all_data: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # releases.csv — one row per version
    releases_path = DATA_DIR / "releases.csv"
    with releases_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["version", "release_date", "fsd_version",
                        "feature_count", "url"],
        )
        writer.writeheader()
        for d in all_data:
            writer.writerow({
                "version": d["version"],
                "release_date": d.get("release_date") or "",
                "fsd_version": d.get("fsd_version") or "",
                "feature_count": len(d.get("features", [])),
                "url": d["url"],
            })
    log.info("Wrote %s (%d rows)", releases_path, len(all_data))

    # features_raw.csv — one row per feature per version
    features_path = DATA_DIR / "features_raw.csv"
    total_features = 0
    with features_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["version", "release_date", "feature_name",
                        "category", "models", "hardware", "description"],
        )
        writer.writeheader()
        for d in all_data:
            for feat in d.get("features", []):
                writer.writerow({
                    "version": d["version"],
                    "release_date": d.get("release_date") or "",
                    "feature_name": feat["name"],
                    "category": feat.get("category") or "",
                    "models": feat.get("models") or "",
                    "hardware": ", ".join(feat.get("hardware", [])),
                    "description": feat.get("description") or "",
                })
                total_features += 1
    log.info("Wrote %s (%d rows)", features_path, total_features)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=== Tesla Scraper — starting ===")
    start = datetime.now()

    versions = fetch_version_list()

    all_data: list[dict] = []
    failed: list[str] = []

    for i, entry in enumerate(versions, 1):
        version = entry["version"]
        url = entry["url"]

        # Skip if already scraped
        cached = SCRAPED_DIR / f"{version}.json"
        if cached.exists():
            log.info("[%d/%d] %s — cached, loading from disk",
                     i, len(versions), version)
            all_data.append(json.loads(cached.read_text(encoding="utf-8")))
            continue

        log.info("[%d/%d] Scraping %s …", i, len(versions), version)
        data = parse_release_notes(version, url)

        if data is None:
            log.warning("  ✗ skipped %s (fetch/parse error)", version)
            failed.append(version)
        else:
            feat_count = len(data.get("features", []))
            log.info("  ✓ %s | %s | %d features",
                     version,
                     data.get("release_date") or "date unknown",
                     feat_count)
            save_json(data)
            all_data.append(data)

        time.sleep(SLEEP_SECONDS)

    # Build CSVs from everything successfully scraped
    if all_data:
        build_csvs(all_data)

    elapsed = (datetime.now() - start).seconds
    log.info("=== Done in %ds — %d scraped, %d failed ===",
             elapsed, len(all_data), len(failed))
    if failed:
        log.warning("Failed versions: %s", ", ".join(failed))


if __name__ == "__main__":
    main()
