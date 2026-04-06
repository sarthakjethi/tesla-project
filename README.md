# Tesla TPM Dashboard

What does it look like to manage a software release program when you don't have access to internal tooling? I built this to find out.

## Overview

It scrapes real Tesla release notes, then structures that data into an actual program management model — features assigned to teams, lifecycle stages, risks with severities and mitigations. You can query it three ways: snapshot, version diff, or date range. The interesting part is the time-travel engine: pick any date and it reconstructs the exact state of the program on that day. To be clear, this is a simulation built on public data, not internal Tesla tooling — but the model is real.

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

