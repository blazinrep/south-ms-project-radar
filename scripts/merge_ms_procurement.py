#!/usr/bin/env python3
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]; base=json.loads((ROOT/'projects.json').read_text()); cur=json.loads((ROOT/'data/raw/ms_procurement_candidates.json').read_text())
by={p['id']:p for p in base if not p['id'].startswith('msproc-')}
for p in cur: by[p['id']]=p
merged=list(by.values()); (ROOT/'projects.json').write_text(json.dumps(merged,indent=2))
print(f'Merged resilient procurement state: {len(cur)} current/stale records; projects.json now has {len(merged)} records.')
