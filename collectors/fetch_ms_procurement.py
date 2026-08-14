#!/usr/bin/env python3
from __future__ import annotations
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
import concurrent.futures as cf
import json, re, sys

ROOT=Path(__file__).resolve().parents[1]
BASE="https://www.ms.gov/dfa/contract_bid_search/Bid/Details/"
OUT=ROOT/"data/raw/ms_procurement_candidates.json"
REVIEW=ROOT/"data/review/ms_procurement_review.json"
STATUS=ROOT/"data/review/ms_procurement_fetch_status.json"
STATE=ROOT/"state/ms_procurement_discovery.json"
PREV=ROOT/"state/ms_procurement_previous.json"
TZ=ZoneInfo("America/Chicago")

COUNTY_ANCHORS={"Marion":(31.2518,-89.8354),"Forrest":(31.3271,-89.2903),"Lamar":(31.1432,-89.4098),"Jones":(31.6941,-89.1306),"Perry":(31.2021,-89.0367),"Greene":(31.1557,-88.5578),"Pearl River":(30.8407,-89.5342),"Walthall":(31.1160,-90.1420),"Jefferson Davis":(31.5985,-89.8670),"Covington":(31.6454,-89.5553),"Lawrence":(31.5538,-90.1070),"Pike":(31.1432,-90.4587),"Lincoln":(31.5791,-90.4407),"Franklin":(31.4724,-90.8968),"Simpson":(31.9618,-89.8701),"Stone":(30.8582,-89.1353),"Clarke":(32.0404,-88.7281),"Jasper":(31.9790,-89.2873),"Wayne":(31.6740,-88.6461),"Harrison":(30.3674,-89.0928),"Hancock":(30.3088,-89.3300),"Jackson":(30.3674,-88.5561)}
CITY_TO_COUNTY={"columbia":"Marion","hattiesburg":"Forrest","purvis":"Lamar","laurel":"Jones","ellisville":"Jones","new augusta":"Perry","leakesville":"Greene","poplarville":"Pearl River","tylertown":"Walthall","prentiss":"Jefferson Davis","collins":"Covington","monticello":"Lawrence","magnolia":"Pike","mccomb":"Pike","brookhaven":"Lincoln","meadville":"Franklin","mendenhall":"Simpson","wiggins":"Stone","quitman":"Clarke","bay springs":"Jasper","waynesboro":"Wayne","gulfport":"Harrison","bay saint louis":"Hancock","bay st louis":"Hancock","pascagoula":"Jackson","moss point":"Jackson"}
LABELS={"Smart Number","Advertised Date","RFx #","Submission Date","RFx Status","Major Procurement Category","RFx Opening Date","Sub Procurement Category","RFx Type","Agency","RFx Description"}

class Cells(HTMLParser):
    def __init__(self): super().__init__(); self.on=False; self.buf=[]; self.cells=[]
    def handle_starttag(self,t,a):
        if t.lower() in ("td","th"): self.on=True; self.buf=[]
    def handle_data(self,d):
        if self.on:self.buf.append(d)
    def handle_endtag(self,t):
        if t.lower() in ("td","th") and self.on:
            self.cells.append(" ".join("".join(self.buf).split())); self.on=False

def fetch_id(i):
    url=BASE+str(i)+"?AppId=1"
    try:
        req=Request(url,headers={"User-Agent":"Mozilla/5.0 ProjectRadar/0.6.3","Accept":"text/html"})
        with urlopen(req,timeout=15) as r: h=r.read().decode("utf-8",errors="ignore")
        if "Procurement Details" not in h or "Smart Number" not in h:return i,None,None
        return i,h,None
    except HTTPError as e:
        if e.code in (404,410):return i,None,None
        return i,None,f"HTTP {e.code}"
    except (URLError,OSError,TimeoutError) as e:return i,None,str(e)

def fields(h):
    p=Cells(); p.feed(h); o={}
    for n,x in enumerate(p.cells[:-1]):
        if x in LABELS:o[x]=p.cells[n+1]
    return o

def dt(s):
    if not s or s.upper()=="N/A":return None
    for f in ("%m/%d/%Y %I:%M %p","%m/%d/%Y %H:%M","%m/%d/%Y"):
        try:return datetime.strptime(s,f).replace(tzinfo=TZ)
        except ValueError:pass
    return None

def county(f):
    text=" ".join(str(v) for v in f.values()).lower()
    for c in COUNTY_ANCHORS:
        if re.search(rf"\b{re.escape(c.lower())}\s+county\b",text):return c
    for city,c in CITY_TO_COUNTY.items():
        if re.search(rf"\b{re.escape(city)}\b",text):return c
    return None

def construction(f):
    major=f.get("Major Procurement Category","").upper()
    sub=f.get("Sub Procurement Category","").upper()
    desc=f.get("RFx Description","").lower()
    return major=="CONSTRUCTION" or "CONSTRUCTION" in sub or any(x in desc for x in ("sealed bids","construction of","road construction","bridge","culvert","drainage","site work","sitework"))

def caps(text):
    t=text.lower(); out=set()
    rules={"excavation":["excavat","earthwork","culvert","ditch"],"grading":["grading","road construction","site work","sitework"],"drainage":["drainage","storm sewer","culvert","ditch"],"utilities":["water main","sewer","utility","wastewater","lift station"],"clearing":["clearing","grubbing","debris removal"],"erosion_control":["erosion","riprap","stabilization"],"hauling":["hauling","aggregate","earthwork"],"paving_base":["paving","overlay","asphalt","milling","base course"]}
    for k,ws in rules.items():
        if any(w in t for w in ws):out.add(k)
    return sorted(out)

def normalize(i,f,c,now):
    desc=f.get("RFx Description",""); sub=f.get("Sub Procurement Category",""); cp=caps(desc+" "+sub)
    lat,lon=COUNTY_ANCHORS[c]; deadline=dt(f.get("Submission Date",""))
    return {"id":f"msproc-{i}","name":f"{c} / {f.get('Smart Number','MS Procurement')}","county":c,"city":f"{c} County","lat":lat,"lon":lon,"locationPrecision":"county_seat_approx","status":"Accepting bids","bucket":"act","deadline":deadline.isoformat(),"prebid":None,"value":None,"match":min(99,55+8*len(cp)),"timing":96,"confidence":96,"distance":None,"scope":[x for x in [sub,desc[:320]] if x],"why":"Official Mississippi procurement detail page; future published deadline verified by Project Radar.","owner":f.get("Agency","Mississippi public agency"),"contact":"See official record and attachments","source":BASE+str(i)+"?AppId=1","verified":now.date().isoformat(),"sourceType":"Official Mississippi procurement","capabilityTags":cp,"lifecycleStage":"open_procurement","signalType":"public_bid","nextMove":"Review the official attachments, confirm exact work location and scope, then decide prime or subcontract pursuit.","changeStatus":"new","automation":{"sourceKey":"ms_procurement","lastSeen":now.isoformat(),"needsHumanReview":True},"sourceDetailId":str(i),"sourceSmartNumber":f.get("Smart Number"),"sourceRFx":f.get("RFx #"),"sourceRFxStatus":f.get("RFx Status"),"majorProcurementCategory":f.get("Major Procurement Category"),"subProcurementCategory":sub,"submissionDateRaw":f.get("Submission Date")}

def main():
    now=datetime.now(TZ); OUT.parent.mkdir(parents=True,exist_ok=True); REVIEW.parent.mkdir(parents=True,exist_ok=True); STATE.parent.mkdir(parents=True,exist_ok=True)
    st=json.loads(STATE.read_text()) if STATE.exists() else {}
    high=int(st.get("high_water",46250))
    low=max(1, high-2200 if not st else high-150)
    upper=high+500

    prev_active=json.loads(PREV.read_text()) if PREV.exists() else []
    prev_ids={int(p["sourceDetailId"]) for p in prev_active if str(p.get("sourceDetailId","")).isdigit()}
    discovery_ids=set(range(low,upper+1))
    ids=sorted(discovery_ids|prev_ids)

    print(f"Scanning discovery IDs {low}–{upper} plus {len(prev_ids)} previously-active IDs...")
    valid=[]; errors=[]
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for i,h,e in ex.map(fetch_id,ids):
            if h:valid.append((i,h))
            elif e:errors.append({"id":i,"error":e})
    if not valid:
        STATUS.write_text(json.dumps({"ok":False,"checked_at":now.isoformat(),"range":[low,upper]},indent=2)); sys.exit(2)

    review=[]; publish=[]; max_seen=max(i for i,_ in valid); cutoff=now-timedelta(days=120)
    for i,h in valid:
        f=fields(h); advertised=dt(f.get("Advertised Date","")); deadline=dt(f.get("Submission Date","")); c=county(f)
        status=f.get("RFx Status","").strip().lower(); reasons=[]
        if not advertised or advertised<cutoff:reasons.append("not_recent")
        if not deadline or deadline<=now:reasons.append("deadline_passed_or_missing")
        if status in {"closed","archived","cancelled","canceled"}:reasons.append("source_closed")
        if not construction(f):reasons.append("not_construction_relevant")
        if not c:reasons.append("outside_or_unresolved_territory")
        decision="publish" if not reasons else "skip"
        review.append({"detail_id":i,"decision":decision,"reasons":reasons,"county":c,"fields":f})
        if decision=="publish":publish.append(normalize(i,f,c,now))

    REVIEW.write_text(json.dumps(review,indent=2)); OUT.write_text(json.dumps(publish,indent=2))
    STATE.write_text(json.dumps({"high_water":max(max_seen,high),"last_scan_upper":upper,"checked_at":now.isoformat()},indent=2))
    STATUS.write_text(json.dumps({"ok":True,"checked_at":now.isoformat(),"range":[low,upper],"previous_active_rechecked":len(prev_ids),"valid_pages":len(valid),"publishable_count":len(publish),"transient_errors":len(errors)},indent=2))
    print(f"Found {len(valid)} valid procurement detail pages.")
    print(f"Published {len(publish)} current South-Mississippi construction opportunities.")
    print(f"Rechecked {len(prev_ids)} previously-active opportunities explicitly.")

if __name__=="__main__":main()
