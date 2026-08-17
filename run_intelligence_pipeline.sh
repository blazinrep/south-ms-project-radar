#!/usr/bin/env bash
set -euo pipefail

python3 scripts/build_opportunity_intelligence.py
python3 scripts/build_scope_evidence.py
python3 scripts/match_trades.py
python3 scripts/match_relationships.py
python3 scripts/build_pursuit_cards.py

echo "V0.10 opportunity intelligence pipeline complete."
echo "Review:"
echo "  data/intelligence/pursuit_cards.json"
echo "  data/intelligence/trade_matches.json"
echo "  data/intelligence/trade_coverage_report.json"
echo "  data/intelligence/relationship_matches.json"
echo "  data/intelligence/scope_evidence.json"
