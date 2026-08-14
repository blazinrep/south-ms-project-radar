#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import json, re

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/"data/snapshots/mdot_proposed.json"
OUT=ROOT/"data/raw/mdot_proposed_candidates.json"

CAPS={
 "Bridge Replacement":["excavation","grading","drainage","erosion_control","hauling"],
 "Bridge Repair":["excavation","grading","drainage","erosion_control","hauling"],
 "Bridge Preventive Maintenance":["drainage","hauling"],
 "Mill & Overlay":["paving_base","hauling"],
 "Fog Seal":["paving_base","hauling"],
 "OGFC Lift":["paving_base","hauling"],
 "Overlay":["paving_base","hauling"],
 "Slide Improvement":["excavation","grading","drainage","erosion_control","hauling"],
 "Lot Improvement":["grading","drainage","paving_base"],
 "Reconstruction":["excavation","grading","drainage","utilities","hauling"],
}
WEIGHT={"Bridge Replacement":90,"Bridge Repair":82,"Bridge Preventive Maintenance":65,
"Mill & Overlay":68,"Fog Seal":58,"OGFC Lift":62,"Overlay":66,"Slide Improvement":94,
"Lot Improvement":84,"Reconstruction":95}

def slug(s): return re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-")

def normalize(r):
    scope=r["scope"]
    return {
      "id":f"mdot-{slug(r['project_no'])}",
      "name":f"MDOT Proposed: {r['route'] or 'Project'} — {r['county']} County {scope}",
      "county":r["county"],"city":f"{r['county']} County corridor",
      "lat":None,"lon":None,
      "status":f"Proposed {r['month']} letting","bucket":"ahead","deadline":None,"prebid":None,
      "value":None,"match":WEIGHT.get(scope,60),"timing":72,"confidence":99,"distance":None,
      "scope":[x for x in [scope,r["route"],r["termini"]] if x],
      "why":f"Official MDOT future-letting signal for {scope.lower() if scope else 'road work'}. Early-stage watch item; not yet represented as an open bid.",
      "owner":"Mississippi Department of Transportation",
      "contact":"Monitor MDOT proposed letting / Bid Express",
      "source":"https://mdot.ms.gov/applications/Schedule_of_Proposed_Projects/ProposedLetting.aspx",
      "verified":datetime.now(timezone.utc).date().isoformat(),
      "sourceType":"Official MDOT proposed letting",
      "capabilityTags":CAPS.get(scope,["hauling"]),
      "lifecycleStage":"pre_bid_or_preconstruction","signalType":"future_letting",
      "nextMove":"Watch for the letting package and identify likely primes before bid release.",
      "changeStatus":"watch",
      "automation":{"sourceKey":"mdot_proposed","lastSeen":datetime.now(timezone.utc).isoformat(),"needsHumanReview":False},
      "sourceProjectNo":r["project_no"],"sourceFedProjectNo":r.get("fed_project_no",""),
      "sourceParallelProjectNo":r.get("parallel_to_project_no",""),
      "proposedMonth":r["month"].replace("/","-")+"-01"
    }

payload=json.loads(SNAP.read_text())
records=[normalize(r) for r in payload["records"]]
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(records,indent=2))
print(f"Wrote {len(records)} normalized live MDOT candidates.")
