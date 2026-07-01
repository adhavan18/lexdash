"""
Stage 4: turn data/scored.csv (accumulated across many apify_discover.py
region runs) into a styled Excel workbook grouped by region/state, merged
with the confirmed trade-press companies (Lawn & Landscape Top 100 / LM150)
found via manual research.

Usage: python build_excel.py
Output: data/commercial_landscapers_by_state.xlsx
"""
import csv
import os
import re

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SCORED_PATH = os.path.join(DATA_DIR, "scored.csv")
OUT_PATH = os.path.join(DATA_DIR, "commercial_landscapers_by_state.xlsx")

STATE_TO_REGION = {
    "CT": "Northeast", "ME": "Northeast", "MA": "Northeast", "NH": "Northeast",
    "RI": "Northeast", "VT": "Northeast", "NJ": "Northeast", "NY": "Northeast",
    "PA": "Northeast",
    "IL": "Midwest", "IN": "Midwest", "MI": "Midwest", "OH": "Midwest",
    "WI": "Midwest", "IA": "Midwest", "KS": "Midwest", "MN": "Midwest",
    "MO": "Midwest", "NE": "Midwest", "ND": "Midwest", "SD": "Midwest",
    "DE": "South", "FL": "South", "GA": "South", "MD": "South", "NC": "South",
    "SC": "South", "VA": "South", "DC": "South", "WV": "South", "AL": "South",
    "KY": "South", "MS": "South", "TN": "South", "AR": "South", "LA": "South",
    "OK": "South", "TX": "South",
    "AZ": "West", "CO": "West", "ID": "West", "MT": "West", "NV": "West",
    "NM": "West", "UT": "West", "WY": "West", "AK": "West", "CA": "West",
    "HI": "West", "OR": "West", "WA": "West",
}

# Confirmed from trade-press rankings (Lawn & Landscape Top 100, LM150),
# gathered via manual web search since the source sites block scraping.
CONFIRMED_ROWS = [
    ("BrightView Holdings", "Blue Bell", "PA", 2_770_000_000, "Confirmed", "#1 LM150, 11 consecutive years at top"),
    ("The Davey Tree Expert Company", "Kent", "OH", 1_690_000_000, "Confirmed", "#2 LM150"),
    ("TruGreen", "Memphis", "TN", 1_500_000_000, "Confirmed (approx.)", "#3 LM150"),
    ("Yellowstone Landscape", "Bunnell", "FL", 773_800_000, "Confirmed", "Largest PE-backed pure-play commercial landscaper"),
    ("SavATree", "Bedford Hills", "NY", 479_000_000, "Confirmed", "2024 revenue"),
    ("Landscape Workshop", "Birmingham", "AL", 209_000_000, "Confirmed", "#23 on Top 100"),
    ("Ryan Lawn & Tree", "Merriam", "KS", 86_000_000, "Confirmed", "#47 on Top 100"),
    ("Massey Services", "Orlando", "FL", 71_600_000, "Confirmed", "2,060 employees"),
    ("Level Green Landscaping", "Hyattsville", "MD", 44_000_000, "Confirmed", "#88 on Top 100"),
    ("Greenscape", "Raynham", "MA", 37_000_000, "Confirmed", "325 employees"),
    ("Southern Botanical", "Dallas", "TX", None, "Confirmed rank, revenue not sourced", "#46 on 2026 Top 100"),
    ("Bland Landscaping", "Apex", "NC", None, "Confirmed PE-backed, exact revenue not public", "Recapitalized as PE-backed platform"),
    ("Ruppert Landscape", "Laytonsville", "MD", None, "Known large national player, exact revenue not sourced", "Multi-state commercial firm"),
    ("U.S. Lawns", "Orlando", "FL", None, "Franchise network, revenue varies by franchisee", "National commercial franchise brand"),
]

STATE_RE = re.compile(r",\s*([A-Z]{2})\s*$")


def parse_state(region: str) -> str:
    if not region:
        return "Unknown"
    m = STATE_RE.search(region.strip())
    return m.group(1) if m else "Unknown"


def load_scored_rows():
    if not os.path.exists(SCORED_PATH):
        print(f"No {SCORED_PATH} found yet -- run discover/apify_discover -> enrich -> score first.")
        return []
    with open(SCORED_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def style_header(ws, ncols):
    for i in range(1, ncols + 1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2F5233", end_color="2F5233", fill_type="solid")
        cell.alignment = Alignment(horizontal="center")


def main():
    scored_rows = load_scored_rows()

    wb = openpyxl.Workbook()

    # Sheet 1: confirmed trade-press companies (known revenue / known >$5M rank)
    ws1 = wb.active
    ws1.title = "Confirmed (Trade Press)"
    headers1 = ["Company", "HQ City", "State", "Region", "Revenue (USD)", "Confidence", "Notes"]
    ws1.append(headers1)
    style_header(ws1, len(headers1))
    for company, city, state, revenue, confidence, notes in CONFIRMED_ROWS:
        ws1.append([company, city, state, STATE_TO_REGION.get(state, "Unknown"), revenue, confidence, notes])
    for i, h in enumerate(headers1, 1):
        ws1.column_dimensions[get_column_letter(i)].width = max(18, len(h) + 4)
    ws1.column_dimensions["A"].width = 30
    ws1.column_dimensions["G"].width = 45
    for row in ws1.iter_rows(min_row=2, min_col=5, max_col=5):
        for cell in row:
            if cell.value is not None:
                cell.number_format = "$#,##0"

    # Sheet 2: pipeline candidates (Apify/Firecrawl discovered, scored, unverified revenue)
    ws2 = wb.create_sheet("Pipeline Candidates")
    headers2 = ["Domain", "Region", "State", "Score", "Likely >$5M", "Review Count",
                "Employee Count", "Years in Business", "Fleet Size", "Client Types", "Website"]
    ws2.append(headers2)
    style_header(ws2, len(headers2))
    for r in scored_rows:
        state = parse_state(r.get("region", ""))
        ws2.append([
            r.get("domain"), r.get("region"), state, r.get("score"), r.get("likely_over_5m"),
            r.get("review_count") or r.get("review_count", ""), r.get("employee_count"),
            r.get("years_in_business"), r.get("fleet_size"), r.get("client_types"), r.get("sample_url"),
        ])
    for i, h in enumerate(headers2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = max(16, len(h) + 4)
    ws2.column_dimensions["K"].width = 40

    # Sheet 3: everything grouped by region/state (confirmed + pipeline combined)
    ws3 = wb.create_sheet("By Region & State")
    headers3 = ["Region", "State", "Company/Domain", "Source", "Revenue or Score"]
    ws3.append(headers3)
    style_header(ws3, len(headers3))

    combined = []
    for company, city, state, revenue, confidence, notes in CONFIRMED_ROWS:
        combined.append((STATE_TO_REGION.get(state, "Unknown"), state, company, "Trade Press", revenue))
    for r in scored_rows:
        state = parse_state(r.get("region", ""))
        combined.append((STATE_TO_REGION.get(state, "Unknown"), state, r.get("domain"), "Pipeline", r.get("score")))

    combined.sort(key=lambda x: (x[0], x[1]))
    for row in combined:
        ws3.append(list(row))
    for i, h in enumerate(headers3, 1):
        ws3.column_dimensions[get_column_letter(i)].width = max(18, len(h) + 4)
    ws3.column_dimensions["C"].width = 30

    # Sheet 4: notes
    ws4 = wb.create_sheet("Notes")
    notes_text = [
        ["Commercial Landscaper Revenue Tracker - Methodology"],
        [""],
        [f"'Confirmed (Trade Press)' tab: {len(CONFIRMED_ROWS)} companies with revenue or a"],
        ["confirmed >$5M-cutoff ranking sourced from Lawn & Landscape Top 100 / LM150"],
        ["via manual web search (the source sites block automated scraping)."],
        [""],
        [f"'Pipeline Candidates' tab: {len(scored_rows)} companies discovered via"],
        ["apify_discover.py (Google Maps) + enrich.py (website scraping) + score.py."],
        ["The 'Score' and 'Likely >$5M' columns are a HEURISTIC, not verified revenue --"],
        ["treat this as a ranked shortlist to manually spot-check, not a ground truth."],
        [""],
        ["To grow the Pipeline Candidates count toward 500+:"],
        ["  Run apify_discover.py once per additional region, e.g.:"],
        ['    python apify_discover.py "Phoenix, AZ"'],
        ['    python apify_discover.py "Atlanta, GA"'],
        ['    python apify_discover.py "Denver, CO"'],
        ["  Each run APPENDS new candidates (deduped by domain) to data/candidates.json."],
        ["  Then re-run: python enrich.py  &&  python score.py  &&  python build_excel.py"],
        ["  enrich.py skips domains already enriched, so re-runs only cost API calls"],
        ["  for genuinely new candidates."],
        [""],
        ["Roughly 5-8 mid-size metro regions at ~60-100 unique candidates each should"],
        ["clear 500 total rows in Pipeline Candidates."],
    ]
    for line in notes_text:
        ws4.append(line)
    ws4.column_dimensions["A"].width = 90
    ws4["A1"].font = Font(bold=True, size=14)

    wb.save(OUT_PATH)
    print(f"Saved {OUT_PATH}")
    print(f"  Confirmed (Trade Press): {len(CONFIRMED_ROWS)} rows")
    print(f"  Pipeline Candidates: {len(scored_rows)} rows")


if __name__ == "__main__":
    main()
