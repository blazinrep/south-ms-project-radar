#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
base=json.loads((ROOT/"projects.json").read_text())
cand=json.loads((ROOT/"data/raw/mdot_proposed_candidates.json").read_text())
by={p["id"]:p for p in base}
for p in cand: by[p["id"]]=p
merged=list(by.values())
(ROOT/"projects.json").write_text(json.dumps(merged,indent=2))
print(f"Merged {len(cand)} live MDOT records; projects.json now has {len(merged)} records.")
