#!/usr/bin/env python3
"""
Live MDOT Proposed Lettings collector.

Uses only the Python standard library:
- downloads the official MDOT page
- parses server-rendered table rows
- filters to the Project Radar South Mississippi coverage counties
- saves a normalized source snapshot
- refuses to overwrite a good snapshot if parsing unexpectedly returns zero rows
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from pathlib import Path
from datetime import datetime, timezone
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
URL = "https://mdot.ms.gov/applications/Schedule_of_Proposed_Projects/ProposedLetting.aspx"
RAW_HTML = ROOT / "data" / "snapshots" / "mdot_proposed_live.html"
SNAP_JSON = ROOT / "data" / "snapshots" / "mdot_proposed.json"

# Broad South Mississippi / Columbia-centered expansion set.
TARGET_COUNTIES = {
    "Marion","Lamar","Forrest","Jones","Perry","Greene","Pearl River","Walthall",
    "Jefferson Davis","Covington","Lawrence","Pike","Lincoln","Franklin","Simpson",
    "Stone","Clarke","Jasper","Wayne","Harrison"
}

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]
        self.in_tr=False
        self.in_td=False
        self.cell=[]
        self.row=[]

    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        if tag=="tr":
            self.in_tr=True
            self.row=[]
        elif tag in ("td","th") and self.in_tr:
            self.in_td=True
            self.cell=[]

    def handle_data(self, data):
        if self.in_td:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag in ("td","th") and self.in_td:
            text=" ".join("".join(self.cell).split())
            self.row.append(text)
            self.in_td=False
        elif tag=="tr" and self.in_tr:
            if self.row:
                self.rows.append(self.row)
            self.in_tr=False

def fetch():
    req=Request(URL, headers={
        "User-Agent":"Mozilla/5.0 ProjectRadar/0.5.2 (+public-project-monitoring)"
    })
    with urlopen(req, timeout=30) as r:
        body=r.read()
    RAW_HTML.parent.mkdir(parents=True, exist_ok=True)
    RAW_HTML.write_bytes(body)
    return body.decode("utf-8", errors="ignore")

def parse_rows(html):
    parser=TableParser()
    parser.feed(html)
    out=[]
    date_re=re.compile(r"^20\d{2}\s*/\s*\d{1,2}$")

    for row in parser.rows:
        # Find the date cell rather than assuming the grid's first column count.
        date_idx=None
        for i, cell in enumerate(row):
            if date_re.match(cell):
                date_idx=i
                break
        if date_idx is None:
            continue

        cells=row[date_idx:]
        # Expected logical columns after GEOM:
        # month, district, 2mnth, proj no, fed proj no, parallel, county, route, scope, termini
        if len(cells) < 9:
            continue

        month=cells[0].replace(" ","")
        district=cells[1]
        # Telerik grid may emit an empty "2 Mnth" cell; locate project no by pattern.
        proj_idx=None
        for i in range(2, min(len(cells),6)):
            if re.match(r"^\d{6}/\d{6}$", cells[i]):
                proj_idx=i
                break
        if proj_idx is None:
            continue

        proj_no=cells[proj_idx]
        fed_proj=cells[proj_idx+1] if proj_idx+1 < len(cells) else ""
        tail=cells[proj_idx+2:]

        # County must be one of our known counties. This makes the parser resilient
        # to optional "Parallel To Proj No" content.
        county_idx=None
        for i,c in enumerate(tail):
            if c in TARGET_COUNTIES:
                county_idx=i
                break
        if county_idx is None:
            continue

        county=tail[county_idx]
        route=tail[county_idx+1] if county_idx+1 < len(tail) else ""
        scope=tail[county_idx+2] if county_idx+2 < len(tail) else ""
        termini=" ".join(tail[county_idx+3:]) if county_idx+3 < len(tail) else ""
        parallel=" ".join(tail[:county_idx]).strip()

        out.append({
            "month":month,
            "district":district,
            "project_no":proj_no,
            "fed_project_no":fed_proj,
            "parallel_to_project_no":parallel,
            "county":county,
            "route":route,
            "scope":scope,
            "termini":termini
        })
    return out

def main():
    print(f"Fetching official MDOT proposed lettings: {URL}")
    html=fetch()
    records=parse_rows(html)

    if not records:
        print("ERROR: Parsed zero target records. Existing JSON snapshot was NOT overwritten.", file=sys.stderr)
        print(f"Raw HTML was saved to {RAW_HTML} for diagnosis.", file=sys.stderr)
        sys.exit(2)

    payload={
        "source":URL,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),
        "records":records
    }
    SNAP_JSON.write_text(json.dumps(payload, indent=2))
    print(f"Saved {len(records)} live South-Mississippi MDOT records to {SNAP_JSON}")

if __name__=="__main__":
    main()
