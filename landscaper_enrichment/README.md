# Commercial Landscaper Revenue Enrichment Pipeline

Identifies US commercial landscaping companies likely doing >$5M/year in
revenue, using public sources other than LinkedIn/Apollo (which don't carry
reliable private-company revenue data).

## Why not just Google Business listings

Google Business Profiles are a good *discovery* layer (review volume, years
active, category) but carry no revenue field. This pipeline treats Maps/
search results as one discovery source among several, then enriches each
candidate with size proxies scraped from the company's own site and public
records, and scores them against a calibration set of companies with known
(self-reported) revenue.

## Sources used (beyond LinkedIn/Apollo)

- Web search results surfacing BBB profiles, local business journal "largest
  companies" lists, and trade press rankings (Lawn & Landscape Top 100,
  Landscape Management LM150) which self-report revenue.
- Company websites (fleet size, employee count, years in business, service
  area breadth, client types, certifications, multi-location signals).
- Recommended next additions (not yet wired up, need per-state scraping):
  state contractor license boards (bond tier), SAM.gov/USASpending contract
  awards, UCC-1 equipment financing filings.

## Pipeline stages

1. `calibrate.py` — pulls trade-press "Top 100" ranking pages that include
   real revenue figures, to use as ground truth. **Manual step**: parse the
   saved markdown tables into `data/calibration_labeled.csv` (columns:
   company,revenue_usd,city,state) — these numbers are needed to validate/
   refit the scoring weights in `score.py`.
2. `discover.py "City, State" "City, State"` — searches for candidate
   companies per region via Firecrawl `/search`, excluding LinkedIn/Apollo/
   job boards. Low volume (~10-20 per region); good for a quick pass.
   **OR** `apify_discover.py "City, State"` — pulls Google Maps listings per
   region via Apify's Google Maps Scraper actor (much higher volume, ~50-150
   per region). Run once per region; each run **appends** new candidates to
   `data/candidates.json` (deduped by domain), so running it across many
   regions builds up a large combined candidate list over time. Requires
   `APIFY_API_TOKEN` in `.env`.
3. `enrich.py` — for each candidate's website, runs Firecrawl `/extract`
   with a schema pulling years in business, employee count, fleet size,
   service areas, client types, certifications, multi-location flag. Also
   **appends**: skips domains already enriched in `data/enriched.json` so
   re-runs only cost API calls for genuinely new candidates.
4. `score.py` — combines signals into a weighted 0-1 score and flags
   `likely_over_5m` above a threshold. Writes `data/scored.csv` (recomputed
   fresh from the full `enriched.json` each run, so it always reflects every
   region enriched so far).
5. `build_excel.py` — converts `data/scored.csv` into a styled Excel
   workbook (`data/commercial_landscapers_by_state.xlsx`) with the pipeline
   candidates grouped by region/state, plus a separate tab of companies with
   confirmed trade-press revenue.

## Usage

```bash
pip install -r requirements.txt
# FIRECRAWL_API_KEY and APIFY_API_TOKEN should already be in .env

python calibrate.py                       # ground truth (manual labeling step after)

# Repeat this block once per region to build up volume:
python apify_discover.py "Dallas, TX"
python apify_discover.py "Charlotte, NC"
python apify_discover.py "Phoenix, AZ"
# ...add more regions as needed...

python enrich.py
python score.py
python build_excel.py
```

Roughly 5-8 mid-size metro regions at ~60-100 unique candidates each should
clear 500 total rows in the "Pipeline Candidates" tab.

## Calibrating the weights

`score.py`'s `WEIGHTS` dict is a starting heuristic. Once
`data/calibration_labeled.csv` has enough rows, fit real weights: enrich the
labeled companies the same way (run them through `enrich.py`), then run a
logistic/linear regression of `signals -> revenue_usd` to replace the
hand-picked weights with fitted coefficients and pick a data-driven
threshold for the $5M cutoff.

## Note on Apify

The original ask mentioned Apify as an alternative to Firecrawl (e.g. its
Google Maps Scraper actor for stage 1 discovery, which returns richer Maps
fields like review_count/rating directly). This pipeline currently only
wires up Firecrawl; swapping `discover.py`'s search step for an Apify Google
Maps Scraper run is a straightforward follow-up if an Apify API token is
provided.
