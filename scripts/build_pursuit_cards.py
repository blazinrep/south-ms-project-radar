#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT/"config/contractor_demo.json"
OVERRIDES = ROOT/"data/intelligence/research_overrides.json"
OPPS = ROOT/"data/intelligence/opportunities.json"
OUT = ROOT/"data/intelligence/pursuit_cards.json"

def load(p): return json.loads(p.read_text())

def profile_capabilities(profile):
    return set(profile.get("capabilitiesConfirmed") or profile.get("capabilities") or [])

def prime_readiness(project, override, profile):
    blockers=[]
    caps=profile_capabilities(profile)
    req=set(override.get("primeCapabilityRequirements") or [])
    missing=sorted(req-caps)
    for cap in missing:
        blockers.append({
            "type":"capability",
            "status":"not_confirmed",
            "detail":f"Prime pursuit requires confirmed capability: {cap}"
        })

    readiness=profile.get("readiness",{})
    lic=(readiness.get("commercialLicense") or {}).get("status","unknown")
    bond=(readiness.get("bonding") or {}).get("status","unknown")

    if lic!="verified":
        blockers.append({
            "type":"commercial_license",
            "status":lic,
            "detail":"Commercial license/classification is not verified in the demo company profile."
        })

    if bond!="verified":
        blockers.append({
            "type":"bonding",
            "status":bond,
            "detail":"Bonding capacity is not verified in the demo company profile."
        })

    if missing:
        status="not_ready"
    elif any(b["status"]=="unknown" for b in blockers):
        status="unknown"
    elif blockers:
        status="not_ready"
    else:
        status="ready"

    return status, blockers

def recommended_lane(project, override, profile):
    intel=project["intelligence"]
    lane=override.get("recommendedLane")

    if lane:
        return lane

    path=intel.get("pursuitPath","investigate")
    if path=="specialist_only":
        return "specialist_only"
    if intel.get("decision")=="optional_outside_radius":
        return "optional_outside_radius"
    if "subcontract" in path:
        return "subcontract_target"
    if "prime" in path:
        status,_=prime_readiness(project,override,profile)
        return "prime_candidate" if status=="ready" else "verify_prime_readiness"
    return path

def card(project, override, profile):
    intel=project["intelligence"]
    prime_status, prime_blockers=prime_readiness(project,override,profile)
    lane=recommended_lane(project,override,profile)

    gates=list(intel.get("qualificationGates") or [])
    # Avoid repeating readiness gates already modeled as blockers.
    gate_types={g.get("type") for g in gates}

    all_blockers=list(prime_blockers)
    for g in gates:
        if g.get("status") in {
            "required","required_for_prime","verify",
            "verify_for_state_business","required_before_pursuit",
            "verify_for_electronic_bid"
        }:
            all_blockers.append(g)

    return {
        "id":project["id"],
        "name":project.get("displayName") or project.get("name"),
        "owner":project.get("owner"),
        "county":project.get("county"),
        "city":project.get("city"),
        "lat":project.get("lat"),
        "lon":project.get("lon"),
        "value":project.get("value"),
        "status":project.get("status"),
        "verified":project.get("verified"),
        "freshnessStatus":project.get("freshnessStatus") or (project.get("automation") or {}).get("lastCheckStatus"),
        "deadline":project.get("deadline"),
        "daysToDeadline":intel.get("daysToDeadline"),
        "distanceMiles":intel.get("distanceMiles"),
        "decision":intel.get("decision"),
        "recommendedLane":lane,
        "primeReadiness":prime_status,
        "actionPriority":intel["scores"].get("actionPriority"),
        "fitScore":intel["scores"].get("fitTotal"),
        "tradeFit":intel.get("tradeFit"),
        "evidenceLevel":intel.get("evidenceLevel"),
        "whyThisMatters":intel.get("whyItMatters"),
        "scope":project.get("scope") or [],
        "fitEvidence":intel.get("fitEvidence") or [],
        "firstAction":override.get("firstAction") or intel.get("nextAction"),
        "secondAction":override.get("secondAction"),
        "stopIf":override.get("stopIf"),
        "contact":override.get("contact") or intel.get("recommendedContact"),
        "source":intel.get("authoritativeSource") or project.get("source"),
        "blockersAndChecks":all_blockers,
        "riskFlags":intel.get("riskFlags") or [],
        "sourceRecordIds":intel.get("sourceRecordIds") or [project["id"]]
    }

def main():
    profile=load(PROFILE)
    overrides=load(OVERRIDES)
    projects=load(OPPS)

    cards=[]
    for p in projects:
        key=p["intelligence"].get("canonicalProjectKey")
        o=(overrides.get("projects") or {}).get(p["id"],{})
        if not o and key:
            o=(overrides.get("projects") or {}).get(key,{})
        cards.append(card(p,o,profile))

    # Source-of-truth queue order:
    # hard urgency decision first, then action priority, fit, and deadline.
    urgency_order={
        "act_today":0,
        "pursue_now":1,
        "verify_then_pursue":2,
        "verify_scope":2,
        "optional_outside_radius":3,
        "watch":3,
        "specialist_only":4,
        "low_priority":5
    }
    cards.sort(key=lambda c: (
        urgency_order.get(c.get("decision"),6),
        -(c.get("actionPriority") or 0),
        -(c.get("fitScore") or 0),
        c.get("deadline") or "9999"
    ))

    payload={
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "profile":profile["name"],
        "profileReadiness":profile.get("readiness"),
        "count":len(cards),
        "topPursuitCards":cards[:10],
        "allCards":cards
    }
    OUT.write_text(json.dumps(payload,indent=2))

    print("V0.9.3 PURSUIT CARDS")
    print(f"Cards built: {len(cards)}")
    for i,c in enumerate(cards[:5],1):
        print(
            f"{i}. {c['name']} | {c['decision']} | {c['recommendedLane']} | "
            f"prime={c['primeReadiness']} | action={c['actionPriority']}"
        )
        print(f"   FIRST: {c['firstAction']}")
        if c.get("stopIf"):
            print(f"   STOP IF: {c['stopIf']}")

if __name__=="__main__":
    main()
