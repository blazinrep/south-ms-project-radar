#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime, timezone
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.json"
ADAPTERS = ROOT / "config" / "adapters.json"
HEALTH = ROOT / "data" / "intelligence" / "source_health.json"


def load(path):
    return json.loads(path.read_text())


def run_command(cmd):
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip()
    }


def main():
    config = load(SOURCES)
    adapter_config = load(ADAPTERS)
    adapters = adapter_config.get("adapters", {})

    results = []

    for source in config.get("sources", []):
        if source.get("status") != "active":
            continue

        platform = source.get("platform")
        source_id = source.get("id")

        if source.get("management") == "legacy_pipeline":
            results.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "platform": platform,
                "status": "legacy_managed"
            })
            continue

        adapter = adapters.get(platform)

        if not adapter:
            results.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "platform": platform,
                "status": "adapter_missing"
            })
            continue

        if adapter.get("status") != "active":
            results.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "platform": platform,
                "status": "adapter_inactive"
            })
            continue

        collector = adapter.get("collector")
        normalizer = adapter.get("normalizer")

        if not collector or not normalizer:
            results.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "platform": platform,
                "status": "adapter_incomplete"
            })
            continue

        print()
        print("=" * 70)
        print("SOURCE:", source.get("name"))
        print("=" * 70)

        raw_file = (
            ROOT / "data" / "raw" /
            f"{source_id}_candidates.json"
        )

        normalized_file = (
            ROOT / "data" / "raw" /
            f"{source_id}_vertical_candidates.json"
        )

        previous_raw_exists = raw_file.exists()
        previous_normalized_exists = normalized_file.exists()

        collect = run_command([
            sys.executable,
            collector,
            "--source",
            source_id
        ])

        print(collect["stdout"])

        if collect["returncode"] != 0:
            print("COLLECT FAILED:", collect["stderr"])

            results.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "platform": platform,
                "status": "collector_failed",
                "lastGoodRawPreserved": previous_raw_exists,
                "lastGoodNormalizedPreserved": previous_normalized_exists,
                "error": collect["stderr"]
            })

            continue

        normalize = run_command([
            sys.executable,
            normalizer,
            "--source",
            source_id
        ])

        print(normalize["stdout"])

        if normalize["returncode"] != 0:
            print("NORMALIZER FAILED:", normalize["stderr"])

            results.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "platform": platform,
                "status": "normalizer_failed",
                "lastGoodNormalizedPreserved": previous_normalized_exists,
                "error": normalize["stderr"]
            })

            continue

        try:
            raw = load(raw_file)
            raw_count = raw.get("count", 0)

            normalized = load(normalized_file)
            normalized_count = len(normalized)

        except Exception as exc:
            raw_count = None
            normalized_count = None

        results.append({
            "sourceId": source_id,
            "source": source.get("name"),
            "platform": platform,
            "status": "healthy",
            "rawCount": raw_count,
            "constructionCandidateCount": normalized_count
        })

    payload = {
        "version": "0.12.0",
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "sourcesChecked": len(results),
        "healthy": sum(x["status"] == "healthy" for x in results),
        "failed": sum(
            x["status"] not in {"healthy", "legacy_managed"}
            for x in results
        ),
        "sources": results
    }

    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    HEALTH.write_text(json.dumps(payload, indent=2) + "\n")

    print()
    print("PROJECT RADAR SOURCE HEALTH")
    print("---------------------------")
    print("Sources checked:", payload["sourcesChecked"])
    print("Healthy:", payload["healthy"])
    print("Failed:", payload["failed"])

    for item in results:
        print(
            f'{item["status"].upper():18} | '
            f'{item["source"]}'
        )


if __name__ == "__main__":
    main()
