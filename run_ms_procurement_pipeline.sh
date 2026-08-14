#!/usr/bin/env bash
set -euo pipefail
mkdir -p data/raw data/review state
python3 collectors/monitor_ms_procurement.py
python3 scripts/merge_ms_procurement.py
echo "Resilient Mississippi procurement monitor complete."
