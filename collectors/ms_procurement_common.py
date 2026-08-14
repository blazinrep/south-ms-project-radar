#!/usr/bin/env python3
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json, re

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://www.ms.gov/dfa/contract_bid_search/Bid/Details/'
TZ = ZoneInfo('America/Chicago')
LABELS = {'Smart Number','Advertised Date','RFx #','Submission Date','RFx Status','Major Procurement Category','RFx Opening Date','Sub Procurement Category','RFx Type','Agency','RFx Description'}
COUNTY_ANCHORS = {
'Marion':(31.2518,-89.8354),'Forrest':(31.3271,-89.2903),'Lamar':(31.1432,-89.4098),'Jones':(31.6941,-89.1306),'Perry':(31.2021,-89.0367),'Greene':(31.1557,-88.5578),'Pearl River':(30.8407,-89.5342),'Walthall':(31.1160,-90.1420),'Jefferson Davis':(31.5985,-89.8670),'Covington':(31.6454,-89.5553),'Lawrence':(31.5538,-90.1070),'Pike':(31.1432,-90.4587),'Lincoln':(31.5791,-90.4407),'Franklin':(31.4724,-90.8968),'Simpson':(31.9618,-89.8701),'Stone':(30.8582,-89.1353),'Clarke':(32.0404,-88.7281),'Jasper':(31.9790,-89.2873),'Wayne':(31.6740,-88.6461),'Harrison':(30.3674,-89.0928),'Hancock':(30.3088,-89.3300),'Jackson':(30.3674,-88.5561)}
CITY_TO_COUNTY = {'columbia':'Marion','hattiesburg':'Forrest','purvis':'Lamar','laurel':'Jones','ellisville':'Jones','new augusta':'Perry','leakesville':'Greene','poplarville':'Pearl River','tylertown':'Walthall','prentiss':'Jefferson Davis','collins':'Covington','monticello':'Lawrence','magnolia':'Pike','mccomb':'Pike','brookhaven':'Lincoln','meadville':'Franklin','mendenhall':'Simpson','wiggins':'Stone','quitman':'Clarke','bay springs':'Jasper','waynesboro':'Wayne','gulfport':'Harrison','bay saint louis':'Hancock','bay st louis':'Hancock','pascagoula':'Jackson','moss point':'Jackson'}

class Cells(HTMLParser):
    def __init__(self):
        super().__init__(); self.on=False; self.buf=[]; self.cells=[]
    def handle_starttag(self,t,a):
        if t.lower() in ('td','th'): self.on=True; self.buf=[]
    def handle_data(self,d):
        if self.on: self.buf.append(d)
    def handle_endtag(self,t):
        if t.lower() in ('td','th') and self.on:
            self.cells.append(' '.join(''.join(self.buf).split())); self.on=False

def fetch_detail(detail_id, timeout=15):
    url=BASE+str(detail_id)+'?AppId=1'
    try:
        req=Request(url,headers={'User-Agent':'Mozilla/5.0 ProjectRadar/0.6.4','Accept':'text/html'})
        with urlopen(req,timeout=timeout) as r: html=r.read().decode('utf-8',errors='ignore')
        if 'Procurement Details' not in html or 'Smart Number' not in html:
            return {'ok':False,'kind':'not_found','detail_id':detail_id}
        return {'ok':True,'kind':'fetched','detail_id':detail_id,'html':html}
    except HTTPError as e:
        if e.code in (404,410): return {'ok':False,'kind':'not_found','detail_id':detail_id}
        return {'ok':False,'kind':'http_error','detail_id':detail_id,'error':f'HTTP {e.code}'}
    except (URLError,OSError,TimeoutError) as e:
        return {'ok':False,'kind':'network_error','detail_id':detail_id,'error':str(e)}

def parse_fields(html):
    p=Cells(); p.feed(html); out={}
    for i,c in enumerate(p.cells[:-1]):
        if c in LABELS: out[c]=p.cells[i+1]
    return out

def parse_dt(s):
    if not s or s.upper()=='N/A': return None
    for fmt in ('%m/%d/%Y %I:%M %p','%m/%d/%Y %H:%M','%m/%d/%Y'):
        try: return datetime.strptime(s,fmt).replace(tzinfo=TZ)
        except ValueError: pass
    return None

def infer_county(fields):
    text=' '.join(str(v) for v in fields.values()).lower()
    for c in COUNTY_ANCHORS:
        if re.search(rf'\b{re.escape(c.lower())}\s+county\b',text): return c
    for city,c in CITY_TO_COUNTY.items():
        if re.search(rf'\b{re.escape(city)}\b',text): return c
    return None

def construction_relevant(fields):
    major=fields.get('Major Procurement Category','').upper(); sub=fields.get('Sub Procurement Category','').upper(); desc=fields.get('RFx Description','').lower()
    return major=='CONSTRUCTION' or 'CONSTRUCTION' in sub or any(x in desc for x in ('sealed bids','construction of','road construction','bridge','culvert','drainage','site work','sitework','water main','wastewater','sewer','paving','overlay','excavation'))

def explicit_closed(fields, now):
    status=fields.get('RFx Status','').strip().lower(); deadline=parse_dt(fields.get('Submission Date',''))
    if status in {'closed','archived','cancelled','canceled'}: return True, f'source_status_{status}'
    if deadline and deadline <= now: return True, 'submission_deadline_passed'
    return False, None

def capability_tags(text):
    t=text.lower(); out=set(); rules={'excavation':['excavat','earthwork','culvert','ditch'],'grading':['grading','road construction','site work','sitework'],'drainage':['drainage','storm sewer','culvert','ditch'],'utilities':['water main','sewer','utility','wastewater','lift station'],'clearing':['clearing','grubbing','debris removal'],'erosion_control':['erosion','riprap','stabilization'],'hauling':['hauling','aggregate','earthwork'],'paving_base':['paving','overlay','asphalt','milling','base course']}
    for k,ws in rules.items():
        if any(w in t for w in ws): out.add(k)
    return sorted(out)

def normalize(detail_id, fields, county, now):
    desc=fields.get('RFx Description',''); sub=fields.get('Sub Procurement Category',''); caps=capability_tags(desc+' '+sub); lat,lon=COUNTY_ANCHORS[county]; deadline=parse_dt(fields.get('Submission Date',''))
    return {'id':f'msproc-{detail_id}','name':f"{county} / {fields.get('Smart Number','MS Procurement')}",'county':county,'city':f'{county} County','lat':lat,'lon':lon,'locationPrecision':'county_seat_approx','status':'Accepting bids','bucket':'act','deadline':deadline.isoformat() if deadline else None,'prebid':None,'value':None,'match':min(99,55+8*len(caps)),'timing':96,'confidence':96,'distance':None,'scope':[x for x in [sub,desc[:320]] if x],'why':'Official Mississippi procurement detail page with a future published deadline.','owner':fields.get('Agency','Mississippi public agency'),'contact':'See official record and attachments','source':BASE+str(detail_id)+'?AppId=1','verified':now.date().isoformat(),'sourceType':'Official Mississippi procurement','capabilityTags':caps,'lifecycleStage':'open_procurement','signalType':'public_bid','nextMove':'Review the official attachments, confirm exact work location and scope, then decide prime or subcontract pursuit.','changeStatus':'new','freshnessStatus':'live_verified','automation':{'sourceKey':'ms_procurement','lastSeen':now.isoformat(),'lastCheckStatus':'live_verified','needsHumanReview':True},'sourceDetailId':str(detail_id),'sourceSmartNumber':fields.get('Smart Number'),'sourceRFx':fields.get('RFx #'),'sourceRFxStatus':fields.get('RFx Status'),'majorProcurementCategory':fields.get('Major Procurement Category'),'subProcurementCategory':sub,'submissionDateRaw':fields.get('Submission Date')}

def mark_stale(record, now, reason):
    p=json.loads(json.dumps(record)); p['freshnessStatus']='stale_unverified'; p['status']=p.get('status','Accepting bids').split(' ·')[0]+' · verification delayed'; auto=p.setdefault('automation',{}); auto['lastCheckStatus']='stale_unverified'; auto['lastCheckFailedAt']=now.isoformat(); auto['lastCheckFailureReason']=reason; return p
