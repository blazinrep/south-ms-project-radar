#!/usr/bin/env bash
set -euo pipefail
python3 scripts/build_opportunity_intelligence.py
python3 scripts/build_pursuit_cards.py
echo "V0.9.3 opportunity intelligence + pursuit cards complete."
echo "Review: data/intelligence/pursuit_cards.json"
