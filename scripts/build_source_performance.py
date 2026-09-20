#!/usr/bin/env python3

from pathlib import Path
from collections import defaultdict
import json

ROOT = Path(__file__).resolve().parents[1]
INTEL = ROOT / "data" / "intelligence"
RAW = ROOT / "data" / "raw"

SOURCE_RECORDS = INTEL / "source_records.json"
GEOCODED = INTEL / "source_records_geocoded.json"
OPPORTUNITIES = INTEL / "opportunities.json"
TRADE_MATCHES = INTEL / "trade_matches.json"
DUPLICATES = INTEL / "duplicates.json"
OUT = INTEL / "source_performance.json"

HIGH_PRIORITY = {
    "act_today",
    "pursue_now",
    "verify_then_pursue"
}


def load(path):
    return json.loads(path.read_text())


def pct(n, d):
    if not d:
        return None
    return round((n / d) * 100, 1)


def raw_count(source_id):
    if source_id == "legacy_projects":
        return None

    path = RAW / f"{source_id}_candidates.json"

    if not path.exists():
        return None

    payload = load(path)

    if isinstance(payload, list):
        return len(payload)

    if isinstance(payload, dict):
        if isinstance(payload.get("projects"), list):
            return len(payload["projects"])
        if isinstance(payload.get("records"), list):
            return len(payload["records"])
        for key in ("count", "recordCount"):
            if isinstance(payload.get(key), int):
                return payload[key]

    return None


def main():
    source_records = load(SOURCE_RECORDS)["records"]
    geocoded_records = load(GEOCODED)["records"]
    opportunities = load(OPPORTUNITIES)

    geocoded_by_id = {
        r.get("id"): r
        for r in geocoded_records
        if r.get("id")
    }

    trade_payload = load(TRADE_MATCHES)
    trade_project_ids = {
        p.get("projectId")
        for p in trade_payload.get("projects", [])
        if p.get("projectId")
    }

    duplicate_groups = load(DUPLICATES)
    duplicate_ids = set()

    for group in duplicate_groups:
        selected = group.get("selectedRecordId")
        if selected:
            duplicate_ids.add(selected)

        duplicate_ids.update(group.get("duplicateRecordIds") or [])

    by_source = defaultdict(list)

    for record in source_records:
        by_source[record.get("sourceFeed", "unknown")].append(record)

    opps_by_source = defaultdict(list)

    for project in opportunities:
        opps_by_source[
            project.get("sourceFeed", "unknown")
        ].append(project)

    results = []

    for source_id, records in sorted(by_source.items()):
        ingest = len(records)
        raw = raw_count(source_id)

        native_deadline = sum(
            bool(r.get("deadline") or r.get("proposalDeadline"))
            for r in records
        )

        native_geo = sum(
            r.get("lat") is not None and r.get("lon") is not None
            for r in records
        )

        native_location = sum(
            bool(
                r.get("city")
                or r.get("county")
                or r.get("locationText")
            )
            for r in records
        )

        CLOSED_STATUSES = {
            "bidding closed",
            "closed",
            "awarded",
            "cancelled",
            "canceled"
        }

        ACTIVE_STATUSES = {
            "accepting bids",
            "open",
            "active"
        }

        PRECONSTRUCTION_STATUSES = {
            "announced",
            "announced / pre-construction",
            "pre-construction",
            "preconstruction",
            "planning",
            "permitting",
            "funded",
            "design"
        }

        PRECONSTRUCTION_LIFECYCLE_STAGES = {
            "signal",
            "announced",
            "pre_construction",
            "pre-construction",
            "planning",
            "permitting",
            "funded",
            "design",
            "future_letting"
        }

        def is_preconstruction(record):
            status = str(record.get("status") or "").strip().lower()
            lifecycle = str(
                record.get("lifecycleStage") or ""
            ).strip().lower()
            signal_stage = str(
                record.get("signalStage") or ""
            ).strip().lower()

            return (
                status in PRECONSTRUCTION_STATUSES
                or lifecycle in PRECONSTRUCTION_LIFECYCLE_STAGES
                or signal_stage in PRECONSTRUCTION_LIFECYCLE_STAGES
            )

        closed_historical = sum(
            str(r.get("status") or "").lower() in CLOSED_STATUSES
            for r in records
        )

        confirmed_active = sum(
            str(r.get("status") or "").lower() in ACTIVE_STATUSES
            for r in records
        )

        preconstruction = sum(
            is_preconstruction(r)
            and str(r.get("status") or "").lower() not in CLOSED_STATUSES
            and str(r.get("status") or "").lower() not in ACTIVE_STATUSES
            for r in records
        )

        recency_unknown = (
            ingest
            - closed_historical
            - confirmed_active
            - preconstruction
        )

        enriched_geo = 0
        exact_geo = 0
        approximate_geo = 0
        unresolved_geo = 0

        for r in records:
            g = geocoded_by_id.get(r.get("id"), {})

            if g.get("lat") is not None and g.get("lon") is not None:
                enriched_geo += 1

            precision = g.get("geoPrecision")

            if precision == "project_coordinates":
                exact_geo += 1
            elif precision == "county_centroid":
                approximate_geo += 1
            else:
                unresolved_geo += 1

        scope_count = sum(
            bool(
                r.get("scope")
                or r.get("description")
                or r.get("summary")
                or r.get("why")
            )
            for r in records
        )

        trade_count = sum(
            r.get("id") in trade_project_ids
            for r in records
        )

        duplicate_count = sum(
            r.get("id") in duplicate_ids
            for r in records
        )

        source_opps = opps_by_source.get(source_id, [])

        high_priority = [
            p for p in source_opps
            if (p.get("intelligence") or {}).get("decision")
            in HIGH_PRIORITY
        ]

        action_scores = [
            (p.get("intelligence") or {})
            .get("scores", {})
            .get("actionPriority")
            for p in source_opps
        ]

        action_scores = [
            x for x in action_scores
            if isinstance(x, (int, float))
        ]

        dup_rate = pct(duplicate_count, ingest)

        results.append({
            "sourceId": source_id,
            "ingestVolume": ingest,
            "rawDiscoveryVolume": raw,
            "normalizationSuccessRate": (
                pct(ingest, raw)
                if raw is not None
                else None
            ),

            "deadlineCoverage": {
                "nativeCount": native_deadline,
                "nativeRate": pct(native_deadline, ingest)
            },

            "geoCoverage": {
                "nativeCoordinateCount": native_geo,
                "nativeCoordinateRate": pct(native_geo, ingest),
                "nativeLocationMetadataCount": native_location,
                "nativeLocationMetadataRate": pct(native_location, ingest),
                "enrichedCount": enriched_geo,
                "enrichedRate": pct(enriched_geo, ingest),
                "exactCount": exact_geo,
                "approximateCount": approximate_geo,
                "unresolvedCount": unresolved_geo
            },

            "scopeCoverage": {
                "count": scope_count,
                "rate": pct(scope_count, ingest)
            },

            "tradeMatchRate": {
                "count": trade_count,
                "rate": pct(trade_count, ingest)
            },

            "duplicateInvolvement": {
                "count": duplicate_count,
                "rate": dup_rate
            },

            "approximateUniquenessRate": (
                round(100 - dup_rate, 1)
                if dup_rate is not None
                else None
            ),

            "recordStatus": {
                "confirmedActiveCount": confirmed_active,
                "preconstructionCount": preconstruction,
                "closedHistoricalCount": closed_historical,
                "recencyUnknownCount": recency_unknown
            },

            "canonicalOpportunityCount": len(source_opps),

            "highPriorityYield": {
                "count": len(high_priority),
                "rate": pct(
                    len(high_priority),
                    len(source_opps)
                )
            },

            "averageActionPriority": (
                round(
                    sum(action_scores) / len(action_scores),
                    1
                )
                if action_scores
                else None
            ),

            "freshnessLagDays": None,
            "freshnessStatus": "not_yet_measurable",

            "behaviorMetrics": {
                "opened": None,
                "contacted": None,
                "estimateStarted": None,
                "submitted": None,
                "won": None,
                "lost": None,
                "contractValueWon": None
            }
        })

    payload = {
        "version": "0.16.4",
        "sourceCount": len(results),
        "notes": [
            "Native metadata is measured before Radar enrichment.",
            "Enriched geography includes Radar county-centroid fallbacks.",
            "legacy_projects still combines older source families.",
            "preconstruction recognizes announced, planning, permitting, funded, design, and future-letting signals.",
            "freshness and behavior metrics are not yet active."
        ],
        "sources": results
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    print("V0.16.4 SOURCE PERFORMANCE")
    print("--------------------------")

    for s in results:
        geo = s["geoCoverage"]
        deadline = s["deadlineCoverage"]

        print()
        print(s["sourceId"])
        print("  ingest:", s["ingestVolume"])
        print("  native deadline:", deadline["nativeRate"], "%")
        print(
            "  native coordinates:",
            geo["nativeCoordinateRate"],
            "%"
        )
        print(
            "  native location metadata:",
            geo["nativeLocationMetadataRate"],
            "%"
        )
        print("  enriched geo:", geo["enrichedRate"], "%")
        print(
            "  geo precision:",
            f'exact={geo["exactCount"]}',
            f'approx={geo["approximateCount"]}',
            f'unresolved={geo["unresolvedCount"]}'
        )
        print("  scope coverage:", s["scopeCoverage"]["rate"], "%")
        print("  trade match:", s["tradeMatchRate"]["rate"], "%")
        print("  uniqueness:", s["approximateUniquenessRate"], "%")
        print(
            "  records:",
            f'active={s["recordStatus"]["confirmedActiveCount"]}',
            f'preconstruction={s["recordStatus"]["preconstructionCount"]}',
            f'historical={s["recordStatus"]["closedHistoricalCount"]}',
            f'unknown={s["recordStatus"]["recencyUnknownCount"]}'
        )
        print(
            "  high priority active:",
            s["highPriorityYield"]["count"],
            "/",
            s["canonicalOpportunityCount"]
        )
        print("  avg action priority:", s["averageActionPriority"])


if __name__ == "__main__":
    main()
