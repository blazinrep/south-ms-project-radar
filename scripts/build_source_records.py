#!/usr/bin/env python3

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

BASE_PROJECTS = ROOT / "projects.json"

SOURCES = ROOT / "config" / "sources.json"

OUT = ROOT / "data" / "intelligence" / "source_records.json"


def load(path):
    return json.loads(path.read_text())


def main():
    records = []
    seen = set()

    def add(record, feed):
        if not isinstance(record, dict):
            return

        rid = record.get("id")
        if not rid or rid in seen:
            return

        seen.add(rid)

        item = dict(record)
        item.setdefault("sourceFeed", feed)

        records.append(item)

    for record in load(BASE_PROJECTS):
        add(record, "legacy_projects")

    source_config = load(SOURCES)

    for source in source_config.get("sources", []):
        if source.get("status") != "active":
            continue

        if source.get("platform") != "reproconnect_planhouse":
            continue

        path = (
            ROOT / "data" / "raw" /
            f'{source["id"]}_vertical_candidates.json'
        )

        if not path.exists():
            continue

        for record in load(path):
            add(record, source["id"])

    OUT.parent.mkdir(parents=True, exist_ok=True)

    OUT.write_text(json.dumps({
        "version": "0.11.0",
        "recordCount": len(records),
        "records": records
    }, indent=2) + "\n")

    print("V0.11 SOURCE RECORD POOL")
    print("Records:", len(records))

    counts = {}
    for r in records:
        feed = r.get("sourceFeed", "unknown")
        counts[feed] = counts.get(feed, 0) + 1

    for feed, count in sorted(counts.items()):
        print(f"- {feed}: {count}")


if __name__ == "__main__":
    main()
