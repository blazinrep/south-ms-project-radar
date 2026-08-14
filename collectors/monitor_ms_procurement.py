#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timezone
import concurrent.futures as cf, hashlib, json
from ms_procurement_common import ROOT, fetch_detail, parse_fields, infer_county, construction_relevant, explicit_closed, parse_dt, normalize, mark_stale, TZ

PREV=ROOT/'state/ms_procurement_previous.json'; DISC=ROOT/'state/ms_procurement_discovery.json'; OUT=ROOT/'data/raw/ms_procurement_candidates.json'; CHANGES=ROOT/'data/review/ms_procurement_changes.json'; STATUS=ROOT/'data/review/ms_procurement_fetch_status.json'; REVIEW=ROOT/'data/review/ms_procurement_review.json'
DAILY_NEW_IDS=30; OVERLAP=5; WORKERS=4

def fp(p):
    return hashlib.sha256('|'.join(str(p.get(k,'')) for k in ['id','deadline','sourceRFxStatus','sourceRFx','scope','freshnessStatus']).encode()).hexdigest()

def main():
    now=datetime.now(TZ); OUT.parent.mkdir(parents=True,exist_ok=True); REVIEW.parent.mkdir(parents=True,exist_ok=True); PREV.parent.mkdir(parents=True,exist_ok=True)
    previous=json.loads(PREV.read_text()) if PREV.exists() else []; prev={p['id']:p for p in previous}
    ds=json.loads(DISC.read_text()) if DISC.exists() else {}; high=int(ds.get('high_water',46250))
    known_ids={int(p['sourceDetailId']) for p in previous if str(p.get('sourceDetailId','')).isdigit()}
    start=max(1,high-OVERLAP+1); end=high+DAILY_NEW_IDS; discovery=set(range(start,end+1)); ids=sorted(known_ids|discovery)
    print(f'Daily procurement monitor: {len(known_ids)} known-active IDs + lightweight discovery {start}–{end}.')
    results=[]
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for r in ex.map(fetch_detail,ids): results.append(r)
    current={}; review=[]; explicit_remove=set(); max_valid=high; failures=0
    for r in results:
        did=r['detail_id']; rid=f'msproc-{did}'; old=prev.get(rid)
        if not r['ok']:
            if r['kind'] in {'network_error','http_error'}: failures+=1
            if old:
                current[rid]=mark_stale(old,now,r.get('error',r['kind'])); review.append({'detail_id':did,'decision':'preserve_stale','reason':r.get('error',r['kind'])})
            continue
        max_valid=max(max_valid,did); fields=parse_fields(r['html']); closed,why=explicit_closed(fields,now)
        if old and closed:
            explicit_remove.add(rid); review.append({'detail_id':did,'decision':'explicitly_remove','reason':why,'fields':fields}); continue
        county=infer_county(fields); deadline=parse_dt(fields.get('Submission Date','')); reasons=[]
        if not deadline: reasons.append('missing_or_unparseable_deadline')
        if not construction_relevant(fields): reasons.append('not_construction_relevant')
        if not county: reasons.append('outside_or_unresolved_territory')
        if not reasons:
            current[rid]=normalize(did,fields,county,now); review.append({'detail_id':did,'decision':'publish','county':county})
        elif old:
            current[rid]=mark_stale(old,now,','.join(reasons)); review.append({'detail_id':did,'decision':'preserve_stale','reason':reasons})
        else:
            review.append({'detail_id':did,'decision':'skip_discovery_candidate','reason':reasons})
    for rid,old in prev.items():
        if rid not in current and rid not in explicit_remove: current[rid]=mark_stale(old,now,'not_rechecked_guard')
    cur=list(current.values()); OUT.write_text(json.dumps(cur,indent=2)); REVIEW.write_text(json.dumps(review,indent=2))
    curb={p['id']:p for p in cur}; events=[]
    for rid,p in curb.items():
        old=prev.get(rid)
        if not old: events.append({'kind':'new_project','project_id':rid,'after':p})
        elif fp(old)!=fp(p): events.append({'kind':'project_changed','project_id':rid,'before':old,'after':p})
    for rid in explicit_remove:
        if rid in prev: events.append({'kind':'source_project_no_longer_open','project_id':rid,'before':prev[rid]})
    summary={'new':sum(e['kind']=='new_project' for e in events),'changed':sum(e['kind']=='project_changed' for e in events),'no_longer_open':sum(e['kind']=='source_project_no_longer_open' for e in events),'stale_unverified':sum(p.get('freshnessStatus')=='stale_unverified' for p in cur)}
    CHANGES.write_text(json.dumps({'source':'ms_procurement','generated_at':datetime.now(timezone.utc).isoformat(),'summary':summary,'events':events},indent=2)); PREV.write_text(json.dumps(cur,indent=2)); DISC.write_text(json.dumps({'high_water':max_valid,'last_daily_discovery_start':start,'last_daily_discovery_end':end,'checked_at':now.isoformat()},indent=2)); STATUS.write_text(json.dumps({'ok':True,'checked_at':now.isoformat(),'known_active_checked':len(known_ids),'lightweight_discovery_count':len(discovery),'network_or_http_failures':failures,'current_records':len(cur),'stale_unverified':summary['stale_unverified'],'explicitly_removed':summary['no_longer_open']},indent=2))
    print(f'Current procurement records preserved/published: {len(cur)}'); print(f'Stale but preserved: {summary["stale_unverified"]}'); print(summary)
if __name__=='__main__': main()
