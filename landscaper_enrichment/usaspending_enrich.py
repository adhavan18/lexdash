"""
Stage 2b (optional, additive): cross-reference candidates against
USASpending.gov's free public API for actual federal contract dollar
amounts under the Landscaping Services NAICS code (561730). This is real
verified revenue for the subset of companies doing government grounds-
maintenance work -- not a proxy like the other signals.

No API key required. Run any time after discover.py/apify_discover.py has
produced data/candidates.json; safe to re-run (idempotent, matches by name).
"""
import json
import os
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
    candidates_path = os.path.join(DATA_DIR, "candidates.json")
    with open(candidates_path, encoding="utf-8") as f:
        candidates = json.load(f)

    govt_path = os.path.join(DATA_DIR, "govt_contracts.json")
    existing = {}
    if os.path.exists(govt_path):
        with open(govt_path, encoding="utf-8") as f:
            existing = json.load(f)

    for c in candidates:
        name = c.get("name") or c.get("title")
        domain = c.get("domain")
        if not name or domain in existing:
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
