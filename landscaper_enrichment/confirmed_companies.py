"""
Shared list of companies confirmed via trade-press rankings (Lawn &
Landscape Top 100, Landscape Management LM150), found via manual web search
since the source sites block automated scraping. Used by both score.py (to
auto-upgrade pipeline candidates that turn out to be one of these companies)
and build_excel.py (for the "Confirmed (Trade Press)" tab).

Each row: (company, hq_city, state, revenue_usd_or_None, confidence, notes, domain_or_None)
domain is used to match against pipeline candidates discovered independently
via Google Maps/web search -- if a pipeline candidate's domain matches one
here, its confidence/revenue gets upgraded to this verified data instead of
whatever weaker estimate the pipeline computed.
"""

CONFIRMED_ROWS = [
    ("BrightView Holdings", "Blue Bell", "PA", 2_770_000_000, "Confirmed", "#1 LM150, 11 consecutive years at top", "brightview.com"),
    ("The Davey Tree Expert Company", "Kent", "OH", 1_690_000_000, "Confirmed", "#2 LM150", "davey.com"),
    ("TruGreen", "Memphis", "TN", 1_500_000_000, "Confirmed (approx.)", "#3 LM150", "trugreen.com"),
    ("Yellowstone Landscape", "Bunnell", "FL", 773_800_000, "Confirmed", "Largest PE-backed pure-play commercial landscaper", "yellowstonelandscape.com"),
    ("SavATree", "Bedford Hills", "NY", 479_000_000, "Confirmed", "2024 revenue", "savatree.com"),
    ("Landscape Workshop", "Birmingham", "AL", 209_000_000, "Confirmed", "#23 on Top 100", "landscapeworkshop.com"),
    ("Ryan Lawn & Tree", "Merriam", "KS", 86_000_000, "Confirmed", "#47 on Top 100", "ryanlawn.com"),
    ("Massey Services", "Orlando", "FL", 71_600_000, "Confirmed", "2,060 employees", "masseyservices.com"),
    ("Level Green Landscaping", "Hyattsville", "MD", 44_000_000, "Confirmed", "#88 on Top 100", "levelgreenlandscaping.com"),
    ("Greenscape", "Raynham", "MA", 37_000_000, "Confirmed", "325 employees", "greenscapeinc.com"),
    ("Southern Botanical", "Dallas", "TX", None, "Confirmed rank, revenue not sourced", "#46 on 2026 Top 100", "southernbotanical.com"),
    ("Bland Landscaping", "Apex", "NC", None, "Confirmed PE-backed, exact revenue not public", "Recapitalized as PE-backed platform", "blandlandscaping.com"),
    ("Ruppert Landscape", "Laytonsville", "MD", None, "Known large national player, exact revenue not sourced", "Multi-state commercial firm", "ruppertlandscape.com"),
    ("U.S. Lawns", "Orlando", "FL", None, "Franchise network, revenue varies by franchisee", "National commercial franchise brand", "uslawns.com"),
]

# domain -> row, for O(1) lookup when cross-matching pipeline candidates
BY_DOMAIN = {row[6]: row for row in CONFIRMED_ROWS if row[6]}
