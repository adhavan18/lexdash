"""
Stage 3: score enriched candidates on likelihood of >$5M revenue.

Heuristic weights below are starting points -- calibrate.py collects a
ground-truth set (Top 100 lists with self-reported revenue) that should be
used to refit these weights via simple linear regression once enough labeled
rows exist (see fit_weights()).
"""
import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

WEIGHTS = {
    "years_in_business": 0.15,   # >15 yrs suggests an established, scaled shop
    "employee_count": 0.30,      # strongest direct proxy when stated
    "fleet_size": 0.20,
    "service_area_count": 0.15,  # more cities served = bigger op
    "commercial_client_flag": 0.10,
    "multi_location_flag": 0.10,
}

THRESHOLD = 0.5  # flag as likely >$5M above this normalized score


def normalize(value, cap):
    if not value:
        return 0.0
    return min(value / cap, 1.0)


def score_record(signals: dict) -> float:
    s = 0.0
    s += WEIGHTS["years_in_business"] * normalize(signals.get("years_in_business"), 25)
    s += WEIGHTS["employee_count"] * normalize(signals.get("employee_count"), 100)
    s += WEIGHTS["fleet_size"] * normalize(signals.get("fleet_size"), 40)
    s += WEIGHTS["service_area_count"] * normalize(len(signals.get("service_areas") or []), 6)
    client_types = set(signals.get("client_types") or [])
    s += WEIGHTS["commercial_client_flag"] * (1.0 if "commercial" in client_types or "municipal" in client_types else 0.0)
    s += WEIGHTS["multi_location_flag"] * (1.0 if signals.get("has_multiple_locations") else 0.0)
    return round(s, 3)


def main():
    in_path = os.path.join(DATA_DIR, "enriched.json")
    with open(in_path) as f:
        enriched = json.load(f)

    rows = []
    for r in enriched:
        signals = r.get("signals", {})
        sc = score_record(signals)
        rows.append({
            "domain": r["domain"],
            "region": r.get("region"),
            "title": r.get("title"),
            "score": sc,
            "likely_over_5m": sc >= THRESHOLD,
            "years_in_business": signals.get("years_in_business"),
            "employee_count": signals.get("employee_count"),
            "fleet_size": signals.get("fleet_size"),
            "service_areas": ";".join(signals.get("service_areas") or []),
            "client_types": ";".join(signals.get("client_types") or []),
            "has_multiple_locations": signals.get("has_multiple_locations"),
            "sample_url": r.get("sample_url"),
        })

    rows.sort(key=lambda x: x["score"], reverse=True)

    out_path = os.path.join(DATA_DIR, "scored.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    flagged = [r for r in rows if r["likely_over_5m"]]
    print(f"Scored {len(rows)} companies, {len(flagged)} flagged as likely >$5M")
    print(f"Full results: {out_path}")


if __name__ == "__main__":
    main()
