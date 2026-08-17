#!/usr/bin/env python3

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE_RECORDS = ROOT / "data" / "intelligence" / "source_records.json"
OUT = ROOT / "data" / "intelligence" / "document_discovery.json"

URL_RE = re.compile(r'https?://[^\s<>"\']+', re.I)

DOCUMENT_SIGNALS = {
    "plans": [
        "plans",
        "drawings",
        "contract drawings"
    ],
    "specifications": [
        "specifications",
        "specs"
    ],
    "project_manual": [
        "project manual"
    ],
    "bid_documents": [
        "bid documents",
        "bidding documents",
        "contract documents"
    ],
    "addenda": [
        "addenda",
        "addendum"
    ],
    "bid_tab": [
        "bid tab",
        "bid-tab",
        "bid results"
    ],
    "planholders": [
        "plan holders",
        "planholders"
    ]
}

ACCESS_SIGNALS = {
    "registration_required": [
        "register or login",
        "registration",
        "registered users",
        "plan holders are required to register"
    ],
    "purchase_required": [
        "nonrefundable",
        "must be purchased",
        "order all hard copy documents"
    ],
    "download_available": [
        "available for download",
        "digital pdf",
        "digital cd"
    ]
}


def load(path):
    return json.loads(path.read_text())


def unique(items):
    seen = set()
    result = []

    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)

    return result


def detect(text, signals):
    lower = text.lower()
    found = []

    for key, phrases in signals.items():
        hits = [p for p in phrases if p in lower]

        if hits:
            found.append({
                "type": key,
                "evidence": hits
            })

    return found


def classify_access(text):
    lower = text.lower()

    registration = any(
        phrase in lower
        for phrase in ACCESS_SIGNALS["registration_required"]
    )

    purchase = any(
        phrase in lower
        for phrase in ACCESS_SIGNALS["purchase_required"]
    )

    downloadable = any(
        phrase in lower
        for phrase in ACCESS_SIGNALS["download_available"]
    )

    if purchase:
        return "purchase_or_registration_required"

    if registration:
        return "registration_required"

    if downloadable:
        return "download_mentioned"

    return "unknown"


def next_action(documents, access, urls):
    types = {x["type"] for x in documents}

    if "project_manual" in types or "specifications" in types:
        target = "project manual/specifications"
    elif "plans" in types:
        target = "plans"
    elif "bid_documents" in types:
        target = "bid documents"
    else:
        target = "project documents"

    if access == "purchase_or_registration_required":
        return (
            f"Open the designated planroom and register/order the "
            f"{target} before making a final trade-scope decision."
        )

    if access == "registration_required":
        return (
            f"Register/login at the designated planroom and obtain the "
            f"{target} before making a final trade-scope decision."
        )

    if urls:
        return (
            f"Check the discovered document source for the {target} "
            f"before making a final trade-scope decision."
        )

    return (
        f"Locate the {target} before making a final trade-scope decision."
    )


def main():
    payload = load(SOURCE_RECORDS)

    if isinstance(payload, dict):
        records = payload.get("records", [])
    else:
        records = payload

    results = []

    for project in records:
        text_parts = [
            str(project.get("name") or ""),
            str(project.get("displayName") or ""),
            str(project.get("description") or ""),
            str(project.get("detailText") or "")
        ]

        scope = project.get("scope")

        if isinstance(scope, list):
            text_parts.extend(str(x) for x in scope)
        elif scope:
            text_parts.append(str(scope))

        text = "\n".join(text_parts)

        documents = detect(text, DOCUMENT_SIGNALS)
        access = classify_access(text)

        urls = unique([
            u.rstrip(".,);]")
            for u in URL_RE.findall(text)
        ])

        source_url = (
            project.get("sourceUrl")
            or project.get("source")
        )

        if source_url and str(source_url).startswith("http"):
            urls.insert(0, str(source_url))

        urls = unique(urls)

        results.append({
            "projectId": project.get("id"),
            "projectName": (
                project.get("displayName")
                or project.get("name")
            ),
            "sourceId": project.get("sourceId"),
            "documentsDetected": documents,
            "documentTypes": [
                x["type"] for x in documents
            ],
            "access": access,
            "documentSources": urls,
            "needsDeeperScopeEvidence": bool(documents),
            "recommendedAction": next_action(
                documents,
                access,
                urls
            )
        })

    OUT.write_text(json.dumps({
        "version": "0.12.0",
        "projectCount": len(results),
        "projects": results
    }, indent=2) + "\n")

    with_docs = [
        x for x in results
        if x["documentsDetected"]
    ]

    restricted = [
        x for x in results
        if x["access"] in {
            "registration_required",
            "purchase_or_registration_required"
        }
    ]

    print("V0.12 DOCUMENT DISCOVERY")
    print("Projects scanned:", len(results))
    print("Projects with document evidence:", len(with_docs))
    print("Registration/purchase indicated:", len(restricted))

    print()
    print("DOCUMENT INTELLIGENCE EXAMPLES")

    for p in with_docs[:10]:
        print()
        print(p["projectName"])
        print("  Documents:", ", ".join(p["documentTypes"]))
        print("  Access:", p["access"])
        print("  Action:", p["recommendedAction"])


if __name__ == "__main__":
    main()
