#!/usr/bin/env python3
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from html import unescape
from html.parser import HTMLParser
from datetime import datetime, timezone
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"
USER_AGENT = "ProjectRadar/0.16 (+public economic-development signal monitor)"
NEWS_RE = re.compile(r"^/news/([^/?#]+)/?$", re.I)
DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4}\b",
    re.I,
)
_ROBOTS = {}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.text = []

    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href is not None:
            self.links.append(
                (self.href, re.sub(r"\s+", " ", " ".join(self.text)).strip())
            )
            self.href = None
            self.text = []


def load_source(source_id):
    data = json.loads(SOURCES.read_text())
    for source in data.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise SystemExit(f"Unknown source id: {source_id}")


def allowed(url):
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin in _ROBOTS:
        rp = _ROBOTS[origin]
        return True if rp is False else rp.can_fetch(USER_AGENT, url)

    rp = RobotFileParser()
    rp.set_url(origin + "/robots.txt")

    try:
        rp.read()
        _ROBOTS[origin] = rp
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        # If robots.txt itself is unavailable, do not make that a permanent
        # source failure. Explicit disallows are honored whenever readable.
        _ROBOTS[origin] = False
        return True


def fetch(url):
    if not allowed(url):
        raise RuntimeError(f"robots.txt disallows fetch: {url}")

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )

    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def textify(html):
    text = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def extract_h1(html):
    match = re.search(r"(?is)<h1\b[^>]*>(.*?)</h1>", html)
    return textify(match.group(1)) if match else ""


def extract_published(html, text):
    for pattern in (
        r'(?is)<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
        r'(?is)<time[^>]+datetime=["\']([^"\']+)',
    ):
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()

    match = DATE_RE.search(text[:2500])
    return match.group(0) if match else None


def article_body(text, title):
    pos = text.find(title) if title else -1
    body = text[pos + len(title):] if pos >= 0 else text

    for marker in ("Subscribe to our Newsletter", "Contact Us"):
        cut = body.find(marker)
        if cut > 1500:
            body = body[:cut]

    return body[:14000].strip()


def page_url(base, page):
    return base if page == 1 else urljoin(base.rstrip("/") + "/", f"page/{page}/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    args = parser.parse_args()

    source = load_source(args.source)
    base = source["baseUrl"]
    max_pages = int(source.get("maxPages", 4))
    max_items = int(source.get("maxItems", 48))
    minimum = int(source.get("minimumExpectedRecords", 3))

    links = []
    seen = set()

    for page in range(1, max_pages + 1):
        link_parser = LinkParser()
        link_parser.feed(fetch(page_url(base, page)))

        for href, label in link_parser.links:
            absolute = urljoin(base, href or "")
            match = NEWS_RE.match(urlparse(absolute).path)

            if not match or absolute in seen:
                continue

            seen.add(absolute)
            links.append((absolute, match.group(1), label))

            if len(links) >= max_items:
                break

        if len(links) >= max_items:
            break

    if len(links) < minimum:
        raise SystemExit(
            f"MDA collector found {len(links)} news links; expected at least "
            f"{minimum}. Last good snapshot preserved."
        )

    rows = []
    failures = 0

    for url, slug, label in links:
        try:
            html = fetch(url)
            visible = textify(html)
            title = extract_h1(html) or label or slug.replace("-", " ").title()
            detail = article_body(visible, title)
            date = extract_published(html, visible)
            status = "fetched"
        except Exception as exc:
            failures += 1
            title = label or slug.replace("-", " ").title()
            detail = ""
            date = None
            status = "failed:" + type(exc).__name__

        rows.append(
            {
                "id": f"mda-{slug}",
                "name": title,
                "sourceId": source["id"],
                "source": source["name"],
                "sourcePlatform": source.get("platform"),
                "sourceType": source.get("type"),
                "sourceUrl": url,
                "country": source.get("country", "US"),
                "state": source.get("state", "MS"),
                "discoveryType": "economic_development_announcement",
                "signalType": "economic_development",
                "publishedAt": date,
                "detailStatus": status,
                "detailText": detail,
            }
        )

    out = ROOT / "data" / "raw" / f'{source["id"]}_candidates.json'
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(
        json.dumps(
            {
                "version": "0.16.0",
                "collectedAt": datetime.now(timezone.utc).isoformat(),
                "sourceId": source["id"],
                "source": source["name"],
                "sourcePlatform": source.get("platform"),
                "sourceUrl": base,
                "count": len(rows),
                "detailFailures": failures,
                "projects": rows,
            },
            indent=2,
        )
        + "\n"
    )

    print("PROJECT RADAR MDA INDUSTRIAL SIGNAL COLLECTOR")
    print("News records discovered:", len(rows), "| detail failures:", failures)

    for row in rows[:10]:
        print("-", row["name"])


if __name__ == "__main__":
    main()
