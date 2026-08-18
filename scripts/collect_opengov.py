#!/usr/bin/env python3

from pathlib import Path
from urllib.request import Request, urlopen
from datetime import datetime, timezone
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"


def load(path):
    return json.loads(path.read_text())


def load_source(source_id):
    data = load(SOURCES)

    for source in data.get("sources", []):
        if source.get("id") == source_id:
            return source

    raise SystemExit(f"Unknown source id: {source_id}")


def fetch(url):
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 ProjectRadar/0.14"}
    )

    with urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def extract_balanced_object(text, start):
    if start < 0 or text[start] != "{":
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True

        elif ch == "{":
            depth += 1

        elif ch == "}":
            depth -= 1

            if depth == 0:
                return text[start:i + 1]

    return None


def clean_html(text):
    if not text:
        return ""

    text = re.sub(r"(?is)<script.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)

    replacements = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
        "&ndash;": "–",
        "&mdash;": "—"
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return re.sub(r"\s+", " ", text).strip()


def extract_projects(body):
    public_marker = '"publicProject":'
    public_pos = body.find(public_marker)

    if public_pos < 0:
        raise ValueError("publicProject marker not found")

    gov_marker = '"govProjects":'
    gov_pos = body.find(gov_marker, public_pos)

    if gov_pos < 0:
        raise ValueError("govProjects marker not found")

    start = body.find("{", gov_pos + len(gov_marker))

    raw = extract_balanced_object(body, start)

    if not raw:
        raise ValueError("could not extract govProjects object")

    return json.loads(raw)


def normalize_row(row, source):
    government = row.get("government") or {}
    organization = government.get("organization") or {}
    department = row.get("department") or {}

    government_code = government.get("code") or source.get("agencySlug")

    project_id = row.get("id")

    detail_url = (
        f"https://procurement.opengov.com/portal/"
        f"{government_code}/projects/{project_id}"
        if government_code and project_id
        else source.get("baseUrl")
    )

    return {
        "id": f'opengov-{government_code}-{project_id}',
        "name": row.get("title"),
        "displayName": row.get("title"),
        "sourceId": source.get("id"),
        "source": source.get("name"),
        "sourcePlatform": "opengov",
        "sourceType": source.get("type", "procurement_platform"),
        "sourceUrl": detail_url,
        "owner": organization.get("name"),
        "department": department.get("name"),
        "country": organization.get("countryCode", "US"),
        "state": organization.get("state"),
        "city": organization.get("city"),
        "zipCode": organization.get("zipCode"),
        "address": organization.get("address1"),
        "timezone": organization.get("timezone"),
        "financialId": row.get("financialId"),
        "projectId": project_id,
        "status": row.get("status"),
        "releaseDate": row.get("releaseProjectDate"),
        "proposalDeadline": row.get("proposalDeadline"),
        "summary": clean_html(row.get("summary")),
        "description": clean_html(row.get("summary")),
        "addendaCount": len(row.get("addendums") or []),
        "isPrivate": bool(row.get("isPrivate")),
        "comingSoon": bool(row.get("comingSoon")),
        "discoveryType": "public_bid"
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    source = load_source(args.source)

    slug = source.get("agencySlug")

    if not slug:
        raise SystemExit(
            f'Source {source["id"]} missing agencySlug'
        )

    page_size = 50
    page = 1
    all_rows = []
    total_available = None

    while True:
        url = (
            f"https://procurement.opengov.com/portal/embed/"
            f"{slug}/project-list"
            f"?departmentId=all&status=all&page={page}&limit={page_size}"
        )

        body = fetch(url)
        project_payload = extract_projects(body)

        if total_available is None:
            total_available = project_payload.get("count")

        rows = project_payload.get("rows", [])

        if not rows:
            break

        all_rows.extend(rows)

        print(
            f"Fetched page {page}: "
            f"{len(rows)} rows "
            f"({len(all_rows)}/{total_available or '?'})"
        )

        if total_available is not None and len(all_rows) >= total_available:
            break

        if len(rows) < page_size:
            break

        page += 1

    seen = set()
    deduped_rows = []

    for row in all_rows:
        row_id = row.get("id")

        if row_id in seen:
            continue

        seen.add(row_id)
        deduped_rows.append(row)

    projects = [
        normalize_row(row, source)
        for row in deduped_rows
        if not row.get("isPrivate")
    ]

    out = (
        ROOT / "data" / "raw" /
        f'{source["id"]}_candidates.json'
    )

    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(json.dumps({
        "version": "0.14.0",
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "sourceId": source.get("id"),
        "source": source.get("name"),
        "agencySlug": slug,
        "totalAvailable": total_available,
        "count": len(projects),
        "projects": projects
    }, indent=2) + "\n")

    print("PROJECT RADAR OPENGOV COLLECTOR")
    print("Source:", source.get("name"))
    print("Total available:", total_available)
    print("Rows collected:", len(projects))

    for project in projects[:10]:
        print(
            "-",
            project.get("name"),
            "|",
            project.get("state"),
            "|",
            project.get("status"),
            "|",
            project.get("proposalDeadline")
        )


if __name__ == "__main__":
    main()
