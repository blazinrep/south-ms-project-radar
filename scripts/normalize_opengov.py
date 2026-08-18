#!/usr/bin/env python3

from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"

NON_CONSTRUCTION = [
    "auditing services",
    "milk and dairy",
    "bread and baked goods",
    "food safety",
    "software",
    "technology solutions",
    "telecommunication systems",
    "financing",
    "insurance services",
    "janitorial services"
]

CONSTRUCTION_SIGNALS = [
    "construction",
    "repair",
    "replacement",
    "rehabilitation",
    "renovation",
    "improvements",
    "bridge",
    "road",
    "street",
    "sidewalk",
    "paving",
    "asphalt",
    "concrete",
    "drainage",
    "sewer",
    "water",
    "roof",
    "hvac",
    "mechanical",
    "plumbing",
    "electrical",
    "lighting",
    "structural",
    "building",
    "demolition",
    "site",
    "grading",
    "excavation",
    "access control",
    "doors",
    "lock",
    "dam",
    "utility",
    "stormwater",
    "traffic signal"
]

ACTIVE_STATUSES = {
    "open",
    "coming_soon",
    "draft"
}


def load(path):
    return json.loads(path.read_text())


def load_source(source_id):
    data = load(SOURCES)
    for source in data.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise SystemExit(f"Unknown source id: {source_id}")


def classify(project):
    text = " ".join([
        str(project.get("name") or ""),
        str(project.get("summary") or ""),
        str(project.get("description") or "")
    ]).lower()

    if any(x in text for x in NON_CONSTRUCTION):
        return "non_construction"

    if any(x in text for x in CONSTRUCTION_SIGNALS):
        return "construction"

    return "review"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    source = load_source(args.source)

    raw_path = ROOT / "data" / "raw" / f'{source["id"]}_candidates.json'

    if not raw_path.exists():
        raise SystemExit(f"Raw candidate file not found: {raw_path}")

    raw = load(raw_path)
    projects = raw.get("projects", [])

    accepted = []
    review = []
    rejected = []

    for project in projects:
        classification = classify(project)
        status = str(project.get("status") or "").lower()

        normalized = dict(project)
        normalized["recordClassification"] = classification
        normalized["needsHumanReview"] = classification == "review"
        normalized["isCurrentlyActionable"] = status in ACTIVE_STATUSES
        normalized["automation"] = {
            "collector": "collect_opengov.py",
            "normalizer": "normalize_opengov.py"
        }

        if classification == "construction" and status in ACTIVE_STATUSES:
            accepted.append(normalized)
        elif classification == "review" and status in ACTIVE_STATUSES:
            review.append(normalized)
        else:
            rejected.append(normalized)

    out = ROOT / "data" / "raw" / f'{source["id"]}_vertical_candidates.json'
    out.write_text(json.dumps(accepted, indent=2) + "\n")

    review_out = ROOT / "data" / "review" / f'{source["id"]}_normalization_review.json'
    review_out.parent.mkdir(parents=True, exist_ok=True)

    review_out.write_text(json.dumps({
        "version": "0.14.0",
        "sourceId": source["id"],
        "accepted": len(accepted),
        "review": review,
        "rejected": rejected
    }, indent=2) + "\n")

    print("PROJECT RADAR OPENGOV NORMALIZER")
    print("Source:", source["name"])
    print("Raw records:", len(projects))
    print("Active construction candidates:", len(accepted))
    print("Active needs review:", len(review))
    print("Rejected / inactive:", len(rejected))

    for project in accepted[:10]:
        print("-", project["name"])


if __name__ == "__main__":
    main()
