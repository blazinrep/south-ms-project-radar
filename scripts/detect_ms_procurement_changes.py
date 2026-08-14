#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
R=Path(__file__).resolve().parents[1]
cur=json.loads((R/"data/raw/ms_procurement_candidates.json").read_text())
P=R/"state/ms_procurement_previous.json"; prev=json.loads(P.read_text()) if P.exists() else []
review=json.loads((R/"data/review/ms_procurement_review.json").read_text())
def fp(p):
 return hashlib.sha256("|".join(str(p.get(k,"")) for k in ["id","deadline","sourceRFxStatus","sourceRFx","scope"]).encode()).hexdigest()
a={p["id"]:p for p in prev};b={p["id"]:p for p in cur}
reviewed={f"msproc-{x['detail_id']}" for x in review}
ev=[]
for k,v in b.items():
    if k not in a:ev.append({"kind":"new_project","project_id":k,"after":v})
    elif fp(a[k])!=fp(v):ev.append({"kind":"project_changed","project_id":k,"before":a[k],"after":v})
for k,v in a.items():
    if k not in b:
        if k in reviewed:ev.append({"kind":"source_project_no_longer_open","project_id":k,"before":v})
        else:ev.append({"kind":"not_rechecked_guard","project_id":k,"before":v})
out={"source":"ms_procurement","generated_at":datetime.now(timezone.utc).isoformat(),"summary":{
"new":sum(x["kind"]=="new_project" for x in ev),"changed":sum(x["kind"]=="project_changed" for x in ev),
"no_longer_open":sum(x["kind"]=="source_project_no_longer_open" for x in ev),
"guarded_not_rechecked":sum(x["kind"]=="not_rechecked_guard" for x in ev)},"events":ev}
(R/"data/review/ms_procurement_changes.json").write_text(json.dumps(out,indent=2))
state={p["id"]:p for p in prev}
for p in cur:state[p["id"]]=p
for e in ev:
    if e["kind"]=="source_project_no_longer_open":state.pop(e["project_id"],None)
P.write_text(json.dumps(list(state.values()),indent=2))
print(out["summary"])
