# Floral Image Ops — Executive Dashboard

A single-page executive scorecard for Floral Image daily operations: Salesforce (Closed Won, Trials, Collect/Cancel, Closed Lost, Units on hire), RouteMap Refresh changeovers, and Geotab vehicle start/end.

**Public URL:** https://pgil26.github.io/fi-ops-dashboard/

## How it updates
- `data/latest.json` is the machine-readable snapshot (`asOf`, `generatedAt`, and all metrics).
- `scripts/build.py` renders `index.html` from `data/latest.json` (Python stdlib only, no build tooling).
- FI Ops Manager refreshes the snapshot on weekdays: write a new `data/latest.json`, run `python3 scripts/build.py`, commit, and push to `main`. GitHub Pages serves the `main` branch root.

Seeded with the Oct 8, 2026 consolidated digest.
