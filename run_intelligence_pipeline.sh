#!/usr/bin/env bash
set -euo pipefail

echo "PROJECT RADAR INTELLIGENCE PIPELINE"
echo "==================================="

python3 scripts/select_sources_for_contractor.py
python3 scripts/build_source_records.py
python3 scripts/apply_geo_fallbacks.py
python3 scripts/build_canonical_projects.py
python3 scripts/build_opportunity_intelligence.py
python3 scripts/build_scope_evidence.py
python3 scripts/match_trades.py
python3 scripts/match_relationships.py
python3 scripts/build_pursuit_cards.py

echo
echo "V0.15 unified opportunity intelligence pipeline complete."
echo "Review:"
echo "  data/intelligence/canonical_projects.json"
echo "  data/intelligence/opportunities.json"
echo "  data/intelligence/pursuit_cards.json"
echo "  data/intelligence/trade_matches.json"
echo "  data/intelligence/trade_coverage_report.json"
echo "  data/intelligence/relationship_matches.json"
echo "  data/intelligence/scope_evidence.json"
