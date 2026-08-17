#!/usr/bin/env python3
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects.json"
OPPS = ROOT / "data" / "intelligence" / "opportunities.json"
OVERRIDES = ROOT / "data" / "intelligence" / "research_overrides.json"
OUT = ROOT / "data" / "intelligence" / "scope_evidence.json"


def load(path):
    return json.loads(path.read_text())


def main():
    projects = load(PROJECTS)
    opps = load(OPPS) if OPPS.exists() else []
    overrides = load(OVERRIDES) if OVERRIDES.exists() else {}

    opp_by_id = {
        x.get("id"): x
        for x in opps
        if isinstance(x, dict) and x.get("id")
    }

    override_projects = (
        overrides.get("projects", {})
        if isinstance(overrides, dict)
        else {}
    )

    results = []

    for project in projects:
        pid = project.get("id")
        opp = opp_by_id.get(pid, {})

        canonical = (
            (opp.get("intelligence") or {}).get("canonicalProjectKey")
            if isinstance(opp, dict)
            else None
        )

        override = override_projects.get(pid, {})
        if not override and canonical:
            override = override_projects.get(canonical, {})

        evidence = []

        def add(source, value):
            if not value:
                return
            if isinstance(value, list):
                for item in value:
                    add(source, item)
                return
            if isinstance(value, dict):
                for key, item in value.items():
                    add(f"{source}.{key}", item)
                return

            text = str(value).strip()
            if text and len(text) >= 3:
                evidence.append({
                    "source": source,
                    "text": text
                })

        add("project.name", project.get("name"))
        add("project.displayName", project.get("displayName"))
        add("project.scope", project.get("scope"))
        add("project.description", project.get("description"))
        add("project.summary", project.get("summary"))

        if isinstance(opp, dict):
            intel = opp.get("intelligence") or {}
            add("intelligence.fitEvidence", intel.get("fitEvidence"))
            add("intelligence.whyItMatters", intel.get("whyItMatters"))
            add("intelligence.nextAction", intel.get("nextAction"))
            add("intelligence.recommendedContact", intel.get("recommendedContact"))
            add("opportunity.scope", opp.get("scope"))
            add("opportunity.description", opp.get("description"))

        add("researchOverride", override)

        results.append({
            "projectId": pid,
            "projectName": project.get("displayName") or project.get("name"),
            "evidenceCount": len(evidence),
            "evidence": evidence
        })

    OUT.write_text(json.dumps({
        "version": "0.10.0",
        "projectCount": len(results),
        "projects": results
    }, indent=2) + "\n")

    print("SCOPE EVIDENCE EXTRACTION")
    print("Projects processed:", len(results))
    print(
        "Evidence items:",
        sum(item["evidenceCount"] for item in results)
    )


if __name__ == "__main__":
    main()
