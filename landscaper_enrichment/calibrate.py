"""
Build a ground-truth calibration set from public 'Top 100 landscape companies'
rankings (Lawn & Landscape, Landscape Management) which self-report revenue.
These give us known (company, revenue) pairs to fit the scoring weights against.
"""
import csv
import json
import os

from firecrawl_client import search, scrape

OUT_PATH = os.path.join(os.path.dirname(__file__), "data", "calibration_raw.json")

SOURCE_QUERIES = [
    "Lawn & Landscape Top 100 landscape companies revenue list",
    "Landscape Management LM150 largest landscaping companies revenue",
]


def fetch_ranking_pages():
    pages = []
    for q in SOURCE_QUERIES:
        results = search(q, limit=5)
        for r in results:
            url = r.get("url")
            if not url:
                continue
            try:
                scraped = scrape(url, formats=["markdown"])
                pages.append({"query": q, "url": url, "markdown": scraped.get("markdown", "")})
            except Exception as e:
                print(f"skip {url}: {e}")
    return pages


def main():
    pages = fetch_ranking_pages()
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=2)
    print(f"Saved {len(pages)} ranking pages to {OUT_PATH}")
    print("Next: manually or via LLM-parse the markdown tables into "
          "data/calibration_labeled.csv with columns: company,revenue_usd,city,state")


if __name__ == "__main__":
    main()
