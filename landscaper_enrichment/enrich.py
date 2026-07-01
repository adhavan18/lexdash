"""
Stage 2: enrich each candidate with revenue-proxy signals scraped from its
own website (fleet size, years in business, service area, client types,
headcount language) using Firecrawl's structured /extract.
"""
import json
import os
import time

from firecrawl_client import extract

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "years_in_business": {"type": "number", "description": "How many years the company has operated, if stated"},
        "employee_count": {"type": "number", "description": "Number of employees/team members/staff, if stated anywhere on the site (About, Careers, Our Team pages often mention this, e.g. '150+ employees' or 'team of 200')"},
        "fleet_size": {"type": "number", "description": "Number of trucks/vehicles/crews mentioned, if any"},
        "service_areas": {"type": "array", "items": {"type": "string"}, "description": "Cities/regions served"},
        "client_types": {
            "type": "array",
            "items": {"type": "string", "enum": ["commercial", "residential", "HOA", "municipal", "industrial"]},
            "description": "Types of clients the company serves",
        },
        "certifications": {"type": "array", "items": {"type": "string"}, "description": "Industry certifications (e.g. NALP, ISA, QWEL)"},
        "has_multiple_locations": {"type": "boolean", "description": "Whether the company lists more than one office/branch"},
    },
    "required": [],
}

EXTRACT_PROMPT = (
    "Extract company size and scale signals from this landscaping company's "
    "website. Employee count is the most important field -- check About Us, "
    "Careers, Our Team, and homepage hero text for phrasing like 'our team of "
    "X', 'X employees', 'X+ crew members', or similar. Also extract: years in "
    "business, fleet/truck/crew count, service areas, client types served, "
    "certifications, and whether it has multiple branch locations. Leave "
    "fields blank if not stated; do not guess or estimate."
)


def enrich_candidates(candidates, sleep_between=3.0):
    enriched = []
    for c in candidates:
        url = c.get("sample_url")
        print(f"Enriching {c['domain']}...")
        record = dict(c)
        try:
            result = extract(url, EXTRACT_SCHEMA, EXTRACT_PROMPT)
            record["signals"] = result.get("data", {})
        except Exception as e:
            print(f"  extract failed: {e}")
            record["signals"] = {}
        # carry over Maps-sourced signals (present when discovered via apify_discover.py)
        record["signals"]["review_count"] = c.get("review_count")
        record["signals"]["rating"] = c.get("rating")
        enriched.append(record)
        time.sleep(sleep_between)
    return enriched


def main():
    in_path = os.path.join(DATA_DIR, "candidates.json")
    with open(in_path, encoding="utf-8") as f:
        candidates = json.load(f)

    out_path = os.path.join(DATA_DIR, "enriched.json")
    existing = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
    already_done = {r["domain"] for r in existing}

    to_enrich = [c for c in candidates if c["domain"] not in already_done]
    print(f"{len(already_done)} already enriched, {len(to_enrich)} new to process.")

    newly_enriched = enrich_candidates(to_enrich)
    all_enriched = existing + newly_enriched

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_enriched, f, indent=2)
    print(f"Saved {len(all_enriched)} total enriched records to {out_path}")


if __name__ == "__main__":
    main()
