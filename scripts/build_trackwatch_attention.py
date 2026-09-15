#!/usr/bin/env python3
"""TrackWatch contractor adapter for South Mississippi Project Radar — V0.1.1.

Consumes Project Radar's existing Mississippi procurement change output and
creates a contractor-specific attention queue.

V0.1.1 source-health rule:
- Raw HTTP/network failures from lightweight discovery are recorded as telemetry.
- They DO NOT interrupt the contractor by themselves.
- A human-facing source-health alert is created only when the monitor reports
  itself unhealthy or when an already-known active record had to be preserved
  as stale/unverified.

This prevents speculative discovery misses from becoming false alarms.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CHANGES = ROOT / "data" / "review" / "ms_procurement_changes.json"
FETCH_STATUS = ROOT / "data" / "review" / "ms_procurement_fetch_status.json"
CARDS = ROOT / "data" / "intelligence" / "pursuit_cards.json"
PROFILE = ROOT / "config" / "contractor_demo.json"

OUT = ROOT / "data" / "intelligence" / "trackwatch_attention.json"
METRICS = ROOT / "data" / "intelligence" / "trackwatch_metrics.json"
STATE = ROOT / "state" / "trackwatch_attention_state.json"

ATTENTION_DECISIONS = {
    "act_today",
    "pursue_now",
    "verify_then_pursue",
    "verify_scope",
}

OPTIONAL_DECISIONS = {
    "optional_outside_radius",
    "watch",
    "specialist_only",
}

IMPORTANT_FIELDS = (
    "deadline",
    "prebid",
    "status",
    "sourceRFxStatus",
    "lifecycleStage",
    "scope",
    "value",
    "nextMove",
)

CAPABILITY_KEYWORDS = {
    "excavation": ("excavat", "earthwork", "earth work", "digging"),
    "grading": ("grading", "grade work", "subgrade"),
    "drainage": ("drainage", "storm drain", "culvert", "ditch"),
    "clearing": ("clearing", "grubbing", "tree removal", "site clearing"),
    "erosion_control": ("erosion", "sediment control", "silt fence"),
    "hauling": ("hauling", "haul", "trucking", "borrow material"),
    "utilities": ("utility", "utilities", "water main", "sewer", "gas main"),
}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value if value is not None else "")


def record_text(record: dict[str, Any]) -> str:
    pieces = [
        record.get("name"),
        record.get("county"),
        record.get("city"),
        record.get("owner"),
        record.get("nextMove"),
        record.get("majorProcurementCategory"),
        record.get("subProcurementCategory"),
    ]
    scope = record.get("scope")
    if isinstance(scope, list):
        pieces.extend(scope)
    elif scope:
        pieces.append(scope)
    return " ".join(str(x) for x in pieces if x).lower()


def card_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cards = payload.get("allCards") or payload.get("topPursuitCards") or []
    return {
        str(card.get("id")): card
        for card in cards
        if isinstance(card, dict) and card.get("id")
    }


def changed_fields(event: dict[str, Any]) -> list[dict[str, Any]]:
    before = event.get("before") if isinstance(event.get("before"), dict) else {}
    after = event.get("after") if isinstance(event.get("after"), dict) else {}
    changes = []
    for field in IMPORTANT_FIELDS:
        if stable(before.get(field)) != stable(after.get(field)):
            changes.append(
                {
                    "field": field,
                    "before": before.get(field),
                    "after": after.get(field),
                }
            )
    return changes


def capability_hits(record: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    text = record_text(record)
    capabilities = (
        profile.get("capabilitiesConfirmed")
        or profile.get("capabilities")
        or []
    )
    hits = []
    for capability in capabilities:
        terms = CAPABILITY_KEYWORDS.get(
            str(capability),
            (str(capability).replace("_", " "),),
        )
        if any(term.lower() in text for term in terms):
            hits.append(str(capability))
    return hits


def contractor_relevance(
    event: dict[str, Any],
    card: dict[str, Any] | None,
    profile: dict[str, Any],
) -> tuple[bool, str, list[str]]:
    record = (
        event.get("after")
        if isinstance(event.get("after"), dict)
        else event.get("before")
        if isinstance(event.get("before"), dict)
        else {}
    )

    if card:
        decision = str(card.get("decision") or "")
        if decision in ATTENTION_DECISIONS:
            return True, f"current Project Radar decision is {decision}", []
        if decision == "low_priority":
            return False, "current Project Radar decision is low_priority", []
        if decision in OPTIONAL_DECISIONS:
            fit = str(card.get("tradeFit") or "").lower()
            if fit == "strong":
                return True, f"optional lane but trade fit is {fit}", []
            return False, f"current Project Radar decision is {decision}", []

    bucket = str(record.get("bucket") or "").lower()
    match = record.get("match")
    try:
        match_score = float(match) if match is not None else 0.0
    except (TypeError, ValueError):
        match_score = 0.0

    hits = capability_hits(record, profile)

    if bucket in {"act", "pursue", "pursue_now", "act_today"}:
        return True, f"source record is in {bucket} bucket", hits
    if match_score >= 50:
        return True, f"source record match score is {match_score:g}", hits
    if hits:
        return True, f"scope matched contractor capabilities: {', '.join(hits)}", hits
    return False, "no strong contractor-fit signal", hits


def priority_for(kind: str, fields: list[str], card: dict[str, Any] | None) -> str:
    decision = str((card or {}).get("decision") or "")
    if kind == "source_project_no_longer_open":
        return "high"
    if "deadline" in fields or "status" in fields or "sourceRFxStatus" in fields:
        return "high"
    if decision == "act_today":
        return "high"
    if kind == "new_project" and decision in {"pursue_now", "verify_then_pursue"}:
        return "high"
    if kind == "new_project":
        return "medium"
    if "scope" in fields or "prebid" in fields:
        return "medium"
    return "normal"


def attention_type(kind: str, fields: list[str]) -> str:
    if kind == "new_project":
        return "new_opportunity"
    if kind == "source_project_no_longer_open":
        return "opportunity_closed"
    if kind == "project_changed":
        if "deadline" in fields:
            return "deadline_changed"
        if any(x in fields for x in ("status", "sourceRFxStatus", "lifecycleStage")):
            return "status_changed"
        if "prebid" in fields:
            return "prebid_changed"
        if "scope" in fields:
            return "scope_changed"
        if "value" in fields:
            return "value_changed"
        return "project_changed"
    return kind or "unknown_change"


def action_text(
    atype: str,
    event: dict[str, Any],
    card: dict[str, Any] | None,
    changes: list[dict[str, Any]],
) -> str:
    if atype == "new_opportunity":
        return str(
            (card or {}).get("firstAction")
            or (event.get("after") or {}).get("nextMove")
            or "Open the official source, verify requirements, and decide whether to pursue."
        )
    if atype == "opportunity_closed":
        return (
            "Stop treating this as an open bid. Confirm the official disposition "
            "if it was being pursued."
        )
    if atype == "deadline_changed":
        d = next((x for x in changes if x["field"] == "deadline"), None)
        if d:
            return (
                f"Recheck the official bid record now. Deadline changed from "
                f"{d.get('before') or 'unknown'} to {d.get('after') or 'unknown'}."
            )
        return "Recheck the official bid record now; the deadline changed."
    if atype in {"status_changed", "prebid_changed"}:
        return (
            "Open the official source and verify the changed status/date before "
            "committing more pursuit time."
        )
    if atype == "scope_changed":
        return (
            "Review the changed scope or addendum and reassess trade fit, price, "
            "and pursuit lane."
        )
    if atype == "value_changed":
        return (
            "Review the changed project value and confirm whether it changes "
            "qualification, bonding, or pursuit strategy."
        )
    return "Open the official source and verify what changed before acting."


def compact_project(record: dict[str, Any], card: dict[str, Any] | None) -> dict[str, Any]:
    c = card or {}
    return {
        "name": c.get("name") or record.get("name"),
        "county": c.get("county") or record.get("county"),
        "city": c.get("city") or record.get("city"),
        "decision": c.get("decision"),
        "tradeFit": c.get("tradeFit"),
        "actionPriority": c.get("actionPriority"),
        "fitScore": c.get("fitScore"),
        "deadline": c.get("deadline") or record.get("deadline"),
        "status": c.get("status") or record.get("status"),
        "source": c.get("source") or record.get("source"),
    }


def event_fingerprint(
    input_generated_at: str,
    event: dict[str, Any],
    changes: list[dict[str, Any]],
) -> str:
    payload = {
        "input": input_generated_at,
        "kind": event.get("kind"),
        "project_id": event.get("project_id"),
        "changes": changes,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:20]


def main() -> int:
    change_payload = load_json(CHANGES, {})
    fetch_status = load_json(FETCH_STATUS, {})
    cards_payload = load_json(CARDS, {})
    profile = load_json(PROFILE, {})
    previous_state = load_json(STATE, {})

    events = change_payload.get("events") or []
    input_generated_at = str(change_payload.get("generated_at") or "")
    cards = card_index(cards_payload)

    attention = []
    filtered = []

    for event in events:
        if not isinstance(event, dict):
            continue
        project_id = str(event.get("project_id") or "")
        card = cards.get(project_id)
        record = (
            event.get("after")
            if isinstance(event.get("after"), dict)
            else event.get("before")
            if isinstance(event.get("before"), dict)
            else {}
        )
        kind = str(event.get("kind") or "unknown")
        changes = changed_fields(event)
        fields = [x["field"] for x in changes]
        relevant, relevance_reason, hits = contractor_relevance(event, card, profile)

        if kind == "project_changed" and not fields:
            filtered.append(
                {
                    "projectId": project_id,
                    "kind": kind,
                    "reason": "only low-value/non-action fields changed",
                }
            )
            continue

        if not relevant:
            filtered.append(
                {
                    "projectId": project_id,
                    "kind": kind,
                    "reason": relevance_reason,
                }
            )
            continue

        atype = attention_type(kind, fields)
        project = compact_project(record, card)
        attention.append(
            {
                "id": event_fingerprint(input_generated_at, event, changes),
                "projectId": project_id,
                "type": atype,
                "priority": priority_for(kind, fields, card),
                "title": {
                    "new_opportunity": "New contractor-relevant opportunity",
                    "opportunity_closed": "Opportunity no longer open",
                    "deadline_changed": "Bid deadline changed",
                    "status_changed": "Opportunity status changed",
                    "prebid_changed": "Pre-bid information changed",
                    "scope_changed": "Project scope changed",
                    "value_changed": "Project value changed",
                    "project_changed": "Project information changed",
                }.get(atype, "Project change needs review"),
                "project": project,
                "relevance": relevance_reason,
                "capabilityHits": hits,
                "changedFields": fields,
                "changes": changes,
                "action": action_text(atype, event, card, changes),
            }
        )

    # Source-health telemetry is intentionally separate from human attention.
    # The underlying procurement monitor probes new IDs as part of discovery.
    # Raw HTTP/network failures can occur there without making already-known
    # opportunities stale. Only stale known records or an explicit unhealthy
    # monitor state deserve an interruption.
    raw_fetch_errors = int(fetch_status.get("network_or_http_failures") or 0)
    stale_unverified = int(fetch_status.get("stale_unverified") or 0)
    monitor_unhealthy = fetch_status.get("ok") is False
    source_health_problem = monitor_unhealthy or stale_unverified > 0

    if source_health_problem:
        attention.insert(
            0,
            {
                "id": f"source-health-{input_generated_at or now_iso()}",
                "projectId": None,
                "type": "source_check_problem",
                "priority": "high",
                "title": "Known procurement data could not be verified",
                "project": {},
                "relevance": (
                    "at least one known opportunity became stale/unverified"
                    if stale_unverified
                    else "the procurement monitor reported an unhealthy run"
                ),
                "capabilityHits": [],
                "changedFields": [],
                "changes": [],
                "action": (
                    f"{stale_unverified} known opportunity record"
                    f"{'s are' if stale_unverified != 1 else ' is'} stale/unverified. "
                    "Review source health before acting on those records."
                    if stale_unverified
                    else "Review the procurement monitor status before relying on this run."
                ),
            },
        )

    type_counts: dict[str, int] = {}
    for item in attention:
        t = str(item.get("type") or "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    summary = {
        "eventsSeen": len(events),
        "needsAttention": len(attention),
        "filtered": len(filtered),
        "sourceHealthProblems": 1 if source_health_problem else 0,
        "staleUnverified": stale_unverified,
        "rawFetchErrors": raw_fetch_errors,
        "byType": type_counts,
    }

    output = {
        "generatedAt": now_iso(),
        "adapter": "TrackWatch Contractor Adapter V0.1.1",
        "inputSource": "Mississippi procurement monitor",
        "inputGeneratedAt": input_generated_at or None,
        "profile": cards_payload.get("profile") or profile.get("name"),
        "summary": summary,
        "attention": attention,
        "filtered": filtered,
        "sourceTelemetry": {
            "monitorOk": fetch_status.get("ok"),
            "checkedAt": fetch_status.get("checked_at"),
            "knownActiveChecked": fetch_status.get("known_active_checked"),
            "currentRecords": fetch_status.get("current_records"),
            "staleUnverified": stale_unverified,
            "rawNetworkOrHttpFailures": raw_fetch_errors,
            "note": (
                "Raw discovery fetch failures are telemetry, not a human alert, "
                "unless known records became stale or the monitor reports unhealthy."
            ),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, indent=2), encoding="utf-8")

    totals = previous_state.get("totals") or {
        "inputsProcessed": 0,
        "eventsSeen": 0,
        "needsAttention": 0,
        "filtered": 0,
        "sourceHealthProblems": 0,
        "staleUnverified": 0,
        "rawFetchErrors": 0,
    }
    # Normalize older V0.1 state keys if present.
    totals.pop("sourceErrors", None)
    for key in (
        "inputsProcessed",
        "eventsSeen",
        "needsAttention",
        "filtered",
        "sourceHealthProblems",
        "staleUnverified",
        "rawFetchErrors",
    ):
        totals.setdefault(key, 0)

    last_input = str(previous_state.get("lastInputGeneratedAt") or "")
    if input_generated_at and input_generated_at != last_input:
        totals["inputsProcessed"] = int(totals["inputsProcessed"]) + 1
        for key in (
            "eventsSeen",
            "needsAttention",
            "filtered",
            "sourceHealthProblems",
            "staleUnverified",
            "rawFetchErrors",
        ):
            totals[key] = int(totals[key]) + int(summary[key])

    state = {
        "updatedAt": now_iso(),
        "lastInputGeneratedAt": input_generated_at or last_input or None,
        "totals": totals,
    }
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    metrics = {
        "generatedAt": now_iso(),
        "purpose": "TrackWatch proof-case metrics for contractor monitoring",
        "profile": output["profile"],
        "latest": summary,
        "cumulative": totals,
        "note": (
            "Cumulative counts advance once per unique Mississippi procurement "
            "change-file generated_at value. Raw discovery fetch errors are tracked "
            "separately from human-facing source-health problems."
        ),
    }
    METRICS.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print("TRACKWATCH — CONTRACTOR ADAPTER V0.1.1")
    print("------------------------------------")
    print(f"{summary['eventsSeen']} procurement change event(s) scanned")
    print(f"{summary['needsAttention']} contractor-relevant item(s) need attention")
    print(f"{summary['filtered']} low-value / weak-fit item(s) filtered")
    print(f"{summary['sourceHealthProblems']} source-health problem(s) needing attention")
    print(f"{summary['rawFetchErrors']} raw discovery/network fetch error(s) logged as telemetry")
    for item in attention:
        name = (item.get("project") or {}).get("name") or "source health"
        print(f"  {str(item['priority']).upper():6} {item['type']}: {name}")
    print(f"\nWrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {METRICS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
