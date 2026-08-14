#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
cur=json.loads((ROOT/"projects.json").read_text())
prevp=ROOT/"state/previous_projects.json"; prev=json.loads(prevp.read_text()) if prevp.exists() else []
def fp(p):
 return hashlib.sha256("|".join(str(p.get(k,"")) for k in ["id","status","deadline","proposedMonth","owner","sourceProjectNo"]).encode()).hexdigest()
a={p["id"]:p for p in prev}; b={p["id"]:p for p in cur}; events=[]
for k,v in b.items():
 if k not in a: events.append({"kind":"new_project","project_id":k,"after":v})
 elif fp(a[k])!=fp(v): events.append({"kind":"project_changed","project_id":k,"before":a[k],"after":v})
for k,v in a.items():
 if k not in b: events.append({"kind":"project_removed","project_id":k,"before":v})
out={"generated_at":datetime.now(timezone.utc).isoformat(),"summary":{"new":sum(e["kind"]=="new_project" for e in events),"changed":sum(e["kind"]=="project_changed" for e in events),"removed":sum(e["kind"]=="project_removed" for e in events)},"events":events}
(ROOT/"changes.json").write_text(json.dumps(out,indent=2)); prevp.parent.mkdir(exist_ok=True); prevp.write_text(json.dumps(cur,indent=2))
print(out["summary"])
