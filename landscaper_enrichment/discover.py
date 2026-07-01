"""
Stage 1: discover candidate commercial landscaping companies in a region.

Uses Firecrawl /search across several source types (Google-indexed business
listings, BBB, state contractor license boards, trade directories) instead of
LinkedIn/Apollo. Region is any "City, State" string.
"""
import json
import os
from urllib.parse import urlparse

from firecrawl_client import search

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

QUERY_TEMPLATES = [
    '"commercial landscaping" company {region}',
    '"commercial landscape maintenance" {region} -jobs -indeed.com',
    'site:bbb.org landscaping {region}',
    '"largest landscaping companies" {region} OR "top landscaping companies" {region}',
]


def domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


# directories, social platforms, media outlets, and PE/investment firms that
# show up in search results but are not landscaping companies themselves
EXCLUDED_DOMAINS = {
    "linkedin.com", "apollo.io", "indeed.com", "ziprecruiter.com",
    "yelp.com", "facebook.com", "instagram.com", "tiktok.com", "twitter.com",
    "x.com", "youtube.com", "giftly.com", "bbb.org", "downtobid.com",
    "lawnandlandscape.com", "landscapemanagement.net", "statista.com",
    "wikipedia.org", "glassdoor.com", "zippia.com", "owler.com",
    "manta.com", "yellowpages.com", "angi.com", "thumbtack.com",
    "houzz.com", "buildzoom.com", "mapquest.com", "google.com",
    "reddit.com",
}

EXCLUDED_KEYWORDS = ("capital", "partners", "equity", "ventures", "investors")


def is_excluded(d: str) -> bool:
    if d in EXCLUDED_DOMAINS:
        return True
    return any(k in d for k in EXCLUDED_KEYWORDS)


def discover_region(region: str, limit_per_query: int = 10):
    candidates = {}
    for template in QUERY_TEMPLATES:
        query = template.format(region=region)
        try:
            results = search(query, limit=limit_per_query)
        except Exception as e:
            print(f"search failed for '{query}': {e}")
            continue
        for r in results:
            url = r.get("url")
            if not url:
                continue
            d = domain(url)
            if is_excluded(d):
                continue
            candidates.setdefault(d, {
                "domain": d,
                "sample_url": url,
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "region": region,
                "found_via": [],
            })
            candidates[d]["found_via"].append(template)
    return list(candidates.values())


def main(regions):
    all_candidates = []
    for region in regions:
        print(f"Discovering candidates in {region}...")
        found = discover_region(region)
        print(f"  {len(found)} candidate companies")
        all_candidates.extend(found)

    out_path = os.path.join(DATA_DIR, "candidates.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, indent=2)
    print(f"Saved {len(all_candidates)} total candidates to {out_path}")


if __name__ == "__main__":
    import sys
    regions = sys.argv[1:] or ["Dallas, TX", "Charlotte, NC"]
    main(regions)
