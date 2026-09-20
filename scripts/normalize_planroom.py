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



MONTHS = {
    "Jan": 1, "January": 1,
    "Feb": 2, "February": 2,
    "Mar": 3, "March": 3,
    "Apr": 4, "April": 4,
    "May": 5,
    "Jun": 6, "June": 6,
    "Jul": 7, "July": 7,
    "Aug": 8, "August": 8,
    "Sep": 9, "Sept": 9, "September": 9,
    "Oct": 10, "October": 10,
    "Nov": 11, "November": 11,
    "Dec": 12, "December": 12
}


def parse_planroom_datetime(label, text):
    if not text:
        return None, None

    pattern = re.compile(
        rf"\b{re.escape(label)}\s+"
        r"(?P<month>"
        + "|".join(sorted(MONTHS.keys(), key=len, reverse=True))
        + r")\s+"
        r"(?P<day>\d{1,2}),\s+"
        r"(?P<year>\d{4})\s+"
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2})"
        r"(?P<ampm>am|pm)\b",
        re.I
    )

    match = pattern.search(text)

    if not match:
        return None, None

    month_text = match.group("month")
    month_key = next(
        (k for k in MONTHS if k.lower() == month_text.lower()),
        None
    )

    if not month_key:
        return None, None

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    ampm = match.group("ampm").lower()

    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0

    value = (
        f'{match.group("year")}-'
        f'{MONTHS[month_key]:02d}-'
        f'{int(match.group("day")):02d}T'
        f'{hour:02d}:{minute:02d}:00'
    )

    start = max(0, match.start() - 55)
    end = min(len(text), match.end() + 55)

    evidence = " ".join(text[start:end].split())

    return value, evidence


def extract_status(text):
    if not text:
        return None, None

    match = re.search(
        r"\bStatus\s+"
        r"(Accepting Bids|Bidding Closed|Closed|Open|Awarded|Cancelled|Canceled)",
        text,
        re.I
    )

    if not match:
        return None, None

    value = match.group(1).strip()

    start = max(0, match.start() - 35)
    end = min(len(text), match.end() + 35)

    evidence = " ".join(text[start:end].split())

    return value, evidence


def extract_location(text):
    if not text:
        return None, None, None

    match = re.search(
        r"\bLocation\s+(.{2,160}?)(?:\s+Open in Google Maps|\s+Reference|\s+Notice|\s+Details)",
        text,
        re.I
    )

    if not match:
        return None, None, None

    location = " ".join(match.group(1).split()).strip()

    city_match = re.search(
        r"\b([A-Za-z][A-Za-z .'-]{1,50}),\s*MS\b",
        location
    )

    city = city_match.group(1).strip() if city_match else None

    evidence = " ".join(
        text[max(0, match.start() - 20):min(len(text), match.end() + 20)].split()
    )

    return location, city, evidence


def parse_natural_prebid(text):
    if not text:
        return None, None

    pattern = re.compile(
        r"(?:Pre[- ]?Bid(?: Meeting| Conference)?).*?"
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*"
        r"(?:a\.?m\.?|p\.?m\.?)\s+on\s+"
        r"(?P<month>"
        + "|".join(sorted(MONTHS.keys(), key=len, reverse=True))
        + r")\s+"
        r"(?P<day>\d{1,2}),\s+"
        r"(?P<year>\d{4})",
        re.I
    )

    match = pattern.search(text)

    if not match:
        return None, None

    matched = match.group(0)
    pm = bool(re.search(r"p\.?m\.?", matched, re.I))

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))

    if pm and hour != 12:
        hour += 12
    elif not pm and hour == 12:
        hour = 0

    month_text = match.group("month")
    month_key = next(
        k for k in MONTHS
        if k.lower() == month_text.lower()
    )

    value = (
        f'{match.group("year")}-'
        f'{MONTHS[month_key]:02d}-'
        f'{int(match.group("day")):02d}T'
        f'{hour:02d}:{minute:02d}:00'
    )

    start = max(0, match.start() - 45)
    end = min(len(text), match.end() + 55)

    evidence = " ".join(text[start:end].split())

    return value, evidence


def extract_planroom_metadata(detail):
    deadline, deadline_evidence = parse_planroom_datetime("Bid", detail)
    prebid, prebid_evidence = parse_planroom_datetime("Prebid", detail)

    if not prebid:
        prebid, prebid_evidence = parse_natural_prebid(detail)

    status, status_evidence = extract_status(detail)
    location_text, city, location_evidence = extract_location(detail)

    # ReproConnect address text sometimes leaves the street suffix
    # immediately before the city, e.g. "215 E Government, St Brandon, MS".
    # Avoid treating that suffix as part of the city name.
    if city and city.lower().startswith("st ") and location_text:
        if any(ch.isdigit() for ch in location_text):
            city = city[3:].strip()

    return {
        "deadline": deadline,
        "prebid": prebid,
        "status": status,
        "locationText": location_text,
        "city": city,
        "evidence": {
            "deadline": deadline_evidence,
            "prebid": prebid_evidence,
            "status": status_evidence,
            "location": location_evidence
        }
    }


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

    metadata = extract_planroom_metadata(detail)

    city = (
        item.get("city")
        or metadata.get("city")
        or source.get("city")
    )

    return {
        "id": item.get("id"),
        "name": name,
        "displayName": name,
        "owner": item.get("owner") or source.get("owner"),
        "country": item.get("country") or source.get("country", "US"),
        "state": item.get("state") or source.get("state"),
        "county": item.get("county") or source.get("county"),
        "city": city,
        "locationText": metadata.get("locationText"),
        "source": item.get("sourceUrl"),
        "sourceName": item.get("source") or source.get("name"),
        "sourceId": source.get("id"),
        "sourcePlatform": source.get("platform"),
        "sourceType": source.get("type"),
        "status": metadata.get("status") or "published",
        "deadline": metadata.get("deadline"),
        "prebid": metadata.get("prebid"),
        "description": detail,
        "scope": [detail] if detail else [],
        "value": extract_money(detail),
        "discoveryType": item.get("discoveryType", "public_bid"),
        "recordClassification": category,
        "needsHumanReview": category == "review",
        "sourceEvidence": metadata.get("evidence"),
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
        "version": "0.16.2",
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
