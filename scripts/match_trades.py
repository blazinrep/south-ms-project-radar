#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TRADES = ROOT / "config" / "trades.json"
PROJECTS = ROOT / "projects.json"
OPPORTUNITIES = ROOT / "data" / "intelligence" / "opportunities.json"
OVERRIDES = ROOT / "data" / "intelligence" / "research_overrides.json"
SCOPE_EVIDENCE = ROOT / "data" / "intelligence" / "scope_evidence.json"
OUT = ROOT / "data" / "intelligence" / "trade_matches.json"
COVERAGE_OUT = ROOT / "data" / "intelligence" / "trade_coverage_report.json"


def load(path):
    return json.loads(path.read_text())


def flatten_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(flatten_text(v) for v in value)
    if isinstance(value, dict):
        return " ".join(flatten_text(v) for v in value.values())
    return ""


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_term(text, term):
    needle = normalize(term)
    if not needle:
        return False

    # Match complete normalized words/phrases rather than arbitrary
    # substrings. This prevents short trade abbreviations such as
    # RTU, AHU or demo from matching inside unrelated words.
    haystack = f" {text} "
    phrase = f" {needle} "
    return phrase in haystack


def project_text(project, opportunity=None, override=None):
    fields = [
        project.get("name"),
        project.get("displayName"),
        project.get("scope"),
        project.get("description"),
        project.get("summary"),
        project.get("status"),
        project.get("owner"),
        opportunity,
        override,
    ]
    return normalize(" ".join(flatten_text(v) for v in fields))


def match_trade(text, key, trade):
    scope_hits = [
        term for term in trade.get("scopeTerms", [])
        if contains_term(text, term)
    ]

    strong_hits = [
        term for term in trade.get("strongSignals", [])
        if contains_term(text, term)
    ]

    exclusion_hits = [
        term for term in trade.get("exclusions", [])
        if contains_term(text, term)
    ]

    if exclusion_hits and not strong_hits:
        return None

    if not scope_hits and not strong_hits:
        return None

    specialist_context = any(
        term in text
        for term in [
            "well plugging",
            "orphaned well",
            "bridge replacement",
            "landfill liner",
            "geosynthetic liner"
        ]
    )

    score = len(scope_hits) + (len(strong_hits) * 3)

    if strong_hits and len(scope_hits) >= 2:
        confidence = "strong"
    elif len(scope_hits) >= 2 or strong_hits:
        confidence = "moderate"
    else:
        confidence = "possible"

    risk_flags = []

    # Specialist project types often contain generic supporting work
    # such as grading or earthwork. Do not let those generic signals
    # become a normal trade opportunity unless we also have a strong,
    # trade-specific scope signal.
    if specialist_context:
        risk_flags.append("specialist_project_context")
        if not strong_hits:
            confidence = "possible"

    if confidence == "strong":
        opportunity_summary = (
            f"{trade['label']} scope is clearly indicated by "
            f"{', '.join((strong_hits + scope_hits)[:4])}."
        )
        recommended_action = (
            "Open the source documents and identify the exact bid package, "
            "plans/spec sections, bidder list, and prime/subcontract path."
        )
        verify_first = False

    elif confidence == "moderate":
        opportunity_summary = (
            f"Relevant {trade['label'].lower()} scope appears in the project: "
            f"{', '.join(scope_hits[:4] or strong_hits[:4])}."
        )
        recommended_action = (
            "Verify the relevant plans/specs and determine whether this trade "
            "is bid directly or through a prime contractor."
        )
        verify_first = True

    else:
        opportunity_summary = (
            f"Possible {trade['label'].lower()} scope detected from "
            f"{', '.join(scope_hits[:3] or strong_hits[:3])}, "
            "but the package is not yet clear."
        )
        recommended_action = (
            "Verify trade-specific drawings/specifications before spending "
            "estimating time or contacting bidders."
        )
        verify_first = True

    if "specialist_project_context" in risk_flags:
        opportunity_summary += (
            " This is a specialist project type, so the trade match may only "
            "represent supporting work rather than a normal standalone package."
        )

    return {
        "tradeKey": key,
        "trade": trade["label"],
        "opportunityLabel": trade["opportunityLabel"],
        "confidence": confidence,
        "matchScore": score,
        "matchedScope": scope_hits,
        "strongSignals": strong_hits,
        "exclusionsFound": exclusion_hits,
        "qualificationGates": trade.get("qualificationGates", []),
        "riskFlags": risk_flags,
        "verifyFirst": verify_first,
        "opportunitySummary": opportunity_summary,
        "recommendedAction": recommended_action,
        "whyMatched": (
            f"Strong scope signal detected: {', '.join(strong_hits)}"
            if strong_hits
            else f"Relevant scope detected: {', '.join(scope_hits)}"
        )
    }


def main():
    trade_config = load(TRADES)
    projects = load(PROJECTS)

    opportunities = load(OPPORTUNITIES) if OPPORTUNITIES.exists() else []
    overrides = load(OVERRIDES) if OVERRIDES.exists() else {}
    scope_evidence = load(SCOPE_EVIDENCE) if SCOPE_EVIDENCE.exists() else {"projects":[]}

    evidence_by_id = {
        p.get("projectId"): p.get("evidence", [])
        for p in scope_evidence.get("projects", [])
        if isinstance(p, dict) and p.get("projectId")
    }

    opportunity_by_id = {
        p.get("id"): p
        for p in opportunities
        if isinstance(p, dict) and p.get("id")
    }

    override_projects = overrides.get("projects", {}) if isinstance(overrides, dict) else {}

    results = []

    for project in projects:
        project_id = project.get("id")
        opportunity = opportunity_by_id.get(project_id, {})

        override = override_projects.get(project_id, {})

        if not override and isinstance(opportunity, dict):
            canonical_key = (
                opportunity.get("intelligence", {})
                .get("canonicalProjectKey")
            )
            if canonical_key:
                override = override_projects.get(canonical_key, {})

        evidence = evidence_by_id.get(project_id, [])
        evidence_text = " ".join(
            str(item.get("text", ""))
            for item in evidence
            if isinstance(item, dict)
        )

        text = project_text(project, opportunity, override)
        if evidence_text:
            text = normalize(text + " " + evidence_text)

        matches = []

        for key, trade in trade_config["trades"].items():
            match = match_trade(text, key, trade)
            if match:
                matches.append(match)

        matches.sort(
            key=lambda m: (
                -m["matchScore"],
                m["trade"]
            )
        )

        if matches:
            results.append({
                "projectId": project.get("id"),
                "projectName": project.get("displayName") or project.get("name"),
                "owner": project.get("owner"),
                "county": project.get("county"),
                "status": project.get("status"),
                "source": project.get("source"),
                "tradeMatches": matches
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": trade_config["version"],
        "projectCount": len(projects),
        "matchedProjectCount": len(results),
        "projects": results
    }

    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    coverage = {}
    for key, trade in trade_config["trades"].items():
        trade_matches = [
            m
            for project in results
            for m in project["tradeMatches"]
            if m["tradeKey"] == key
        ]

        coverage[key] = {
            "trade": trade["label"],
            "total": len(trade_matches),
            "strong": sum(m["confidence"] == "strong" for m in trade_matches),
            "moderate": sum(m["confidence"] == "moderate" for m in trade_matches),
            "possible": sum(m["confidence"] == "possible" for m in trade_matches),
            "verifyFirst": sum(bool(m["verifyFirst"]) for m in trade_matches)
        }

    coverage_payload = {
        "version": trade_config["version"],
        "projectsScanned": len(projects),
        "trades": coverage
    }

    COVERAGE_OUT.write_text(
        json.dumps(coverage_payload, indent=2) + "\n"
    )

    print("V0.10 TRADE MATCHER")
    print("Projects scanned:", len(projects))
    print("Projects with trade matches:", len(results))

    for row in results[:10]:
        print()
        print(row["projectName"])
        for match in row["tradeMatches"]:
            print(
                f"  - {match['trade']} | "
                f"{match['confidence']} | "
                f"score={match['matchScore']} | "
                f"{', '.join(match['matchedScope'][:5])}"
            )


if __name__ == "__main__":
    main()
