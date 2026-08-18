#!/usr/bin/env python3

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

PROFILE = ROOT / "config" / "contractor_demo.json"
SOURCES = ROOT / "config" / "sources.json"
OUT = ROOT / "data" / "intelligence" / "contractor_source_selection.json"


def load(path):
    return json.loads(path.read_text())


def main():
    profile = load(PROFILE)
    source_config = load(SOURCES)

    territory = profile.get("territory", {})
    allowed_states = set(territory.get("allowedStates", []))
    home_state = territory.get("homeState")

    selected = []
    excluded = []

    for source in source_config.get("sources", []):
        source_id = source.get("id")
        status = source.get("status")
        state = source.get("state")
        geography = source.get("geography") or []
        enabled = source.get("enabledForPipeline")

        if enabled is False:
            excluded.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "reason": "explicitly_disabled"
            })
            continue

        if status == "known_restricted":
            excluded.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "reason": "restricted_source"
            })
            continue

        if status != "active":
            excluded.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "reason": f"status_{status}"
            })
            continue

        inferred_state = state

        if not inferred_state:
            geo_text = " ".join(str(x) for x in geography).lower()

            if "mississippi" in geo_text:
                inferred_state = "MS"

        if inferred_state and inferred_state not in allowed_states:
            excluded.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "reason": f"outside_allowed_states:{inferred_state}"
            })
            continue

        if not inferred_state and home_state:
            excluded.append({
                "sourceId": source_id,
                "source": source.get("name"),
                "reason": "state_unknown"
            })
            continue

        selected.append({
            "sourceId": source_id,
            "source": source.get("name"),
            "platform": source.get("platform"),
            "state": inferred_state,
            "status": status,
            "authentication": source.get("authentication"),
            "selectionReason": "within_contractor_territory"
        })

    payload = {
        "version": "0.15.0",
        "profileId": profile.get("profileId"),
        "homeBase": profile.get("base"),
        "territory": territory,
        "selectedCount": len(selected),
        "excludedCount": len(excluded),
        "selectedSources": selected,
        "excludedSources": excluded
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n")

    print("V0.15 CONTRACTOR SOURCE SELECTION")
    print("--------------------------------")
    print("Profile:", profile.get("name"))
    print("Allowed states:", ", ".join(sorted(allowed_states)))
    print("Selected sources:", len(selected))
    print("Excluded sources:", len(excluded))

    print()
    print("SELECTED")

    for item in selected:
        print(
            "-",
            item["sourceId"],
            "|",
            item["state"],
            "|",
            item["status"]
        )

    print()
    print("EXCLUDED")

    for item in excluded:
        print(
            "-",
            item["sourceId"],
            "|",
            item["reason"]
        )


if __name__ == "__main__":
    main()
