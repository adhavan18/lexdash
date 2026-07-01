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
   per region). Drops any result whose Google Maps category doesn't contain
   a landscaping-related keyword (landscap/lawn/grounds/tree service/
   arborist/irrigation/turf/hardscape/garden/nursery) -- filters out the
   roofing/pool/electrician-type noise that fuzzy Maps search term matching
   pulls in. Run once per region; each run **appends** new candidates to
   `data/candidates.json` (deduped by domain), so running it across many
   regions builds up a large combined candidate list over time. Requires
   `APIFY_API_TOKEN` in `.env`.
3. `enrich.py` — for each candidate's website, runs Firecrawl `/extract`
   with a schema pulling years in business, employee count, fleet size,
   branch/location count, client portfolio size, sq ft/acreage managed,
   service areas, client types, certifications, multi-location flag. Also
   does an independent Indeed job-posting-volume search per company (via
   Firecrawl web search, not LinkedIn/Apollo) as a second headcount proxy.
   **Appends**: skips domains already enriched in `data/enriched.json` so
   re-runs only cost API calls for genuinely new candidates.
4. `usaspending_enrich.py` (optional, additive) — looks up each candidate on
   USASpending.gov's free public API for federal contract dollars under the
   Landscaping Services NAICS code (561730). No API key needed. Writes
   `data/govt_contracts.json`; safe to re-run anytime.
5. `score.py` — combines every available signal into a revenue estimate,
   prioritizing the most reliable one available per company: confirmed
   federal contract dollars > employee count stated on-site > employee
   count estimated from job postings > from fleet size > from branch count
   > a soft fallback score when no employee signal exists at all. Also
   excludes any company whose website explicitly states residential
   clients only with no commercial/municipal/industrial mention (confirmed
   trade-press companies are never excluded this way, even if their site
   text wasn't scraped) -- those go to `data/excluded_non_commercial.csv`
   instead, so you can review what got filtered out. Writes
   `data/scored.csv` (recomputed fresh from `enriched.json` +
   `govt_contracts.json` each run).
6. `build_excel.py` — converts `data/scored.csv` into a styled Excel
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
python usaspending_enrich.py              # optional, free, adds verified federal contract $
python score.py
python build_excel.py
```

Roughly 5-8 mid-size metro regions at ~60-100 unique candidates each should
clear 500 total rows in the "Pipeline Candidates" tab.

## Calibrating the constants

`score.py`'s `REVENUE_PER_EMPLOYEE` ($120K), `EMPLOYEES_PER_TRUCK` (2.5),
`EMPLOYEES_PER_JOB_POSTING` (15), and `EMPLOYEES_PER_BRANCH` (15) are
industry rules-of-thumb, not fitted values. Once
`data/calibration_labeled.csv` has enough rows (company, revenue, and ideally
headcount if you can find it), refit these against real (revenue, headcount)
pairs from the Top 100/LM150 companies rather than relying on the defaults.

## Deliberately not using LinkedIn or Apollo

Every signal in this pipeline comes from company websites, Google Maps,
Indeed search results, and USASpending.gov — not LinkedIn or Apollo, which
don't carry reliable revenue data for private companies anyway.
