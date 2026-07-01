"""
Stage 3: estimate revenue primarily from employee count, since commercial
landscaping is labor-intensive with a fairly consistent revenue-per-employee
ratio industry-wide. Falls back to a multi-factor heuristic score only when
no employee signal is available at all.

REVENUE_PER_EMPLOYEE is an industry rule-of-thumb ($100K-150K/FTE is the
commonly cited range for commercial landscaping/grounds maintenance) --
adjust it if you have better benchmark data (e.g. from calibrate.py's
ground-truth set once you have both revenue and headcount for the same
companies).
"""
import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

REVENUE_PER_EMPLOYEE = 120_000  # industry rule-of-thumb, adjust as calibrated
REVENUE_THRESHOLD = 5_000_000
MIN_EMPLOYEES_FOR_THRESHOLD = REVENUE_THRESHOLD / REVENUE_PER_EMPLOYEE  # ~42

# used only as a fallback when no direct/fleet-based employee estimate exists
FALLBACK_WEIGHTS = {
    "years_in_business": 0.20,
    "service_area_count": 0.20,
    "commercial_client_flag": 0.20,
    "multi_location_flag": 0.20,
    "review_count": 0.15,
    "rating": 0.05,
}

EMPLOYEES_PER_TRUCK = 2.5  # rough crew-size proxy when fleet_size is stated but headcount isn't


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
    s += FALLBACK_WEIGHTS["review_count"] * normalize(signals.get("review_count"), 150)
    s += FALLBACK_WEIGHTS["rating"] * normalize(signals.get("rating"), 5)
    return round(s, 3)


def estimate_employees(signals: dict):
    """Returns (estimated_employees, source) where source explains how we got the number."""
    employee_count = signals.get("employee_count")
    if employee_count:
        return employee_count, "stated_on_website"

    fleet_size = signals.get("fleet_size")
    if fleet_size:
        return round(fleet_size * EMPLOYEES_PER_TRUCK, 1), "estimated_from_fleet_size"

    return None, "unknown"


def score_record(signals: dict) -> dict:
    employees, employee_source = estimate_employees(signals)

    if employees is not None:
        estimated_revenue = round(employees * REVENUE_PER_EMPLOYEE)
        likely_over_5m = estimated_revenue >= REVENUE_THRESHOLD
        confidence = "employee_based"
    else:
        estimated_revenue = None
        likely_over_5m = False
        confidence = "fallback_heuristic_only"

    return {
        "estimated_employees": employees,
        "employee_source": employee_source,
        "estimated_revenue_usd": estimated_revenue,
        "likely_over_5m": likely_over_5m,
        "confidence": confidence,
        "fallback_score": fallback_score(signals),  # secondary ranking signal, always computed
    }


def main():
    in_path = os.path.join(DATA_DIR, "enriched.json")
    with open(in_path, encoding="utf-8") as f:
        enriched = json.load(f)

    rows = []
    for r in enriched:
        signals = r.get("signals", {})
        est = score_record(signals)
        rows.append({
            "domain": r["domain"],
            "region": r.get("region"),
            "title": r.get("title") or r.get("name"),
            **est,
            "years_in_business": signals.get("years_in_business"),
            "fleet_size": signals.get("fleet_size"),
            "review_count": signals.get("review_count"),
            "rating": signals.get("rating"),
            "service_areas": ";".join(signals.get("service_areas") or []),
            "client_types": ";".join(signals.get("client_types") or []),
            "has_multiple_locations": signals.get("has_multiple_locations"),
            "sample_url": r.get("sample_url"),
        })

    # employee-based estimates first (most trustworthy), then by fallback score
    rows.sort(key=lambda x: (x["estimated_revenue_usd"] is None, -(x["estimated_revenue_usd"] or 0), -x["fallback_score"]))

    out_path = os.path.join(DATA_DIR, "scored.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    with_employees = [r for r in rows if r["estimated_employees"] is not None]
    flagged = [r for r in rows if r["likely_over_5m"]]
    print(f"Scored {len(rows)} companies")
    print(f"  {len(with_employees)} have an employee estimate (stated or fleet-derived)")
    print(f"  {len(flagged)} flagged as likely >$5M (>= ~{int(MIN_EMPLOYEES_FOR_THRESHOLD)} employees "
          f"at ${REVENUE_PER_EMPLOYEE:,}/employee)")
    print(f"Full results: {out_path}")


if __name__ == "__main__":
    main()
