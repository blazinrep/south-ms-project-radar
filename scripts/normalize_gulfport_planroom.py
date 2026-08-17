#!/usr/bin/env python3

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "gulfport_planroom_candidates.json"
OUT = ROOT / "data" / "raw" / "gulfport_vertical_candidates.json"


def load(path):
    return json.loads(path.read_text())


def extract_money(text):
    if not text:
        return None
    m = re.search(r"\$([0-9][0-9,]*(?:\.\d{2})?)", text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except Exception:
        return None


def classify(name, detail):
    text = f"{name} {detail}".lower()

    if any(x in text for x in [
        "engineering services",
        "professional auditing",
        "janitorial services",
        "energy service providers",
        "dispatch consoles",
        "camera systems"
    ]):
        return "non_construction_or_professional"

    return "construction"


def main():
    raw = load(RAW)

    results = []

    for item in raw.get("projects", []):
        name = item.get("name", "")
        detail = item.get("detailText", "")
        category = classify(name, detail)

        if category != "construction":
            continue

        results.append({
            "id": item.get("id"),
            "name": name,
            "displayName": name,
            "owner": item.get("owner"),
            "city": item.get("city"),
            "state": item.get("state"),
            "county": "Harrison",
            "source": item.get("sourceUrl"),
            "sourceName": item.get("source"),
            "sourceType": item.get("sourceType"),
            "status": "published",
            "description": detail,
            "scope": [detail] if detail else [],
            "value": extract_money(detail),
            "discoveryType": item.get("discoveryType"),
            "automation": {
                "collector": "collect_gulfport_planroom.py",
                "normalizer": "normalize_gulfport_planroom.py"
            }
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n")

    print("V0.11 GULFPORT NORMALIZER")
    print("Construction candidates:", len(results))

    for p in results:
        print("-", p["name"])


if __name__ == "__main__":
    main()
