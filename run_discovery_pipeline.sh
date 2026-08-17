#!/usr/bin/env bash
set -euo pipefail

python3 scripts/run_configured_sources.py
python3 scripts/build_source_records.py
python3 scripts/discover_project_documents.py
python3 scripts/build_scope_evidence.py
python3 scripts/match_trades.py
python3 scripts/analyze_source_gaps.py

echo
echo "PROJECT RADAR NATIONAL DISCOVERY PIPELINE COMPLETE"
echo "Review:"
echo "  data/intelligence/source_health.json"
echo "  data/intelligence/source_records.json"
echo "  data/intelligence/document_discovery.json"
echo "  data/intelligence/scope_evidence.json"
echo "  data/intelligence/trade_matches.json"
echo "  data/intelligence/trade_coverage_report.json"
echo "  data/intelligence/source_gap_report.json"
