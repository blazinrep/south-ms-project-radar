#!/usr/bin/env bash
set -e
mkdir -p data/raw data/snapshots state
python3 collectors/fetch_mdot_live.py
python3 collectors/mdot_proposed.py
python3 scripts/merge_candidates.py
python3 scripts/detect_changes.py
echo "Live MDOT pipeline complete."
