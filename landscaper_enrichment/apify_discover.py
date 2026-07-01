"""
Stage 1 (volume alternative to discover.py): pull ~200 Google Maps listings
per region using Apify's Google Maps Scraper actor. Better suited than
Firecrawl /search for high-volume Maps discovery.

Requires APIFY_API_TOKEN in .env. Get one at https://console.apify.com/account/integrations
"""
import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
ACTOR_ID = "compass~crawler-google-places"  # Apify's "Google Maps Scraper" actor
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SEARCH_TERMS = [
    "commercial landscaping company",
    "commercial landscape maintenance",
    "landscape contractor",
]


def run_actor_sync(region: str, max_results: int = 200):
    """Runs the actor and waits for results (Apify's run-sync-get-dataset-items endpoint)."""
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN not set (check .env)")

    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    payload = {
        "searchStringsArray": SEARCH_TERMS,
        "locationQuery": region,
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "skipClosedPlaces": True,
    }
    resp = requests.post(
        url,
        params={"token": APIFY_TOKEN},
        json=payload,
        timeout=600,  # actor runs can take minutes for large maxCrawledPlaces
    )
    resp.raise_for_status()
    return resp.json()


def normalize(place: dict, region: str) -> dict:
    return {
        "domain": (place.get("website") or "").replace("https://", "").replace("http://", "").split("/")[0],
        "name": place.get("title"),
        "sample_url": place.get("website") or place.get("url"),
        "phone": place.get("phone"),
        "address": place.get("address"),
        "rating": place.get("totalScore"),
        "review_count": place.get("reviewsCount"),
        "category": place.get("categoryName"),
        "region": region,
        "found_via": "apify_google_maps",
    }


def discover_region(region: str, max_results: int = 200):
    print(f"Running Apify Google Maps Scraper for '{region}' (target {max_results} listings)...")
    places = run_actor_sync(region, max_results)
    candidates = {}
    for p in places:
        rec = normalize(p, region)
        if not rec["domain"]:
            continue
        candidates.setdefault(rec["domain"], rec)
    return list(candidates.values())


def main(regions, max_results=200):
    all_candidates = []
    for region in regions:
        found = discover_region(region, max_results)
        print(f"  {len(found)} unique candidates with websites in {region}")
        all_candidates.extend(found)
        time.sleep(1)

    out_path = os.path.join(DATA_DIR, "candidates.json")
    with open(out_path, "w") as f:
        json.dump(all_candidates, f, indent=2)
    print(f"Saved {len(all_candidates)} total candidates to {out_path}")


if __name__ == "__main__":
    import sys
    regions = sys.argv[1:] or ["Dallas, TX"]
    main(regions)
