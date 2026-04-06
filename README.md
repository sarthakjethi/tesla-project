# Tesla TPM Dashboard

Managing a software release program means knowing what shipped, what is at risk, and who owns what at any point in time. I built tooling to simulate exactly that, using three years of real Tesla Autopilot release data.

## Overview

The dashboard scrapes public Tesla release notes from 2023 to 2026, structures 1,782 features into engineering teams, lifecycle stages, and risk categories, then lets you query the full program state at any date. The core engine reconstructs what was in development, what had shipped, and what risks were open on any given day across 118 software versions. Built end to end from data collection to web deployment using only public information.

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

