# Tesla TPM Dashboard

A full-stack program management tool that ingests 118 Tesla software releases, tracks 1,782 features across 10 engineering teams, and surfaces risks and progress through a live web interface.

## Live Demo

https://sarthakjethi.com/projects/tpm.html

## What It Does

The dashboard supports three input modes: snapshot (current state of any single version), version-to-version diff (what changed between two releases), and date range (all activity within a time window). A visitor can explore feature velocity by engineering team, filter active risks by severity, and trace any feature from introduction through completion. Every view is generated dynamically from structured data derived from real Tesla release notes.

## Why I Built It

I built this to demonstrate the kind of end-to-end ownership a TPM at Tesla is expected to exercise — taking a vague problem (how do you track software program health across dozens of releases?) and driving it from data acquisition through tooling to a shippable product. The risk tracking and cross-functional team assignment layers reflect the core of what a TPM does: making sure nothing falls through the cracks across engineering boundaries. This project is my answer to the question of what cross-functional visibility looks like when you build it from scratch.

## Data

- 118 software versions scraped from public Tesla release notes (2023–2026)
- 1,782 features categorized by group, subgroup, and lifecycle stage
- 10 engineering teams with feature assignments and progress tracking
- 10 risks with severities, mitigations, and date-aware filtering

## How It Works

**Phase 1 — Scraper**
`scraper.py` fetches and parses public Tesla software release pages using Python and BeautifulSoup, extracting version metadata and feature text into structured JSON. An enrichment pass in `enricher.py` assigns each feature to an engineering team, lifecycle stage, and risk tags.

**Phase 2 — Dashboard Engine**
`tracker.py` implements a time-travel snapshot engine that can reconstruct program state at any version or date, compute diffs between releases, and aggregate team-level velocity metrics. `reporter.py` formats this data for both CLI output and web consumption.

**Phase 3 — Web Deployment**
`app.py` exposes three Flask routes corresponding to the three input modes, rendering server-side HTML templates styled to match a clean, professional aesthetic. The app is served via Gunicorn and deployed at sarthakjethi.com.

## Tech Stack

Python, BeautifulSoup, Flask, Gunicorn, Git, Claude Code

## Input Modes

```
# Snapshot — current state of a single version
python main.py --mode snapshot --version 2024.44.25

# Diff — what changed between two releases
python main.py --mode diff --from 2024.44.25 --to 2025.2.6

# Date range — all activity within a time window
python main.py --mode range --start 2024-01-01 --end 2024-12-31
```

`snapshot` — shows feature status, team assignments, and active risks for one release.  
`diff` — highlights features added, completed, or dropped between two versions.  
`range` — aggregates velocity and risk exposure across all releases in a date window.

## Author

Sarthak Jethi — sarthakjethi.com
