#!/usr/bin/env python3

from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"


NON_CONSTRUCTION_PHRASES = [
    "professional auditing",
    "janitorial services",
    "professional services",
    "engineering services",
    "architectural services",
    "energy service providers",
    "dispatch consoles",
    "camera systems"
]


def load(path):
    return json.loads(path.read_text())


def load_source(source_id):
    data = load(SOURCES)

    for source in data.get("sources", []):
        if source.get("id") == source_id:
            return source

    raise SystemExit(f"Unknown source id: {source_id}")


def extract_money(text):
    if not text:
        return None

    values = re.findall(
        r"\$([0-9][0-9,]*(?:\.\d{2})?)",
        text
    )

    if not values:
        return None

    numbers = []

    for value in values:
        try:
            numbers.append(float(value.replace(",", "")))
        except ValueError:
            pass

    return max(numbers) if numbers else None


def classify(name, detail):
    text = f"{name} {detail}".lower()

    for phrase in NON_CONSTRUCTION_PHRASES:
        if phrase in text:
            return "non_construction_or_professional"

    construction_signals = [
        "construction",
        "rehabilitation",
        "rehabilitiation",
        "repair",
        "replacement",
        "renovation",
        "improvements",
        "reroof",
        "roofing",
        "plumbing",
        "hvac",
        "mechanical",
        "electrical",
        "lighting",
        "concrete",
        "sidewalk",
        "bridge",
        "street",
        "paving",
        "asphalt",
        "drainage",
        "sewer",
        "water",
        "demolition",
        "framing",
        "masonry",
        "airport",
        "taxilane"
    ]

    if any(signal in text for signal in construction_signals):
        return "construction"

    return "review"


def normalize_project(item, source):
    name = item.get("name", "").strip()
    detail = item.get("detailText", "").strip()

    category = classify(name, detail)

    return {
        "id": item.get("id"),
        "name": name,
        "displayName": name,
        "owner": item.get("owner") or source.get("owner"),
        "country": item.get("country") or source.get("country", "US"),
        "state": item.get("state") or source.get("state"),
        "county": item.get("county") or source.get("county"),
        "city": item.get("city") or source.get("city"),
        "source": item.get("sourceUrl"),
        "sourceName": item.get("source") or source.get("name"),
        "sourceId": source.get("id"),
        "sourcePlatform": source.get("platform"),
        "sourceType": source.get("type"),
        "status": "published",
        "description": detail,
        "scope": [detail] if detail else [],
        "value": extract_money(detail),
        "discoveryType": item.get("discoveryType", "public_bid"),
        "recordClassification": category,
        "needsHumanReview": category == "review",
        "automation": {
            "collector": source.get("collector"),
            "normalizer": "normalize_planroom.py"
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    source = load_source(args.source)

    raw_path = (
        ROOT / "data" / "raw" /
        f'{source["id"]}_candidates.json'
    )

    if not raw_path.exists():
        raise SystemExit(
            f"Raw candidate file not found: {raw_path}"
        )

    raw = load(raw_path)
    projects = raw.get("projects", [])

    accepted = []
    review = []
    rejected = []

    for item in projects:
        project = normalize_project(item, source)
        classification = project["recordClassification"]

        if classification == "construction":
            accepted.append(project)
        elif classification == "review":
            review.append(project)
        else:
            rejected.append(project)

    out = (
        ROOT / "data" / "raw" /
        f'{source["id"]}_vertical_candidates.json'
    )

    out.write_text(json.dumps(accepted, indent=2) + "\n")

    review_out = (
        ROOT / "data" / "review" /
        f'{source["id"]}_normalization_review.json'
    )
    review_out.parent.mkdir(parents=True, exist_ok=True)

    review_out.write_text(json.dumps({
        "version": "0.12.0",
        "sourceId": source["id"],
        "review": review,
        "rejected": rejected
    }, indent=2) + "\n")

    print("PROJECT RADAR REUSABLE PLANROOM NORMALIZER")
    print("Source:", source["name"])
    print("Raw records:", len(projects))
    print("Construction candidates:", len(accepted))
    print("Needs review:", len(review))
    print("Rejected:", len(rejected))

    for project in accepted[:10]:
        print("-", project["name"])


if __name__ == "__main__":
    main()
