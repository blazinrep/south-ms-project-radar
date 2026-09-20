#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"

POSITIVE_TITLE_TERMS = (
    "expand",
    "expansion",
    "locating",
    "locates",
    "establishing",
    "establishes",
    "operations",
    "facility",
    "manufactur",
    "plant",
    "sawmill",
    "terminal",
    "invest",
    "jobs",
    "bringing",
    "bring ",
    "opens",
    "opening",
)

NEGATIVE_TITLE_TERMS = (
    "grant program",
    "accepting applications",
    "workshop",
    "business forum",
    "tax climate",
    "by the numbers",
    "branding campaign",
    "economic development week",
    "award",
    "invited to",
    "applications for",
)

COUNTY_RE = re.compile(
    r"\b([A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*){0,2}) County\b"
)

MONEY_RE = re.compile(
    r"\$([0-9][0-9,]*(?:\.[0-9]+)?)\s*(billion|million|thousand)?",
    re.I,
)

JOBS_RE = re.compile(
    r"(?:create|creating|add|adding|support|supporting|retain|retaining|"
    r"bring|bringing|generate|generating)"
    r"(?:\s+more than|\s+over|\s+approximately|\s+about|\s+nearly|\s+up to)?"
    r"\s+([0-9][0-9,]*)\s+(?:new\s+)?jobs\b",
    re.I,
)

SQFT_PATTERNS = (
    re.compile(
        r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s*[- ]square[- ]foot\b",
        re.I,
    ),
    re.compile(
        r"\b([0-9][0-9,]*(?:\.[0-9]+)?)\s+square feet\b",
        re.I,
    ),
)

TRADE_TERMS = {
    "excavation": ("excavation", "earthwork"),
    "grading": ("grading", "site grading"),
    "drainage": ("drainage", "stormwater", "storm water"),
    "clearing": ("clearing", "site clearing"),
    "erosion_control": ("erosion control",),
    "hauling": ("hauling",),
    "utilities": ("utilities", "utility installation", "water line", "sewer line"),
}


def load(path):
    return json.loads(path.read_text())


def load_source(source_id):
    data = load(SOURCES)

    for source in data.get("sources", []):
        if source.get("id") == source_id:
            return source

    raise SystemExit(f"Unknown source id: {source_id}")


def slugify(value):
    value = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower())
    return value.strip("-")


def parse_date(value):
    if not value:
        return None

    value = str(value).strip()

    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass

    if re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]

    return value


def title_is_project(title):
    low = title.lower()

    if any(term in low for term in NEGATIVE_TITLE_TERMS):
        return False

    return any(term in low for term in POSITIVE_TITLE_TERMS)


def clean_company_prefix(value):
    value = re.sub(
        r"^(technology company|wire and cable manufacturer|defense technology leader|"
        r"defense systems manufacturer|manufacturer|company)\s+",
        "",
        value,
        flags=re.I,
    )

    return value.strip(" -–—,:;")


def extract_company(title, detail):
    action_patterns = (
        r"\s+marks\s+(?:second\s+)?expansion\b",
        r"\s+expanding\b",
        r"\s+expands\b",
        r"\s+locating\b",
        r"\s+locates\b",
        r"\s+establishing\b",
        r"\s+establishes\b",
        r"\s+bringing\b",
        r"\s+to bring\b",
        r"\s+investing\b",
        r"\s+plans\b",
        r"\s+opening\b",
        r"\s+opens\b",
    )

    for pattern in action_patterns:
        match = re.search(pattern, title, re.I)

        if match and match.start() > 1:
            return clean_company_prefix(title[: match.start()])

    body_match = re.search(
        r"[–—-]\s*([A-Z][A-Za-z0-9&.,' \-]{2,80}?)\s+"
        r"(?:is|will be|plans to|has announced)\s+"
        r"(?:expanding|locating|establishing|building|investing|opening)",
        detail,
    )

    if body_match:
        return clean_company_prefix(body_match.group(1))

    return clean_company_prefix(title.split(" in ")[0].split(" to ")[0])


def extract_county(detail):
    matches = COUNTY_RE.findall(detail)

    for county in matches:
        county = county.strip()
        words = county.split()

        if 1 <= len(words) <= 3:
            return county

    return None


def extract_city(title, detail, county):
    title_patterns = (
        r"\boperations in ([A-Z][A-Za-z .'\-]+)$",
        r"\boperations to ([A-Z][A-Za-z .'\-]+)$",
        r"\bfacility in ([A-Z][A-Za-z .'\-]+)$",
        r"\bsawmill in ([A-Z][A-Za-z .'\-]+)$",
        r"\bplant in ([A-Z][A-Za-z .'\-]+)$",
        r"\bin ([A-Z][A-Za-z .'\-]+)$",
    )

    for pattern in title_patterns:
        match = re.search(pattern, title)

        if match:
            city = match.group(1).strip(" .,-")
            low = city.lower()

            bad_title_location = (
                low in {"mississippi", "mississippi state"}
                or low.endswith(" county")
                or low.endswith(" mississippi")
                or "u.s." in low
                or "united states" in low
                or " to mississippi" in low
            )

            if not bad_title_location and len(city.split()) <= 5:
                return city

    if county:
        county_escaped = re.escape(county)
        body_patterns = (
            rf"\bfacility in ([A-Z][A-Za-z .'\-]{{1,50}}?) in {county_escaped} County\b",
            rf"\boperations in ([A-Z][A-Za-z .'\-]{{1,50}}?)(?:,| in) {county_escaped} County\b",
            rf"\bexpanding(?: its)? operations in ([A-Z][A-Za-z .'\-]{{1,50}}?)(?:,| in) {county_escaped} County\b",
        )

        for pattern in body_patterns:
            match = re.search(pattern, detail)

            if match:
                city = match.group(1).strip(" .,-")

                if 1 <= len(city.split()) <= 5:
                    return city

    return None


def money_to_number(number, scale):
    value = float(number.replace(",", ""))
    scale = (scale or "").lower()

    if scale == "billion":
        value *= 1_000_000_000
    elif scale == "million":
        value *= 1_000_000
    elif scale == "thousand":
        value *= 1_000

    return int(round(value))


def extract_investment(text):
    money_value = (
        r"\$([0-9][0-9,]*(?:\.[0-9]+)?)"
        r"\s*(billion|million|thousand)?"
    )

    qualifier = (
        r"(?:more\s+than\s+|over\s+|approximately\s+|about\s+|"
        r"nearly\s+|up\s+to\s+)?"
    )

    primary_patterns = (
        rf"(?:project|expansion)\s+represents\s+(?:a\s+)?"
        rf"(?:corporate\s+)?investment\s+of\s+{qualifier}{money_value}",
        rf"corporate\s+investment\s+of\s+{qualifier}{money_value}",
        rf"(?:is|will be)\s+investing\s+{qualifier}{money_value}",
        rf"investment\s+of\s+{qualifier}{money_value}",
    )

    early = text[:5000]

    for pattern in primary_patterns:
        match = re.search(pattern, early, re.I)

        if match:
            return money_to_number(match.group(1), match.group(2))

    for sentence in re.split(r"(?<=[.!?])\s+", early):
        low = sentence.lower()

        if "invest" not in low:
            continue

        if not any(
            term in low
            for term in ("project", "expansion", "facility", "operations", "company")
        ):
            continue

        match = re.search(money_value, sentence, re.I)

        if match:
            return money_to_number(match.group(1), match.group(2))

    return None


def extract_jobs(text):
    values = [
        int(match.group(1).replace(",", ""))
        for match in JOBS_RE.finditer(text)
    ]

    if values:
        return max(values)

    return None


def extract_sqft(text):
    values = []

    for pattern in SQFT_PATTERNS:
        for match in pattern.finditer(text):
            values.append(int(float(match.group(1).replace(",", ""))))

    return max(values) if values else None


def classify_project_type(text):
    low = text.lower()

    if "data center" in low:
        return "data_center"

    if any(
        item in low
        for item in ("shipyard", "shipbuilding", "marine vessel", "gulf ship")
    ):
        return "shipbuilding_marine"

    if any(
        item in low
        for item in ("sawmill", "timber", "wood products", "lumber")
    ):
        return "forest_products"

    if any(
        item in low
        for item in ("warehouse", "distribution center", "logistics facility", "terminal facility")
    ):
        return "logistics_distribution"

    if any(
        item in low
        for item in ("laboratory", "testing operations", "medical testing")
    ):
        return "laboratory_health"

    if any(
        item in low
        for item in ("solar", "battery storage", "power plant", "energy facility")
    ):
        return "energy"

    if any(
        item in low
        for item in ("manufactur", "production", "fabrication", "processing")
    ):
        return "manufacturing"

    return "industrial_commercial"


def extract_scope_sentences(detail):
    sentences = re.split(r"(?<=[.!?])\s+", detail)
    keywords = (
        "construction",
        "construct",
        "facility",
        "building",
        "square feet",
        "square-foot",
        "site",
        "infrastructure",
        "electrical",
        "hvac",
        "roof",
        "flooring",
        "utilities",
        "warehouse",
        "plant",
        "manufactur",
        "expansion",
        "equipment",
        "paving",
        "drainage",
        "water",
        "sewer",
        "steel",
        "fabrication",
    )

    selected = []

    for sentence in sentences:
        sentence = re.sub(r"\s+", " ", sentence).strip()

        if len(sentence) < 35:
            continue

        low = sentence.lower()

        if any(keyword in low for keyword in keywords):
            selected.append(sentence[:700])

        if len(selected) >= 6:
            break

    return selected


def capability_tags(text):
    low = text.lower()
    tags = []

    for tag, terms in TRADE_TERMS.items():
        if any(term in low for term in terms):
            tags.append(tag)

    return tags


def normalize_project(item, source):
    title = str(item.get("name") or "").strip()
    detail = str(item.get("detailText") or "").strip()
    combined = f"{title}. {detail}".strip()

    company = extract_company(title, detail)
    county = extract_county(detail)
    city = extract_city(title, detail, county)
    project_type = classify_project_type(combined)
    published_at = parse_date(item.get("publishedAt"))
    investment = extract_investment(combined)
    jobs = extract_jobs(combined)
    facility_sqft = extract_sqft(combined)
    scope = extract_scope_sentences(detail)

    location_key = slugify(county or city or "mississippi")
    company_key = slugify(company)
    candidate_link_key = "-".join(
        item
        for item in (company_key, location_key, slugify(project_type))
        if item
    )

    why_parts = [
        "Early economic-development signal from the Mississippi Development Authority."
    ]

    if investment:
        why_parts.append(f"Announced investment: ${investment:,}.")

    if jobs:
        why_parts.append(f"Announced jobs: {jobs:,}.")

    if facility_sqft:
        why_parts.append(f"Facility size signal: {facility_sqft:,} sq. ft.")

    return {
        "id": item.get("id"),
        "name": title,
        "displayName": title,
        "company": company or None,
        "owner": company or source.get("owner"),
        "country": item.get("country") or source.get("country", "US"),
        "state": item.get("state") or source.get("state", "MS"),
        "county": county,
        "city": city,
        "source": item.get("sourceUrl"),
        "sourceName": item.get("source") or source.get("name"),
        "sourceId": source.get("id"),
        "sourcePlatform": source.get("platform"),
        "sourceType": source.get("type"),
        "status": "Announced / pre-construction",
        "bucket": "watch",
        "description": detail[:10000],
        "scope": scope,
        "why": " ".join(why_parts),
        "value": investment,
        "investment": investment,
        "jobs": jobs,
        "facilitySqFt": facility_sqft,
        "projectType": project_type,
        "signalType": "economic_development",
        "signalStage": "announced",
        "lifecycleStage": "pre_construction",
        "publishedAt": published_at,
        "discoveryType": "economic_development_announcement",
        "recordClassification": "economic_development_project",
        "capabilityTags": capability_tags(combined),
        # This is only a candidate cross-source key. It is intentionally NOT
        # wired into canonical dedupe yet because the same company can announce
        # multiple distinct expansions in the same county.
        "projectEntityKey": candidate_link_key or None,
        "projectEntityConfidence": "candidate",
        "linkage": {
            "companyKey": company_key or None,
            "locationKey": location_key or None,
            "candidateProjectKey": candidate_link_key or None,
            "linkStatus": "candidate_unverified",
            "note": (
                "Candidate key only. Cross-source linker must confirm identity "
                "before collapsing MDA, permit, utility, funding, or bid records."
            ),
        },
        "nextMove": (
            "Watch for environmental permits, local approvals, utility/infrastructure "
            "filings, general-contractor identification, and bid/subcontract packages."
        ),
        "needsHumanReview": item.get("detailStatus") != "fetched",
        "automation": {
            "collector": "scripts/collect_mda_news.py",
            "normalizer": "scripts/normalize_mda_news.py",
            "detailStatus": item.get("detailStatus"),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    source = load_source(args.source)
    raw_path = ROOT / "data" / "raw" / f'{source["id"]}_candidates.json'

    if not raw_path.exists():
        raise SystemExit(f"Raw candidate file not found: {raw_path}")

    raw = load(raw_path)
    accepted = []
    review = []
    rejected = []

    for item in raw.get("projects", []):
        title = str(item.get("name") or "")

        if not title_is_project(title):
            rejected.append(
                {
                    "id": item.get("id"),
                    "name": title,
                    "reason": "not_an_industrial_or_business_expansion_signal",
                }
            )
            continue

        project = normalize_project(item, source)

        if project["needsHumanReview"]:
            review.append(project)
        else:
            accepted.append(project)

    if not accepted and raw.get("count", 0):
        raise SystemExit(
            "MDA normalizer accepted zero project signals from a non-empty feed. "
            "Last good normalized output was not overwritten."
        )

    out = ROOT / "data" / "raw" / f'{source["id"]}_vertical_candidates.json'
    review_out = (
        ROOT
        / "data"
        / "review"
        / f'{source["id"]}_normalization_review.json'
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    review_out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(json.dumps(accepted, indent=2) + "\n")
    review_out.write_text(
        json.dumps(
            {
                "version": "0.16.0",
                "sourceId": source["id"],
                "review": review,
                "rejected": rejected,
            },
            indent=2,
        )
        + "\n"
    )

    print("PROJECT RADAR MDA INDUSTRIAL SIGNAL NORMALIZER")
    print("Source:", source["name"])
    print("Accepted project signals:", len(accepted))
    print("Needs review:", len(review))
    print("Rejected non-project news:", len(rejected))

    for project in accepted[:10]:
        extra = []

        if project.get("investment"):
            extra.append(f'${project["investment"]:,}')

        if project.get("jobs"):
            extra.append(f'{project["jobs"]:,} jobs')

        suffix = " | " + " | ".join(extra) if extra else ""
        print("-", project["name"] + suffix)


if __name__ == "__main__":
    main()
