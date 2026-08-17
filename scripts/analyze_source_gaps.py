#!/usr/bin/env python3

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

TRADES = ROOT / "config" / "trades.json"
COVERAGE = ROOT / "data" / "intelligence" / "trade_coverage_report.json"
SOURCES = ROOT / "config" / "sources.json"
OUT = ROOT / "data" / "intelligence" / "source_gap_report.json"


def load(path):
    return json.loads(path.read_text())


def main():
    trades = load(TRADES)
    coverage = load(COVERAGE)
    sources = load(SOURCES)

    coverage_by_trade = coverage.get("trades", {})
    results = []

    for trade_id, trade in trades.get("trades", {}).items():
        stats = coverage_by_trade.get(trade_id, {})

        total = stats.get("total", 0)
        strong = stats.get("strong", 0)
        moderate = stats.get("moderate", 0)
        possible = stats.get("possible", 0)

        supporting_sources = []

        for source in sources.get("sources", []):
            bias = source.get("tradeBias", [])
            if "all" in bias or trade_id in bias:
                supporting_sources.append(source.get("name"))

        if total == 0:
            gap = "critical"
        elif strong == 0 and moderate == 0:
            gap = "high"
        elif strong == 0:
            gap = "medium"
        else:
            gap = "covered"

        results.append({
            "tradeId": trade_id,
            "trade": trade.get("label", trade_id),
            "coverageGap": gap,
            "matches": total,
            "strong": strong,
            "moderate": moderate,
            "possible": possible,
            "supportingSources": supporting_sources
        })

    order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "covered": 3
    }

    results.sort(
        key=lambda x: (
            order[x["coverageGap"]],
            x["matches"]
        )
    )

    payload = {
        "version": "0.11.0",
        "projectsScanned": coverage.get("projectsScanned"),
        "sourceCount": len(sources.get("sources", [])),
        "tradeGaps": results
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    print("V0.11 SOURCE GAP ANALYSIS")
    print("-------------------------")

    for item in results:
        print(
            f'{item["coverageGap"].upper():8} | '
            f'{item["trade"]}: '
            f'{item["matches"]} matches | '
            f'{item["strong"]} strong | '
            f'{item["moderate"]} moderate'
        )


if __name__ == "__main__":
    main()
