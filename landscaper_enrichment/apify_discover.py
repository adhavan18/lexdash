"""
Stage 1 (volume alternative to discover.py): pull Google Maps listings per
region using Apify's Google Maps Scraper actor. Better suited than Firecrawl
/search for high-volume Maps discovery (target: hundreds per region).

Requires APIFY_API_TOKEN in .env. Get one at https://console.apify.com/account/integrations

Run this once per region, e.g.:
    python apify_discover.py "Dallas, TX"
    python apify_discover.py "Charlotte, NC"
    python apify_discover.py "Phoenix, AZ"
Each run APPENDS new candidates to data/candidates.json (deduped by domain)
so you can build up to hundreds/thousands of candidates across many regions
without losing earlier runs.
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
CANDIDATES_PATH = os.path.join(DATA_DIR, "candidates.json")

SEARCH_TERMS = [
    "commercial landscaping company",
    "commercial landscape maintenance",
    "landscape contractor",
]


def start_run(region: str, max_results: int):
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_API_TOKEN not set (check .env)")
    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
    payload = {
        "searchStringsArray": SEARCH_TERMS,
        "locationQuery": region,
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "skipClosedPlaces": True,
    }
    resp = requests.post(url, params={"token": APIFY_TOKEN}, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def wait_for_run(run_id: str, poll_seconds: int = 10, timeout_seconds: int = 1200):
    url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    waited = 0
    while waited < timeout_seconds:
        resp = requests.get(url, params={"token": APIFY_TOKEN}, timeout=30)
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]
        if status in ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"):
            return data
        print(f"  run status: {status} (waited {waited}s)...")
        time.sleep(poll_seconds)
        waited += poll_seconds
    raise TimeoutError(f"Apify run {run_id} did not finish within {timeout_seconds}s")


def fetch_dataset_items(dataset_id: str):
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    resp = requests.get(url, params={"token": APIFY_TOKEN, "clean": "true"}, timeout=120)
    resp.raise_for_status()
    return resp.json()


def run_actor(region: str, max_results: int, retries: int = 3):
    """Starts the actor run asynchronously, polls until done, then pulls the dataset.
    Avoids the sync run-sync-get-dataset-items endpoint, which 502s on longer runs."""
    last_err = None
    for attempt in range(retries):
        try:
            print(f"Starting Apify run for '{region}' (target {max_results} listings/search term)...")
            run_id = start_run(region, max_results)
            run_data = wait_for_run(run_id)
            if run_data["status"] != "SUCCEEDED":
                raise RuntimeError(f"Apify run ended with status {run_data['status']}")
            return fetch_dataset_items(run_data["defaultDatasetId"])
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError, RuntimeError) as e:
            last_err = e
            wait = 10 * (attempt + 1)
            print(f"  attempt {attempt + 1} failed ({e}); retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


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


def discover_region(region: str, max_results: int = 100):
    places = run_actor(region, max_results)
    candidates = {}
    for p in places:
        rec = normalize(p, region)
        if not rec["domain"]:
            continue
        candidates.setdefault(rec["domain"], rec)
    return list(candidates.values())


def load_existing():
    if os.path.exists(CANDIDATES_PATH):
        with open(CANDIDATES_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def main(regions, max_results=100):
    existing = load_existing()
    merged = {c["domain"]: c for c in existing if c.get("domain")}
    print(f"Starting with {len(merged)} existing candidates from prior runs.")

    for region in regions:
        found = discover_region(region, max_results)
        new_count = sum(1 for f in found if f["domain"] not in merged)
        print(f"  {len(found)} listings with websites in {region} ({new_count} new)")
        for f in found:
            merged.setdefault(f["domain"], f)

    all_candidates = list(merged.values())
    with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, indent=2)
    print(f"Saved {len(all_candidates)} total unique candidates to {CANDIDATES_PATH}")


if __name__ == "__main__":
    import sys
    regions = sys.argv[1:] or ["Dallas, TX"]
    main(regions)
