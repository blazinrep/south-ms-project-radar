#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import copy, json, math, re, sys

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "data" / "intelligence" / "canonical_projects.json"
PROFILE = ROOT / "config/contractor_demo.json"
RULES = ROOT / "config/intelligence_rules.json"
OVERRIDES = ROOT / "data/intelligence/research_overrides.json"
OUT_DIR = ROOT / "data/intelligence"

def load(p): return json.loads(p.read_text())

def haversine_miles(lat1, lon1, lat2, lon2):
    r=3958.7613
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(math.sqrt(a))

def text_blob(p):
    vals=[p.get("name",""),p.get("county",""),p.get("city",""),p.get("why",""),
          p.get("sourceType",""),p.get("majorProcurementCategory",""),
          p.get("subProcurementCategory",""),p.get("sourceDescription","")]
    vals += p.get("scope") or []
    return " ".join(str(x) for x in vals if x).lower()

def parse_deadline(v):
    if not v: return None
    try: return datetime.fromisoformat(str(v).replace("Z","+00:00"))
    except ValueError: return None

def days_until(v):
    d=parse_deadline(v)
    if not d: return None
    now=datetime.now(d.tzinfo) if d.tzinfo else datetime.now()
    return (d-now).total_seconds()/86400

def hard_reject_reason(p,rules):
    major=str(p.get("majorProcurementCategory","")).upper()
    sub=str(p.get("subProcurementCategory","")).upper()
    blob=text_blob(p)
    if major in set(rules["hardRejectMajorCategories"]): return f"wrong_major_category:{major}"
    if sub in set(rules["hardRejectSubcategories"]): return f"wrong_subcategory:{sub}"
    for phrase in rules["hardRejectPhrases"]:
        if phrase.lower() in blob: return f"non_sitework_procurement:{phrase}"
    return None

def infer_fit(p,rules,profile):
    blob=text_blob(p); caps=set(profile["capabilities"])
    terms=[]; raw=0
    for term,w in rules["siteworkPositiveTerms"].items():
        if term in blob:
            terms.append(term); raw+=w
    overlap=set(p.get("capabilityTags") or []) & caps
    raw += min(12, 3*len(overlap))

    # Words such as "likely" mean the source record is signaling inference.
    inferred = any(x in blob for x in (" likely","possible","potential","should be checked","must be confirmed"))
    score=min(35,raw)
    if inferred: score=min(score,18)

    fit="none"
    if score>=27: fit="strong"
    elif score>=16: fit="conditional"
    elif score>=7: fit="weak"
    return fit,score,sorted(set(terms)),inferred

EVIDENCE_POINTS={
    "official_explicit":15,
    "published_scope_explicit":15,
    "published_project_explicit_scope_partial":10,
    "researched_scope_explicit":14,
    "source_record":8,
    "sitework_inferred_not_explicit":4,
    "researched_false_positive":15
}

def evidence_points(level,p):
    base=EVIDENCE_POINTS.get(level,7)
    if (p.get("automation") or {}).get("needsHumanReview"):
        base=min(base,8)
    return base

def geo_points(distance,radius):
    if distance is None:return 6
    if distance<=radius*.45:return 15
    if distance<=radius*.75:return 13
    if distance<=radius:return 10
    if distance<=radius*1.15:return 3
    return 0

def runway_points(days):
    if days is None:return 7
    if days<0:return 0
    if days<2:return 2
    if days<5:return 6
    if days<=14:return 15
    if days<=30:return 13
    if days<=90:return 10
    return 7

def urgency_bonus(days):
    if days is None or days<0:return 0
    if days<2:return 12
    if days<5:return 10
    if days<=7:return 7
    if days<=14:return 4
    return 0

def access_points(path, fit, profile):
    score=7
    if fit=="strong":score+=6
    elif fit=="conditional":score+=3
    if "subcontract" in path:score+=4
    elif "prime_candidate" in path:score+=4
    elif path=="watch":score+=2
    if profile.get("commercialLicenseStatus")=="unknown" and "prime" in path:score-=1
    if profile.get("bondingCapacity")=="unknown" and "prime" in path:score-=1
    return max(0,min(20,score))

def inferred_path(p,fit):
    blob=text_blob(p)
    if p.get("bucket") in ("watch","ahead") or p.get("lifecycleStage") in ("future_letting","pre_construction"):
        return "watch"
    if "new construction" in blob and any(x in blob for x in (" likely","possible","potential")):
        return "subcontract_target"
    if any(x in blob for x in ("milling","overlay","asphalt","bridge","landfill cell")):
        return "subcontract_target_or_prime_if_qualified"
    if fit=="strong":return "prime_candidate_or_subcontract"
    if fit=="conditional":return "subcontract_target"
    return "investigate"

def qualification_gates(p):
    gates=[]
    value=p.get("value")
    if isinstance(value,(int,float)) and value>50000:
        gates.append({"type":"commercial_license","status":"verify",
                      "detail":"Published project value exceeds $50,000; verify the appropriate Mississippi commercial contractor classification before bidding/performing covered work."})
    elif p.get("bucket")=="act":
        gates.append({"type":"commercial_license","status":"verify_if_applicable",
                      "detail":"Verify applicable Mississippi contractor licensing/classification requirements for the exact scope and contract value."})
    if str(p.get("sourceType","")).lower().startswith("official mississippi"):
        gates.append({"type":"state_vendor_registration","status":"verify_for_state_business",
                      "detail":"Confirm Mississippi supplier/MAGIC registration requirements for this procurement and bid method."})
    return gates

def project_override_for(p,ovs):
    if p["id"] in ovs.get("projects",{}):
        return copy.deepcopy(ovs["projects"][p["id"]])
    alias=ovs.get("nameAliases",{}).get(p.get("name",""))
    if alias and alias in ovs.get("projects",{}):
        o=copy.deepcopy(ovs["projects"][alias])
        o.setdefault("canonicalProjectKey",alias)
        return o
    return {}

def canonical_key(p,ovs,o):
    if o.get("canonicalProjectKey"):return o["canonicalProjectKey"]
    if p["id"] in ovs.get("aliases",{}):return ovs["aliases"][p["id"]]
    for k in ("sourceFedProjectNo","sourceProjectNo"):
        if p.get(k):return re.sub(r"[^a-z0-9]+","-",str(p[k]).lower()).strip("-")
    return p["id"]

def fit_score_from_override(fit,level,automatic):
    if automatic:return 0
    if level in ("published_scope_explicit","official_explicit","researched_scope_explicit"):
        return {"strong":35,"conditional":24,"weak":12,"none":0}.get(fit,0)
    if level=="published_project_explicit_scope_partial":
        return {"strong":27,"conditional":20,"weak":10,"none":0}.get(fit,0)
    if level=="sitework_inferred_not_explicit":
        return {"strong":16,"conditional":12,"weak":6,"none":0}.get(fit,0)
    return None

def decision_class(fit,level,distance,radius,days,path,automatic,override):
    if automatic or override.get("disposition")=="reject": return "reject"
    if days is not None and days<0:return "closed_or_expired"
    if distance is not None and distance>radius:
        return "optional_outside_radius"
    if level=="sitework_inferred_not_explicit":
        return "verify_scope"
    if fit in ("none","weak"):
        return "low_priority"
    if path=="watch":
        return "watch"
    if fit=="strong" and level in ("published_scope_explicit","official_explicit","researched_scope_explicit"):
        if days is not None and days<=5:
            return "act_today"
        return "pursue_now"
    if fit in ("strong","conditional"):
        return "verify_then_pursue"
    return "investigate"

def enrich(p,rules,profile,ovs):
    o=project_override_for(p,ovs)
    automatic=hard_reject_reason(p,rules)
    fit,scope_score,fit_terms,inferred=infer_fit(p,rules,profile)

    # Research can correct the raw classifier.
    fit=o.get("tradeFit",fit)
    level=o.get("evidenceLevel","sitework_inferred_not_explicit" if inferred else "source_record")
    explicit_score=fit_score_from_override(fit,level,automatic)
    if explicit_score is not None:scope_score=explicit_score

    path=o.get("pursuitPath",inferred_path(p,fit))

    distance=p.get("distance")
    if distance is None and p.get("lat") is not None and p.get("lon") is not None:
        distance=round(haversine_miles(profile["base"]["lat"],profile["base"]["lon"],p["lat"],p["lon"]),1)

    days=days_until(p.get("deadline"))
    geo=geo_points(distance,profile["preferredRadiusMiles"])
    runway=runway_points(days)
    evidence=evidence_points(level,p)
    access=access_points(path,fit,profile)

    if automatic:
        fit="none";path="reject";scope_score=0;access=0

    specialist_required=o.get("specialistCapabilityRequired")
    has_specialist_capability=(
        not specialist_required
        or specialist_required in set(profile.get("capabilities",[]))
    )

    decision=decision_class(fit,level,distance,profile["preferredRadiusMiles"],days,path,automatic,o)
    if specialist_required and not has_specialist_capability:
        decision="specialist_only"
        path="specialist_only"

    gates=qualification_gates(p)
    gates.extend(o.get("requiredChecks",[]))

    if o.get("scopeFitOverride") is not None:
        scope_score=int(o["scopeFitOverride"])
    if o.get("pursuitAccessibilityOverride") is not None:
        access=int(o["pursuitAccessibilityOverride"])

    fit_total=scope_score+access+runway+geo+evidence

    # Action priority is deliberately distinct from bid/no-bid fit.
    # An excellent opportunity with four days left may require a call TODAY
    # even though the short runway lowers its fit/feasibility score.
    action_priority=fit_total+urgency_bonus(days)
    if decision=="verify_scope":
        action_priority=min(action_priority,72)
    if decision=="optional_outside_radius":
        action_priority=min(action_priority,68)
    if decision=="specialist_only":
        action_priority=min(action_priority,30)
    if decision in ("low_priority","reject","closed_or_expired"):
        action_priority=min(action_priority,45 if decision=="low_priority" else 0)

    risk_flags=list(o.get("riskFlags",[]))
    if distance is not None and distance>profile["preferredRadiusMiles"] and "outside_preferred_radius" not in risk_flags:
        risk_flags.append("outside_preferred_radius")
    if level=="sitework_inferred_not_explicit" and "sitework_scope_inferred" not in risk_flags:
        risk_flags.append("sitework_scope_inferred")

    intel={
        "version":"0.7.2",
        "canonicalProjectKey":canonical_key(p,ovs,o),
        "displayName":o.get("displayName",p.get("name")),
        "authoritativeSource":o.get("authoritativeSource",p.get("source")),
        "decision":decision,
        "disposition":decision,  # compatibility with V0.7 consumers
        "pursuitPath":path,
        "tradeFit":fit,
        "evidenceLevel":level,
        "fitEvidence":o.get("fitEvidence",fit_terms),
        "qualificationGates":gates,
        "scores":{
            "scopeFit":scope_score,
            "pursuitAccessibility":access,
            "runway":runway,
            "geography":geo,
            "evidenceQuality":evidence,
            "fitTotal":fit_total,
            "actionPriority":action_priority
        },
        "daysToDeadline":round(days,1) if days is not None else None,
        "distanceMiles":distance,
        "riskFlags":risk_flags,
        "whyItMatters":o.get("whyItMatters",p.get("why","")),
        "nextAction":o.get("nextAction",p.get("nextMove") or "Open the source and verify scope, requirements, documents and pursuit path."),
        "actionType":o.get("actionType","research_and_verify"),
        "recommendedContact":o.get("recommendedContact",p.get("contact")),
        "automaticRejectReason":automatic
    }

    out=copy.deepcopy(p)
    out["displayName"]=intel["displayName"]
    out["intelligence"]=intel
    return out

def choose_canonical(group):
    def rank(p):
        i=p["intelligence"];x=0
        if not p["id"].startswith("msproc-"):x+=1000
        if i["evidenceLevel"] in ("published_scope_explicit","official_explicit","researched_scope_explicit"):x+=100
        x+=i["scores"]["fitTotal"]
        return x
    return max(group,key=rank)

def main():
    for f in (PROJECTS,PROFILE,RULES,OVERRIDES):
        if not f.exists():
            print(f"Missing: {f}",file=sys.stderr);sys.exit(2)
    payload=load(PROJECTS)
    projects=payload["projects"] if isinstance(payload,dict) and "projects" in payload else payload
    profile=load(PROFILE);rules=load(RULES);ovs=load(OVERRIDES)
    enriched=[enrich(p,rules,profile,ovs) for p in projects]

    groups={}
    for p in enriched:
        groups.setdefault(p["intelligence"]["canonicalProjectKey"],[]).append(p)

    canonical=[];dupes=[]
    for key,g in groups.items():
        selected=copy.deepcopy(choose_canonical(g))
        selected["intelligence"]["sourceRecordIds"]=sorted(x["id"] for x in g)
        canonical.append(selected)
        if len(g)>1:
            dupes.append({"canonicalProjectKey":key,"selectedRecordId":selected["id"],
                          "duplicateRecordIds":sorted(x["id"] for x in g if x["id"]!=selected["id"])})

    rejected=[p for p in canonical if p["intelligence"]["decision"]=="reject"]
    opps=[p for p in canonical if p["intelligence"]["decision"] not in ("reject","closed_or_expired")]

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

    action_queue=sorted(
        opps,
        key=lambda p:(
            urgency_order.get(p["intelligence"].get("decision"),6),
            -p["intelligence"]["scores"].get("actionPriority",0),
            -p["intelligence"]["scores"].get("fitTotal",0),
            p.get("deadline") or "9999"
        )
    )[:10]
    fit_ranking=sorted(opps,key=lambda p:(-p["intelligence"]["scores"]["fitTotal"],
                                          p.get("deadline") or "9999"))[:10]

    OUT_DIR.mkdir(parents=True,exist_ok=True)
    (OUT_DIR/"opportunities.json").write_text(json.dumps(opps,indent=2))
    (OUT_DIR/"rejected.json").write_text(json.dumps(rejected,indent=2))
    (OUT_DIR/"duplicates.json").write_text(json.dumps(dupes,indent=2))

    brief={
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "profile":profile["name"],
        "sourceRecordCount":len(projects),
        "canonicalProjectCount":len(canonical),
        "duplicateGroups":len(dupes),
        "rejectedCount":len(rejected),
        "decisionCounts":{},
        "actionQueue":[],
        "fitRanking":[]
    }
    for p in opps:
        d=p["intelligence"]["decision"]
        brief["decisionCounts"][d]=brief["decisionCounts"].get(d,0)+1

    def compact(p):
        i=p["intelligence"]
        return {
            "id":p["id"],"name":p["intelligence"].get("displayName",p.get("name")),"county":p.get("county"),
            "deadline":p.get("deadline"),"daysToDeadline":i["daysToDeadline"],
            "distanceMiles":i["distanceMiles"],"decision":i["decision"],
            "pursuitPath":i["pursuitPath"],"tradeFit":i["tradeFit"],
            "evidenceLevel":i["evidenceLevel"],"scores":i["scores"],
            "whyItMatters":i["whyItMatters"],"nextAction":i["nextAction"],
            "actionType":i["actionType"],"riskFlags":i["riskFlags"],
            "qualificationGates":i["qualificationGates"]
        }

    brief["actionQueue"]=[compact(p) for p in action_queue]
    brief["fitRanking"]=[compact(p) for p in fit_ranking]
    (OUT_DIR/"daily_brief.json").write_text(json.dumps(brief,indent=2))

    print(f"Source records: {len(projects)}")
    print(f"Canonical projects after dedupe: {len(canonical)}")
    print(f"Duplicate groups collapsed: {len(dupes)}")
    print(f"Rejected false/non-fit records: {len(rejected)}")
    print("Decision counts:", brief["decisionCounts"])
    print("TOP ACTION QUEUE:")
    for n,p in enumerate(action_queue[:5],1):
        i=p["intelligence"]
        print(f"{n}. {i.get('displayName',p.get('name'))} | action {i['scores']['actionPriority']} | fit {i['scores']['fitTotal']} | {i['decision']} | {i['pursuitPath']}")
    print("TOP FIT RANKING:")
    for n,p in enumerate(fit_ranking[:5],1):
        i=p["intelligence"]
        print(f"{n}. {i.get('displayName',p.get('name'))} | fit {i['scores']['fitTotal']} | {i['decision']} | {i['evidenceLevel']}")

if __name__=="__main__":
    main()
