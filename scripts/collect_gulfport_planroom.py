#!/usr/bin/env python3

from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
import json
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "gulfport_planroom_candidates.json"

BASE = "https://www.gulfportmsbids.com/"
PROJECT_RE = re.compile(r"/projects/\d+/details/")


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

            if PROJECT_RE.search(href):
                self.links.append({
                    "name": re.sub(r"\s+", " ", text),
                    "url": urljoin(BASE, href)
                })

            self.current_href = None
            self.current_text = []


def fetch(url):
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 ProjectRadar/0.11"
        }
    )

    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_html(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html.replace("&amp;", "&")
    html = html.replace("&nbsp;", " ")
    html = html.replace("&#39;", "'")
    html = html.replace("&quot;", '"')
    return re.sub(r"\s+", " ", html).strip()


def extract_detail(html):
    text = clean_html(html)

    lower = text.lower()

    markers = [
        "project description",
        "scope of work",
        "description",
        "project details"
    ]

    start = None

    for marker in markers:
        pos = lower.find(marker)
        if pos >= 0:
            start = pos
            break

    if start is not None:
        detail = text[start:start + 5000]
    else:
        detail = text[:5000]

    return detail.strip()


def main():
    html = fetch(BASE)

    parser = ProjectParser()
    parser.feed(html)

    seen = set()
    projects = []

    for item in parser.links:
        if item["url"] in seen:
            continue

        seen.add(item["url"])

        try:
            detail_html = fetch(item["url"])
            detail_text = extract_detail(detail_html)
            detail_status = "fetched"
        except Exception as exc:
            detail_text = ""
            detail_status = "failed:" + type(exc).__name__

        projects.append({
            "id": "gulfport-planroom-" + (
                re.search(r"/projects/(\d+)/", item["url"]).group(1)
                if re.search(r"/projects/(\d+)/", item["url"])
                else re.sub(r"[^a-z0-9]+", "-", item["url"].lower()).strip("-")
            ),
            "name": item["name"] or "City of Gulfport Project",
            "source": "City of Gulfport Planroom",
            "sourceType": "owner_planroom",
            "sourceUrl": item["url"],
            "owner": "City of Gulfport",
            "city": "Gulfport",
            "state": "MS",
            "discoveryType": "public_bid",
            "detailStatus": detail_status,
            "detailText": detail_text,
            "needsDetailFetch": False if detail_text else True
        })

    payload = {
        "version": "0.11.0",
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "source": "City of Gulfport Planroom",
        "sourceUrl": BASE,
        "count": len(projects),
        "projects": projects
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    print("V0.11 GULFPORT PLANROOM")
    print("Projects discovered:", len(projects))

    for project in projects[:10]:
        print("-", project["name"])


if __name__ == "__main__":
    main()
