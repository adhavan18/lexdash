"""
Stage 3: estimate revenue by combining every available proxy, prioritizing
the most direct/reliable signal available for each company:

  1. Confirmed federal contract dollars (USASpending.gov, real $ -- if this
     alone clears $5M, that's verified, not estimated)
  2. Employee count stated directly on the company website
  3. Employee count estimated from Indeed job-posting volume
  4. Employee count estimated from fleet/truck count
  5. Employee count estimated from branch/location count
  6. No employee signal at all -- fall back to a soft multi-factor score
     (years in business, client portfolio size, sqft/acreage managed,
     service area count, client types, review count/rating) for ranking
     only, not a revenue estimate.

REVENUE_PER_EMPLOYEE and the other per-signal multipliers are industry
rules-of-thumb -- refit them once calibrate.py's ground-truth set has
enough labeled (revenue, headcount) pairs.
"""
import csv
import json
import os

import confirmed_companies

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

REVENUE_PER_EMPLOYEE = 120_000
REVENUE_THRESHOLD = 5_000_000
MIN_EMPLOYEES_FOR_THRESHOLD = REVENUE_THRESHOLD / REVENUE_PER_EMPLOYEE  # ~42

EMPLOYEES_PER_TRUCK = 2.5
EMPLOYEES_PER_JOB_POSTING = 15  # a company only has a fraction of its workforce open at once
EMPLOYEES_PER_BRANCH = 15

FALLBACK_WEIGHTS = {
    "years_in_business": 0.15,
    "service_area_count": 0.15,
    "commercial_client_flag": 0.15,
    "multi_location_flag": 0.10,
    "client_portfolio_size": 0.15,
    "sqft_or_acreage_managed": 0.10,
    "review_count": 0.15,
    "rating": 0.05,
}


def normalize(value, cap):
    if not value:
        return 0.0
    return min(value / cap, 1.0)


def fallback_score(signals: dict) -> float:
    s = 0.0
    s += FALLBACK_WEIGHTS["years_in_business"] * normalize(signals.get("years_in_business"), 25)
    s += FALLBACK_WEIGHTS["service_area_count"] * normalize(len(signals.get("service_areas") or []), 6)
    client_types = set(signals.get("client_types") or [])
    s += FALLBACK_WEIGHTS["commercial_client_flag"] * (1.0 if "commercial" in client_types or "municipal" in client_types else 0.0)
    s += FALLBACK_WEIGHTS["multi_location_flag"] * (1.0 if signals.get("has_multiple_locations") else 0.0)
    s += FALLBACK_WEIGHTS["client_portfolio_size"] * normalize(signals.get("client_portfolio_size"), 200)
    s += FALLBACK_WEIGHTS["sqft_or_acreage_managed"] * (1.0 if signals.get("sqft_or_acreage_managed") else 0.0)
    s += FALLBACK_WEIGHTS["review_count"] * normalize(signals.get("review_count"), 150)
    s += FALLBACK_WEIGHTS["rating"] * normalize(signals.get("rating"), 5)
    return round(s, 3)


def estimate_employees(signals: dict):
    """Returns (estimated_employees, source), trying each proxy in priority order."""
    if signals.get("employee_count"):
        return signals["employee_count"], "stated_on_website"

    job_postings = signals.get("indeed_job_postings")
    if job_postings:
        return round(job_postings * EMPLOYEES_PER_JOB_POSTING, 1), "estimated_from_job_postings"

    if signals.get("fleet_size"):
        return round(signals["fleet_size"] * EMPLOYEES_PER_TRUCK, 1), "estimated_from_fleet_size"

    if signals.get("location_count"):
        return round(signals["location_count"] * EMPLOYEES_PER_BRANCH, 1), "estimated_from_location_count"

    return None, "unknown"


def load_govt_contracts():
    path = os.path.join(DATA_DIR, "govt_contracts.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def score_record(domain: str, signals: dict, govt_contracts: dict) -> dict:
    # if this pipeline candidate is actually one of our known trade-press
    # companies, use its verified data instead of estimating from scratch
    confirmed = confirmed_companies.BY_DOMAIN.get(domain)
    if confirmed:
        company, city, state, revenue, trade_press_confidence, notes, _ = confirmed
        priority = "Low"
        reason = f"Matched trade-press company '{company}' -- {notes}"
        return {
            "estimated_employees": None,
            "employee_source": "matched_trade_press_company",
            "confirmed_federal_contracts_usd": govt_contracts.get(domain, {}).get("total_federal_landscaping_awards_usd", 0) or 0,
            "estimated_revenue_usd": revenue,
            "likely_over_5m": True if revenue else (trade_press_confidence.startswith("Confirmed")),
            "confidence": "confirmed_trade_press",
            "fallback_score": fallback_score(signals),
            "manual_verification_priority": priority,
            "manual_verification_reason": reason,
        }

    govt = govt_contracts.get(domain, {})
    confirmed_govt_usd = govt.get("total_federal_landscaping_awards_usd", 0) or 0

    employees, employee_source = estimate_employees(signals)

    if confirmed_govt_usd >= REVENUE_THRESHOLD:
        # federal contract dollars alone already clear the bar -- verified, not estimated
        estimated_revenue = confirmed_govt_usd
        likely_over_5m = True
        confidence = "confirmed_federal_contracts"
    elif employees is not None:
        estimated_revenue = round(employees * REVENUE_PER_EMPLOYEE)
        # federal contracts are a partial revenue floor -- take whichever estimate is higher
        estimated_revenue = max(estimated_revenue, confirmed_govt_usd)
        likely_over_5m = estimated_revenue >= REVENUE_THRESHOLD
        confidence = "employee_based"
    elif confirmed_govt_usd > 0:
        estimated_revenue = confirmed_govt_usd
        likely_over_5m = False
        confidence = "partial_federal_contracts_only"
    else:
        estimated_revenue = None
        likely_over_5m = False
        confidence = "fallback_heuristic_only"

    fb_score = fallback_score(signals)
    priority, reason = manual_verification_priority(confidence, employee_source, estimated_revenue, fb_score)

    return {
        "estimated_employees": employees,
        "employee_source": employee_source,
        "confirmed_federal_contracts_usd": confirmed_govt_usd,
        "estimated_revenue_usd": estimated_revenue,
        "likely_over_5m": likely_over_5m,
        "confidence": confidence,
        "fallback_score": fb_score,
        "manual_verification_priority": priority,
        "manual_verification_reason": reason,
    }


# how close an estimate has to be to the $5M line to be worth a second look
BORDERLINE_BAND = (0.6, 1.6)  # 0.6x-1.6x of REVENUE_THRESHOLD
STRONG_FALLBACK_SCORE = 0.4


def manual_verification_priority(confidence, employee_source, estimated_revenue, fb_score):
    """Flags which rows are worth spending manual/paid verification effort on,
    vs. ones the pipeline is already reasonably confident about either way."""
    if confidence == "confirmed_federal_contracts":
        return "Low", "Already verified via federal contract data"

    if confidence == "employee_based" and employee_source == "stated_on_website":
        if estimated_revenue and BORDERLINE_BAND[0] * REVENUE_THRESHOLD <= estimated_revenue <= BORDERLINE_BAND[1] * REVENUE_THRESHOLD:
            return "Medium", "Direct headcount data, but estimate sits close to the $5M line"
        return "Low", "Direct headcount stated on company site -- reasonably reliable estimate"

    if confidence == "employee_based":
        if estimated_revenue and BORDERLINE_BAND[0] * REVENUE_THRESHOLD <= estimated_revenue <= BORDERLINE_BAND[1] * REVENUE_THRESHOLD:
            return "High", f"Estimate from proxy ({employee_source}) sits close to the $5M line -- verify"
        return "Medium", f"Employee count is a proxy estimate ({employee_source}), not stated directly"

    if confidence == "partial_federal_contracts_only":
        return "Medium", "Has some confirmed federal $ but not enough alone; no employee signal to add"

    # fallback_heuristic_only: no employee or contract signal at all
    if fb_score >= STRONG_FALLBACK_SCORE:
        return "High", "No employee/contract data, but strong secondary signals (reviews, portfolio, tenure) -- worth manual check"
    return "Low", "Weak signals across the board -- deprioritize"


COMMERCIAL_CLIENT_TYPES = {"commercial", "municipal", "industrial"}


def is_residential_only(client_types: set) -> bool:
    """True only when the site clearly states residential clients and never
    mentions any commercial-ish client type -- i.e. we have positive evidence
    it's not a commercial landscaper, not just an absence of information."""
    return "residential" in client_types and not (client_types & COMMERCIAL_CLIENT_TYPES)


def main():
    in_path = os.path.join(DATA_DIR, "enriched.json")
    with open(in_path, encoding="utf-8") as f:
        enriched = json.load(f)

    govt_contracts = load_govt_contracts()

    rows = []
    excluded_rows = []
    for r in enriched:
        signals = r.get("signals", {})
        est = score_record(r["domain"], signals, govt_contracts)
        client_types_set = set(signals.get("client_types") or [])
        row = {
            "domain": r["domain"],
            "region": r.get("region"),
            "title": r.get("title") or r.get("name"),
            **est,
            "years_in_business": signals.get("years_in_business"),
            "fleet_size": signals.get("fleet_size"),
            "location_count": signals.get("location_count"),
            "client_portfolio_size": signals.get("client_portfolio_size"),
            "sqft_or_acreage_managed": signals.get("sqft_or_acreage_managed"),
            "indeed_job_postings": signals.get("indeed_job_postings"),
            "review_count": signals.get("review_count"),
            "rating": signals.get("rating"),
            "service_areas": ";".join(signals.get("service_areas") or []),
            "client_types": ";".join(client_types_set),
            "has_multiple_locations": signals.get("has_multiple_locations"),
            "sample_url": r.get("sample_url"),
        }
        # confirmed trade-press companies are commercial by definition even if
        # their site's client_types wasn't scraped -- never exclude those
        if est["confidence"] != "confirmed_trade_press" and is_residential_only(client_types_set):
            row["excluded_reason"] = "Website states residential clients only, no commercial/municipal/industrial mention"
            excluded_rows.append(row)
        else:
            rows.append(row)

    # verified trade-press/federal data first, then employee-based estimates, then fallback score
    confidence_rank = {
        "confirmed_trade_press": 0,
        "confirmed_federal_contracts": 0,
        "employee_based": 1,
        "partial_federal_contracts_only": 2,
        "fallback_heuristic_only": 3,
    }
    rows.sort(key=lambda x: (
        confidence_rank.get(x["confidence"], 9),
        -(x["estimated_revenue_usd"] or 0),
        -x["fallback_score"],
    ))

    out_path = os.path.join(DATA_DIR, "scored.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    if excluded_rows:
        excluded_path = os.path.join(DATA_DIR, "excluded_non_commercial.csv")
        with open(excluded_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = list(excluded_rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(excluded_rows)

    with_employees = [r for r in rows if r["estimated_employees"] is not None]
    flagged = [r for r in rows if r["likely_over_5m"]]
    confirmed = [r for r in rows if r["confidence"] == "confirmed_federal_contracts"]
    high_priority = [r for r in rows if r["manual_verification_priority"] == "High"]
    print(f"Scored {len(rows)} companies (commercial only)")
    print(f"  {len(excluded_rows)} excluded as residential-only (see data/excluded_non_commercial.csv)")
    print(f"  {len(with_employees)} have an employee estimate (stated, job-postings, fleet, or branch-derived)")
    print(f"  {len(confirmed)} have verified federal contract dollars alone clearing $5M")
    print(f"  {len(flagged)} total flagged as likely >$5M")
    print(f"  {len(high_priority)} flagged 'High' manual-verification priority -- worth the paid/manual follow-up")
    print(f"Full results: {out_path}")


if __name__ == "__main__":
    main()
