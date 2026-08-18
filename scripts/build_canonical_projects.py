#!/usr/bin/env python3

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

IN = ROOT / "data" / "intelligence" / "source_records_geocoded.json"
OUT = ROOT / "data" / "intelligence" / "canonical_projects.json"


def load(path):
    return json.loads(path.read_text())


def main():
    payload = load(IN)
    records = payload["records"]

    projects = []

    for r in records:
        p = dict(r)

        # Compatibility aliases for the existing opportunity engine.
        p["deadline"] = (
            r.get("deadline")
            or r.get("proposalDeadline")
        )

        p["why"] = (
            r.get("why")
            or r.get("description")
            or r.get("summary")
            or ""
        )

        p["nextMove"] = (
            r.get("nextMove")
            or "Open the source and verify scope, documents, deadline, requirements, and pursuit path."
        )

        p["contact"] = r.get("contact")

        # Preserve source URL under the field the old engine already reads.
        p["source"] = (
            r.get("source")
            or r.get("sourceUrl")
        )

        # Make geographic uncertainty explicit.
        p["geoPrecision"] = r.get("geoPrecision")
        p["geoApproximate"] = bool(r.get("geoApproximate", False))

        projects.append(p)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "version": "0.15.0",
        "recordCount": len(projects),
        "projects": projects
    }, indent=2) + "\n")

    with_deadline = sum(bool(p.get("deadline")) for p in projects)
    with_coords = sum(
        p.get("lat") is not None and p.get("lon") is not None
        for p in projects
    )

    print("V0.15 CANONICAL PROJECT COMPATIBILITY")
    print("-----------------------------------")
    print("Projects:", len(projects))
    print("With deadline:", with_deadline)
    print("With coordinates:", with_coords)
    print("Approximate geo:", sum(bool(p.get("geoApproximate")) for p in projects))


if __name__ == "__main__":
    main()
