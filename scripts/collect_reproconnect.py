#!/usr/bin/env python3

from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
from datetime import datetime, timezone
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"

PROJECT_RE = re.compile(r"/projects/(\d+)/details/")


class ProjectParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            self.current_href = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current_href is not None:
            href = self.current_href
            text = " ".join(self.current_text).strip()

            if PROJECT_RE.search(href or ""):
                self.links.append({
                    "name": re.sub(r"\s+", " ", text),
                    "href": href
                })

            self.current_href = None
            self.current_text = []


def fetch(url):
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 ProjectRadar/0.12"}
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_html(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)

    replacements = {
        "&amp;": "&",
        "&nbsp;": " ",
        "&#39;": "'",
        "&quot;": '"',
        "&middot;": "·"
    }

    for old, new in replacements.items():
        html = html.replace(old, new)

    return re.sub(r"\s+", " ", html).strip()


def extract_detail(html):
    text = clean_html(html)
    lower = text.lower()

    markers = [
        "scope of work",
        "project description",
        "description",
        "project details"
    ]

    start = None

    for marker in markers:
        pos = lower.find(marker)
        if pos >= 0:
            start = pos
            break

    return text[start:start + 6000] if start is not None else text[:6000]


def load_source(source_id):
    data = json.loads(SOURCES.read_text())

    for source in data.get("sources", []):
        if source.get("id") == source_id:
            return source

    raise SystemExit(f"Unknown source id: {source_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    source = load_source(args.source)

    base = source["baseUrl"]
    html = fetch(base)

    parser_html = ProjectParser()
    parser_html.feed(html)

    seen = set()
    projects = []

    for item in parser_html.links:
        url = urljoin(base, item["href"])
        match = PROJECT_RE.search(url)

        if not match:
            continue

        project_number = match.group(1)

        if project_number in seen:
            continue

        seen.add(project_number)

        try:
            detail_text = extract_detail(fetch(url))
            detail_status = "fetched"
        except Exception as exc:
            detail_text = ""
            detail_status = "failed:" + type(exc).__name__

        projects.append({
            "id": f'{source["id"]}-{project_number}',
            "name": item["name"] or source["name"],
            "sourceId": source["id"],
            "source": source["name"],
            "sourcePlatform": source.get("platform"),
            "sourceType": source.get("type"),
            "sourceUrl": url,
            "owner": source.get("owner"),
            "country": source.get("country", "US"),
            "state": source.get("state"),
            "county": source.get("county"),
            "city": source.get("city"),
            "discoveryType": "public_bid",
            "detailStatus": detail_status,
            "detailText": detail_text
        })

    out = ROOT / "data" / "raw" / f'{source["id"]}_candidates.json'
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(json.dumps({
        "version": "0.12.0",
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "sourceId": source["id"],
        "source": source["name"],
        "sourcePlatform": source.get("platform"),
        "sourceUrl": base,
        "count": len(projects),
        "projects": projects
    }, indent=2) + "\n")

    print("PROJECT RADAR REUSABLE PLANROOM COLLECTOR")
    print("Source:", source["name"])
    print("Projects discovered:", len(projects))

    for project in projects[:10]:
        print("-", project["name"])


if __name__ == "__main__":
    main()
