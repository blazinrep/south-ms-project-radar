# Project Radar V0.5.2 — Live MDOT Automation

This upgrade replaces the static MDOT source snapshot with live retrieval from MDOT's official Proposed Lettings page.

## Pipeline
1. `fetch_mdot_live.py` downloads the official page with Python standard library.
2. A resilient HTML table parser finds proposed-project rows.
3. Results are filtered to the South Mississippi coverage counties.
4. `mdot_proposed.py` normalizes them into neutral Project Radar records.
5. `merge_candidates.py` merges them into the existing `projects.json`.
6. `detect_changes.py` emits `changes.json`.
7. GitHub Actions can run this automatically every day.

## Safety behavior
If the MDOT page changes and the parser returns zero target records, the collector exits with an error and DOES NOT overwrite the last good JSON snapshot.

## Local run
`./run_mdot_pipeline.sh`

## GitHub automation
`.github/workflows/update-mdot.yml` runs daily at 11:17 UTC and can also be run manually from GitHub Actions.

Before enabling automated writes, make sure GitHub repository Settings → Actions → General → Workflow permissions allows Read and write permissions.

## Important
The workflow may update timestamp fields even when the underlying MDOT project list is unchanged. A later hardening pass should separate source-retrieval metadata from semantic project fingerprints so routine fetch timestamps never look like opportunity changes.
