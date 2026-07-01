"""
Stage 2: enrich each candidate with revenue-proxy signals scraped from its
own website (fleet size, years in business, service area, client types,
headcount language, branch count, client portfolio scale) using Firecrawl's
structured /extract, plus an independent Indeed job-posting-volume check.

Usage:
    python enrich.py                # process candidates not yet enriched
    python enrich.py --retry-failed # also re-process candidates whose last
                                     # attempt failed (e.g. hit a 402/429/403),
                                     # without re-spending API calls on ones
                                     # that already succeeded
"""
import json
import os
import sys
import time

from firecrawl_client import extract, search

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "years_in_business": {"type": "number", "description": "How many years the company has operated, if stated"},
        "employee_count": {"type": "number", "description": "Number of employees/team members/staff, if stated anywhere on the site (About, Careers, Our Team pages often mention this, e.g. '150+ employees' or 'team of 200')"},
        "fleet_size": {"type": "number", "description": "Number of trucks/vehicles/crews mentioned, if any"},
        "location_count": {"type": "number", "description": "Number of branch offices/locations, if stated (e.g. 'serving from 5 locations')"},
        "client_portfolio_size": {"type": "number", "description": "Number of properties, HOAs, or clients under contract, if stated (e.g. 'we maintain 200+ properties')"},
        "sqft_or_acreage_managed": {"type": "string", "description": "Square footage or acreage under management, if stated (e.g. '10 million sq ft', '500 acres')"},
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
    "business, fleet/truck/crew count, number of branch locations, number of "
    "properties/HOAs/clients served, square footage or acreage under "
    "management, service areas, client types served, certifications, and "
    "whether it has multiple branch locations. Leave fields blank if not "
    "stated; do not guess or estimate."
)


def count_indeed_job_postings(company_name: str) -> int:
    """Uses Firecrawl web search (not LinkedIn/Apollo) as a proxy for open-role
    volume on Indeed. Returns the number of distinct Indeed job postings found
    for this company name -- a rough independent headcount signal."""
    if not company_name:
        return 0
    try:
        results = search(f'site:indeed.com "{company_name}" jobs', limit=20)
    except Exception:
        return 0
    return sum(1 for r in results if "indeed.com" in (r.get("url") or ""))


def enrich_candidates(candidates, sleep_between=3.0):
    enriched = []
    for c in candidates:
        url = c.get("sample_url")
        name = c.get("name") or c.get("title")
        print(f"Enriching {c['domain']}...")
        record = dict(c)
        try:
            result = extract(url, EXTRACT_SCHEMA, EXTRACT_PROMPT)
            record["signals"] = result.get("data", {})
            record["extract_failed"] = False
        except Exception as e:
            print(f"  extract failed: {e}")
            record["signals"] = {}
            record["extract_failed"] = True

        # carry over Maps-sourced signals (present when discovered via apify_discover.py)
        record["signals"]["review_count"] = c.get("review_count")
        record["signals"]["rating"] = c.get("rating")

        # independent job-posting-volume signal (Indeed via web search, not LinkedIn/Apollo)
        job_count = count_indeed_job_postings(name)
        record["signals"]["indeed_job_postings"] = job_count

        enriched.append(record)
        time.sleep(sleep_between)
    return enriched


def main():
    retry_failed = "--retry-failed" in sys.argv

    in_path = os.path.join(DATA_DIR, "candidates.json")
    with open(in_path, encoding="utf-8") as f:
        candidates = json.load(f)

    out_path = os.path.join(DATA_DIR, "enriched.json")
    existing = []
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)

    if retry_failed:
        # keep only the ones that succeeded; failed ones get re-attempted.
        # legacy records (from before extract_failed was tracked) are treated
        # as failed if none of the extraction schema's fields have a value.
        def looks_failed(r):
            if "extract_failed" in r:
                return r["extract_failed"]
            s = r.get("signals", {})
            core_fields = ("years_in_business", "employee_count", "fleet_size",
                           "location_count", "client_portfolio_size", "sqft_or_acreage_managed",
                           "service_areas", "client_types", "certifications", "has_multiple_locations")
            return not any(s.get(f) for f in core_fields)

        kept = [r for r in existing if not looks_failed(r)]
        previously_failed = len(existing) - len(kept)
        existing = kept
        print(f"--retry-failed: dropping {previously_failed} previously-failed/empty records to re-process them.")

    already_done = {r["domain"] for r in existing}
    to_enrich = [c for c in candidates if c["domain"] not in already_done]
    print(f"{len(already_done)} already enriched (succeeded), {len(to_enrich)} to process.")

    newly_enriched = enrich_candidates(to_enrich)
    all_enriched = existing + newly_enriched

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_enriched, f, indent=2)

    still_failed = sum(1 for r in all_enriched if r.get("extract_failed"))
    print(f"Saved {len(all_enriched)} total enriched records to {out_path}")
    print(f"  {still_failed} still have a failed extract (run with --retry-failed to retry just these)")


if __name__ == "__main__":
    main()
