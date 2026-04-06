# Tesla TPM Dashboard

Program management tooling built on real Tesla release data — tracks feature velocity, team ownership, and risk exposure across 118 software versions.

## Overview

Scraped from public Tesla release notes and enriched with engineer assignments, lifecycle stages, and risk tags. Supports three query modes: point-in-time snapshot, version diff, and date range rollup. Built to show what cross-functional software tracking looks like when you own it from data to deployment.

## Live Demo

https://sarthakjethi.com/projects/tpm.html

## Data

- 118 Tesla software versions · 2023–2026
- 1,782 features across 7 groups and 20 subgroups
- 10 engineers tracked across 6 teams
- 10 risks with severity levels and date-aware filtering

## Usage

```
python src/main.py 2024-09-01                    # snapshot any date
python src/main.py 2024.26 2025.14               # version to version
python src/main.py 2024-07-01 2025-04-01         # date range
```

## Tech

Python · BeautifulSoup · Flask · Git · Claude Code

## Author

Sarthak Jethi · sarthakjethi.com
