#!/usr/bin/env python3
"""
Menuverso Database Validation Script
Runs comprehensive checks on restaurants.json and outputs an audit report.
"""

import json
import re
import sys
from collections import Counter
from urllib.parse import urlparse

INPUT = "restaurants.json"

VALID_CUISINES = {
    "Mediterranean", "Spanish", "Catalan", "Italian", "Asian",
    "Japanese", "Indian", "Mexican", "Middle Eastern", "Fusion",
    "Vegetarian/Vegan", "Seafood", "Basque", "French", "Greek",
    "Lebanese", "Argentine", "Peruvian", "Chinese", "Korean",
    "Thai", "Colombian", "Cuban", "Ethiopian", "Turkish",
    "Gastropub", "Café", "Market", "Other"
}

VALID_TIERS = {"budget", "mid-range", "premium"}
VALID_MENU_TIERS = {"confirmed", "likely", "none"}
VALID_STATUSES = {"active", "permanently_closed", "temporarily_closed"}

# Barcelona bounding box
BCN_LAT = (41.32, 41.47)
BCN_LNG = (2.05, 2.23)

REQUIRED_FIELDS = ["id", "name", "neighborhood", "cuisine_type", "pricing_tier", "menu_tier", "postal_code"]


def parse_price(price_str):
    if not price_str:
        return None, None
    nums = re.findall(r'[\d.]+', price_str)
    if not nums:
        return None, None
    nums = [float(n) for n in nums]
    return min(nums), max(nums)


def validate(data):
    issues = {"critical": [], "warning": [], "info": []}

    ids = [r["id"] for r in data]

    # 1. ID integrity
    if len(ids) != len(set(ids)):
        dupes = [i for i, c in Counter(ids).items() if c > 1]
        issues["critical"].append(f"Duplicate IDs: {dupes}")

    expected = set(range(1, max(ids) + 1))
    missing = sorted(expected - set(ids))
    if missing:
        issues["info"].append(f"ID gaps ({len(missing)}): {missing[:20]}")

    # 2. Required fields
    for r in data:
        for field in REQUIRED_FIELDS:
            if not r.get(field):
                issues["critical"].append(f"#{r.get('id','?')} {r.get('name','?')}: missing required '{field}'")

    # 3. Cuisine validation
    bad_cuisines = set()
    for r in data:
        c = r.get("cuisine_type", "")
        if c not in VALID_CUISINES:
            bad_cuisines.add(c)
    if bad_cuisines:
        issues["warning"].append(f"Non-canonical cuisine types: {bad_cuisines}")

    # 4. Pricing tier validation
    for r in data:
        if r.get("pricing_tier") not in VALID_TIERS:
            issues["warning"].append(f"#{r['id']} {r['name']}: invalid pricing_tier '{r.get('pricing_tier')}'")

    # 5. Menu tier validation
    for r in data:
        if r.get("menu_tier") not in VALID_MENU_TIERS:
            issues["warning"].append(f"#{r['id']} {r['name']}: invalid menu_tier '{r.get('menu_tier')}'")

    # 6. Pricing consistency
    for r in data:
        lo, hi = parse_price(r.get("menu_price_range", ""))
        tier = r.get("pricing_tier", "")
        if lo is not None:
            if tier == "budget" and hi > 16:
                issues["warning"].append(f"#{r['id']} {r['name']}: budget tier but {r['menu_price_range']}")
            if tier == "premium" and hi < 18:
                issues["warning"].append(f"#{r['id']} {r['name']}: premium tier but {r['menu_price_range']}")

    # 7. URL format
    for r in data:
        url = r.get("website", "")
        if url and not url.startswith("http"):
            issues["warning"].append(f"#{r['id']} {r['name']}: website doesn't start with http: {url}")

    # 8. Coordinates
    has_coords = sum(1 for r in data if r.get("coordinates") and r["coordinates"].get("lat"))
    if has_coords == 0:
        issues["info"].append("No restaurants have coordinates (0%)")
    elif has_coords < len(data):
        issues["info"].append(f"Coordinates: {has_coords}/{len(data)} ({has_coords/len(data)*100:.1f}%)")
        # Validate those with coords are in BCN
        for r in data:
            c = r.get("coordinates", {})
            if c.get("lat") and c.get("lng"):
                if not (BCN_LAT[0] <= c["lat"] <= BCN_LAT[1] and BCN_LNG[0] <= c["lng"] <= BCN_LNG[1]):
                    issues["warning"].append(f"#{r['id']} {r['name']}: coordinates outside Barcelona ({c['lat']}, {c['lng']})")

    # 9. Closed restaurants
    closed = [r for r in data if r.get("status") == "permanently_closed"]
    if closed:
        issues["info"].append(f"Permanently closed: {', '.join(r['name'] for r in closed)}")
        for r in closed:
            if r.get("menu_tier") != "none":
                issues["warning"].append(f"#{r['id']} {r['name']}: closed but menu_tier is '{r['menu_tier']}'")

    # 10. Duplicate names
    names = Counter(r["name"] for r in data)
    dupes = [(n, c) for n, c in names.items() if c > 1]
    if dupes:
        issues["info"].append(f"Duplicate restaurant names: {len(dupes)}")
        for n, c in dupes[:5]:
            issues["info"].append(f"  '{n}' appears {c} times")

    # 11. Missing fields summary
    field_stats = {}
    check_fields = ["address_full", "website", "phone", "google_maps_url", "instagram", "notes"]
    for f in check_fields:
        has = sum(1 for r in data if r.get(f))
        field_stats[f] = f"{has}/{len(data)} ({has/len(data)*100:.0f}%)"

    # 12. Status field
    no_status = sum(1 for r in data if not r.get("status"))
    if no_status:
        issues["warning"].append(f"{no_status} restaurants missing 'status' field")

    return issues, field_stats


def main():
    with open(INPUT) as f:
        data = json.load(f)

    print(f"🔍 Validating {len(data)} restaurants...\n")

    issues, field_stats = validate(data)

    # Print results
    has_critical = bool(issues["critical"])

    if issues["critical"]:
        print(f"🔴 CRITICAL ISSUES ({len(issues['critical'])}):")
        for i in issues["critical"][:20]:
            print(f"   {i}")

    if issues["warning"]:
        print(f"\n🟡 WARNINGS ({len(issues['warning'])}):")
        for i in issues["warning"][:20]:
            print(f"   {i}")
        if len(issues["warning"]) > 20:
            print(f"   ... and {len(issues['warning'])-20} more")

    if issues["info"]:
        print(f"\n🔵 INFO ({len(issues['info'])}):")
        for i in issues["info"]:
            print(f"   {i}")

    print(f"\n📊 Field Completeness:")
    for f, s in field_stats.items():
        print(f"   {f}: {s}")

    # Summary counts
    tiers = Counter(r.get("menu_tier") for r in data)
    ptiers = Counter(r.get("pricing_tier") for r in data)
    cuisines = Counter(r.get("cuisine_type") for r in data)

    print(f"\n📈 Distribution:")
    print(f"   Menu tiers: confirmed={tiers.get('confirmed',0)}, likely={tiers.get('likely',0)}, none={tiers.get('none',0)}")
    print(f"   Pricing: budget={ptiers.get('budget',0)}, mid-range={ptiers.get('mid-range',0)}, premium={ptiers.get('premium',0)}")
    print(f"   Cuisine types: {len(cuisines)}")

    if has_critical:
        print("\n❌ VALIDATION FAILED — Critical issues found")
        sys.exit(1)
    else:
        print("\n✅ VALIDATION PASSED — No critical issues")
        sys.exit(0)


if __name__ == "__main__":
    main()
