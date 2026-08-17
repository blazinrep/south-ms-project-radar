#!/usr/bin/env python3
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RELATIONSHIPS = ROOT / "data" / "company" / "relationships.json"
OPPORTUNITIES = ROOT / "data" / "intelligence" / "opportunities.json"
OUT = ROOT / "data" / "intelligence" / "relationship_matches.json"


def load(path):
    return json.loads(path.read_text())


def norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def opportunity_text(item):
    fields = [
        item.get("name"),
        item.get("displayName"),
        item.get("owner"),
        item.get("agency"),
        item.get("prime"),
        item.get("contractor"),
        item.get("description"),
        item.get("summary"),
        item.get("source")
    ]
    return norm(" ".join(str(v or "") for v in fields))


def main():
    relationship_data = (
        load(RELATIONSHIPS)
        if RELATIONSHIPS.exists()
        else {"version": "0.10.0", "relationships": []}
    )
    opportunities = load(OPPORTUNITIES)

    relationships = relationship_data.get("relationships", [])
    results = []

    for opportunity in opportunities:
        text = opportunity_text(opportunity)
        matches = []

        for rel in relationships:
            organization = norm(rel.get("organization"))

            if organization and organization in text:
                matches.append({
                    "organization": rel.get("organization"),
                    "contactName": rel.get("contactName"),
                    "role": rel.get("role"),
                    "relationship": rel.get("relationship"),
                    "strength": rel.get("strength"),
                    "referredBy": rel.get("referredBy"),
                    "performanceNote": rel.get("performanceNote"),
                    "lastInteraction": rel.get("lastInteraction"),
                    "nextFollowUp": rel.get("nextFollowUp")
                })

        if matches:
            edge = "relationship_edge"
        else:
            edge = "no_known_relationship"

        results.append({
            "projectId": opportunity.get("id"),
            "projectName": (
                opportunity.get("displayName")
                or opportunity.get("name")
            ),
            "relationshipStatus": edge,
            "matches": matches
        })

    OUT.write_text(json.dumps({
        "version": relationship_data.get("version", "0.10.0"),
        "relationshipsKnown": len(relationships),
        "opportunitiesChecked": len(opportunities),
        "projectsWithRelationshipEdge": sum(
            r["relationshipStatus"] == "relationship_edge"
            for r in results
        ),
        "projects": results
    }, indent=2) + "\n")

    print("RELATIONSHIP INTELLIGENCE")
    print("Known relationships:", len(relationships))
    print("Opportunities checked:", len(opportunities))
    print(
        "Relationship edges found:",
        sum(r["relationshipStatus"] == "relationship_edge" for r in results)
    )


if __name__ == "__main__":
    main()
