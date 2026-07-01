"""
Stage 2b (optional, additive): cross-reference candidates against
USASpending.gov's free public API for actual federal contract dollar
amounts under the Landscaping Services NAICS code (561730). This is real
verified revenue for the subset of companies doing government grounds-
maintenance work -- not a proxy like the other signals.

No API key required. Run after enrich.py -- only checks companies that were
actually enriched (data/enriched.json), not the full raw candidates.json, so
a --limit 50 enrich.py run stays fast here too. Safe to re-run (idempotent,
matches by domain, skips ones already looked up).
"""
import json
import os
import sys
import time

import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
NAICS_LANDSCAPING = "561730"
API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"


def search_awards_for_company(company_name: str, retries: int = 3):
    """Returns total obligated federal contract dollars found for this company
    name under the landscaping NAICS code over the last 5 fiscal years."""
    payload = {
        "filters": {
            "award_type_codes": ["A", "B", "C", "D"],
            "naics_codes": [NAICS_LANDSCAPING],
            "recipient_search_text": [company_name],
            "time_period": [{"start_date": "2019-10-01", "end_date": "2025-09-30"}],
        },
        "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency"],
        "page": 1,
        "limit": 50,
        "sort": "Award Amount",
        "order": "desc",
    }
    for attempt in range(retries):
        try:
            resp = requests.post(API_URL, json=payload, timeout=30)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json().get("results", [])
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                print(f"  USASpending lookup failed for '{company_name}': {e}")
                return []
            time.sleep(2 ** attempt)
    return []


def main():
    enriched_path = os.path.join(DATA_DIR, "enriched.json")
    if not os.path.exists(enriched_path):
        print(f"No {enriched_path} found -- run enrich.py first.")
        return
    with open(enriched_path, encoding="utf-8") as f:
        candidates = json.load(f)

    govt_path = os.path.join(DATA_DIR, "govt_contracts.json")
    existing = {}
    if os.path.exists(govt_path):
        with open(govt_path, encoding="utf-8") as f:
            existing = json.load(f)

    to_check = [c for c in candidates if c.get("domain") not in existing]

    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        to_check = to_check[:limit]

    print(f"{len(candidates) - len(to_check)} already checked or n/a, {len(to_check)} to check.")

    for c in to_check:
        name = c.get("name") or c.get("title")
        domain = c.get("domain")
        if not name:
            continue
        print(f"Checking federal contracts for {name}...")
        awards = search_awards_for_company(name)
        total = sum(a.get("Award Amount", 0) or 0 for a in awards)
        existing[domain] = {
            "company_name": name,
            "total_federal_landscaping_awards_usd": total,
            "award_count": len(awards),
        }
        time.sleep(0.5)

    with open(govt_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    with_contracts = sum(1 for v in existing.values() if v["total_federal_landscaping_awards_usd"] > 0)
    print(f"Saved {len(existing)} lookups to {govt_path}")
    print(f"  {with_contracts} companies have confirmed federal landscaping contract dollars")


if __name__ == "__main__":
    main()
