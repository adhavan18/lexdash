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
        "employee_count": {"type": "number", "description": "Number of employees, if stated anywhere on the site"},
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
    "website: years in business, employee count, fleet/crew size, service "
    "areas, client types served, certifications, and whether it has multiple "
    "branch locations. Leave fields blank if not stated; do not guess."
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

    enriched = enrich_candidates(candidates)

    out_path = os.path.join(DATA_DIR, "enriched.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2)
    print(f"Saved {len(enriched)} enriched records to {out_path}")


if __name__ == "__main__":
    main()
