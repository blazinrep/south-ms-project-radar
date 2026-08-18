#!/usr/bin/env python3

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

SOURCE_RECORDS = ROOT / "data" / "intelligence" / "source_records.json"
CENTROIDS = ROOT / "config" / "ms_county_centroids.json"
OUT = ROOT / "data" / "intelligence" / "source_records_geocoded.json"


def load(path):
    return json.loads(path.read_text())


def main():
    payload = load(SOURCE_RECORDS)
    records = payload["records"] if isinstance(payload, dict) else payload

    centroid_data = load(CENTROIDS)
    counties = centroid_data["counties"]

    exact = 0
    fallback = 0
    unresolved = 0

    results = []

    for record in records:
        r = dict(record)

        if r.get("lat") is not None and r.get("lon") is not None:
            r["geoPrecision"] = r.get("geoPrecision") or "project_coordinates"
            exact += 1
            results.append(r)
            continue

        county = r.get("county")

        if county in counties:
            r["lat"] = counties[county]["lat"]
            r["lon"] = counties[county]["lon"]
            r["geoPrecision"] = "county_centroid"
            r["geoApproximate"] = True
            fallback += 1
        else:
            r["geoPrecision"] = "unknown"
            r["geoApproximate"] = True
            unresolved += 1

        results.append(r)

    out_payload = {
        "version": "0.15.0",
        "recordCount": len(results),
        "exactCoordinates": exact,
        "countyFallbacks": fallback,
        "unresolved": unresolved,
        "records": results
    }

    OUT.write_text(json.dumps(out_payload, indent=2) + "\n")

    print("V0.15 GEO FALLBACKS")
    print("-------------------")
    print("Records:", len(results))
    print("Exact coordinates:", exact)
    print("County centroid fallbacks:", fallback)
    print("Still unresolved:", unresolved)


if __name__ == "__main__":
    main()
