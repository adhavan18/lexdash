"""
Stage 4: turn data/scored.csv (accumulated across many apify_discover.py
region runs) into a styled Excel workbook grouped by region/state, merged
with the confirmed trade-press companies (Lawn & Landscape Top 100 / LM150)
found via manual research.

Usage: python build_excel.py
Output: data/commercial_landscapers_by_state_<timestamp>.xlsx -- each run
creates a NEW file (never overwrites a prior one) so you can compare runs
or keep a snapshot from before/after a change.
"""
import csv
import os
import re
from datetime import datetime

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from confirmed_companies import CONFIRMED_ROWS

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SCORED_PATH = os.path.join(DATA_DIR, "scored.csv")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_PATH = os.path.join(DATA_DIR, f"commercial_landscapers_by_state_{TIMESTAMP}.xlsx")

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
    for company, city, state, revenue, confidence, notes, _domain in CONFIRMED_ROWS:
        ws1.append([company, city, state, STATE_TO_REGION.get(state, "Unknown"), revenue, confidence, notes])
    for i, h in enumerate(headers1, 1):
        ws1.column_dimensions[get_column_letter(i)].width = max(18, len(h) + 4)
    ws1.column_dimensions["A"].width = 30
    ws1.column_dimensions["G"].width = 45
    for row in ws1.iter_rows(min_row=2, min_col=5, max_col=5):
        for cell in row:
            if cell.value is not None:
                cell.number_format = "$#,##0"

    # Sheet 2: pipeline candidates (Apify/Firecrawl discovered, combined revenue estimate)
    ws2 = wb.create_sheet("Pipeline Candidates")
    headers2 = ["Domain", "Region", "State", "Confidence", "Estimated Employees", "Employee Source",
                "Estimated Revenue (USD)", "Confirmed Federal Contracts (USD)", "Likely >$5M",
                "Verify Priority", "Verify Reason", "Fallback Score", "Review Count",
                "Years in Business", "Fleet Size", "Location Count", "Client Portfolio Size",
                "Sqft/Acreage Managed", "Indeed Job Postings", "Client Types", "Website"]
    ws2.append(headers2)
    style_header(ws2, len(headers2))
    for r in scored_rows:
        state = parse_state(r.get("region", ""))
        ws2.append([
            r.get("domain"), r.get("region"), state, r.get("confidence"),
            r.get("estimated_employees"), r.get("employee_source"),
            r.get("estimated_revenue_usd"), r.get("confirmed_federal_contracts_usd"),
            r.get("likely_over_5m"), r.get("manual_verification_priority"),
            r.get("manual_verification_reason"), r.get("fallback_score"), r.get("review_count"),
            r.get("years_in_business"), r.get("fleet_size"), r.get("location_count"),
            r.get("client_portfolio_size"), r.get("sqft_or_acreage_managed"),
            r.get("indeed_job_postings"), r.get("client_types"), r.get("sample_url"),
        ])
    for i, h in enumerate(headers2, 1):
        ws2.column_dimensions[get_column_letter(i)].width = max(16, len(h) + 4)
    ws2.column_dimensions["K"].width = 55
    ws2.column_dimensions["U"].width = 40
    for col in ("G", "H"):
        for row in ws2.iter_rows(min_row=2, min_col=ord(col) - 64, max_col=ord(col) - 64):
            for cell in row:
                if cell.value not in (None, ""):
                    cell.number_format = "$#,##0"

    priority_fill = {
        "High": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
        "Medium": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
        "Low": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    }
    for row in ws2.iter_rows(min_row=2, min_col=10, max_col=10):
        for cell in row:
            fill = priority_fill.get(cell.value)
            if fill:
                cell.fill = fill

    # Sheet: shortlist of rows worth spending manual/paid verification effort on
    ws2b = wb.create_sheet("Needs Manual Verification")
    headers2b = ["Domain", "Region", "State", "Verify Priority", "Verify Reason",
                 "Estimated Revenue (USD)", "Confidence", "Website"]
    ws2b.append(headers2b)
    style_header(ws2b, len(headers2b))
    high_priority_rows = [r for r in scored_rows if r.get("manual_verification_priority") == "High"]
    for r in high_priority_rows:
        state = parse_state(r.get("region", ""))
        ws2b.append([
            r.get("domain"), r.get("region"), state, r.get("manual_verification_priority"),
            r.get("manual_verification_reason"), r.get("estimated_revenue_usd"),
            r.get("confidence"), r.get("sample_url"),
        ])
    for i, h in enumerate(headers2b, 1):
        ws2b.column_dimensions[get_column_letter(i)].width = max(16, len(h) + 4)
    ws2b.column_dimensions["E"].width = 55
    ws2b.column_dimensions["H"].width = 40
    for row in ws2b.iter_rows(min_row=2, min_col=6, max_col=6):
        for cell in row:
            if cell.value not in (None, ""):
                cell.number_format = "$#,##0"

    # Sheet 3: everything grouped by region/state (confirmed + pipeline combined)
    ws3 = wb.create_sheet("By Region & State")
    headers3 = ["Region", "State", "Company/Domain", "Source", "Revenue (confirmed or estimated)"]
    ws3.append(headers3)
    style_header(ws3, len(headers3))

    combined = []
    for company, city, state, revenue, confidence, notes, _domain in CONFIRMED_ROWS:
        combined.append((STATE_TO_REGION.get(state, "Unknown"), state, company, "Trade Press (confirmed)", revenue))
    for r in scored_rows:
        state = parse_state(r.get("region", ""))
        combined.append((STATE_TO_REGION.get(state, "Unknown"), state, r.get("domain"),
                          "Pipeline (employee-based estimate)", r.get("estimated_revenue_usd")))

    combined.sort(key=lambda x: (x[0], x[1]))
    for row in combined:
        ws3.append(list(row))
    for i, h in enumerate(headers3, 1):
        ws3.column_dimensions[get_column_letter(i)].width = max(18, len(h) + 4)
    ws3.column_dimensions["C"].width = 30
    for row in ws3.iter_rows(min_row=2, min_col=5, max_col=5):
        for cell in row:
            if cell.value not in (None, ""):
                cell.number_format = "$#,##0"

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
        ["apify_discover.py (Google Maps) + enrich.py (website scraping + Indeed job-posting"],
        ["count) + usaspending_enrich.py (federal contract lookup) + score.py."],
        [""],
        ["'Confidence' column, in priority order (best signal wins per company):"],
        ["  1. confirmed_federal_contracts -- USASpending.gov shows this company alone"],
        ["     holds >= $5M in federal landscaping (NAICS 561730) contract awards."],
        ["     This is VERIFIED dollar data, not an estimate."],
        ["  2. employee_based -- Estimated Revenue = Estimated Employees x $120,000/employee"],
        ["     (score.py's REVENUE_PER_EMPLOYEE constant, an industry rule-of-thumb)."],
        ["     Estimated Employees comes from, in priority order:"],
        ["       a. employee_count stated directly on the company website (most reliable)"],
        ["       b. indeed_job_postings x 15 -- open-role volume on Indeed as an independent"],
        ["          headcount proxy (a company only has a fraction of staff hiring at once)"],
        ["       c. fleet_size x 2.5 -- crew-size proxy from stated truck/fleet count"],
        ["       d. location_count x 15 -- average branch size proxy from stated office count"],
        ["  3. partial_federal_contracts_only -- has some federal contract dollars, but not"],
        ["     enough alone to clear $5M, and no employee estimate available either."],
        ["  4. fallback_heuristic_only -- no employee or contract signal at all. 'Likely >$5M'"],
        ["     defaults to False; 'Fallback Score' (years in business, client portfolio size,"],
        ["     sqft/acreage managed, service area count, client types, review count/rating)"],
        ["     is the only ranking signal -- use it to spot-check manually, not as a revenue"],
        ["     estimate."],
        [""],
        ["Everything except 'confirmed_federal_contracts' is still an ESTIMATE. Most company"],
        ["websites don't state headcount, so many rows will fall back to weaker proxies or"],
        ["no employee estimate at all -- treat this as a ranked shortlist to manually verify,"],
        ["not ground truth."],
        [""],
        ["'Verify Priority' / 'Verify Reason' columns (also color-coded green/yellow/red in"],
        ["the Pipeline Candidates tab) tell you WHICH rows to trust as-is vs. which need a"],
        ["manual or paid check before you act on them:"],
        ["  Low (green)    = confirmed federal contracts, or a direct employee count stated"],
        ["                   on the company's own site -- reasonably trustworthy as-is."],
        ["  Medium (yellow)= revenue estimate comes from a proxy (job postings/fleet/branch"],
        ["                   count), not a stated number -- directionally useful, not precise."],
        ["  High (red)     = either the estimate sits right on the $5M line (could go either"],
        ["                   way) or there's no employee/contract signal at all and the row"],
        ["                   is ranked only by soft signals (reviews, tenure, portfolio size)."],
        ["                   These are the rows worth spending manual research or a paid tool"],
        ["                   (D&B, ZoomInfo) on before treating them as qualified."],
        ["The 'Needs Manual Verification' tab is pre-filtered to just the High-priority rows."],
        [""],
        ["To add the federal contract check: python usaspending_enrich.py (free API, no key"],
        ["needed) before running score.py -- it writes data/govt_contracts.json which"],
        ["score.py automatically picks up if present."],
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
