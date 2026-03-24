#!/usr/bin/env python3
"""
Data Validation Script — Checks restaurants.json integrity before deployment.
Run: python3 validate_data.py
"""

import json
import sys
from collections import Counter


def validate():
    with open("restaurants.json") as f:
        data = json.load(f)

    errors = []
    warnings = []
    total = len(data)

    # 1. Check for required fields
    required = ["id", "name", "neighborhood", "cuisine_type"]
    for r in data:
        for field in required:
            if not r.get(field):
                errors.append(f"#{r.get('id','?')}: Missing required field '{field}'")

    # 2. Check for duplicate IDs
    ids = [r["id"] for r in data]
    id_counts = Counter(ids)
    dupes = {k: v for k, v in id_counts.items() if v > 1}
    if dupes:
        errors.append(f"Duplicate IDs found: {dupes}")

    # 3. Check for duplicate names in same neighborhood
    name_hood = [(r["name"].lower().strip(), r["neighborhood"]) for r in data]
    nh_counts = Counter(name_hood)
    nh_dupes = {k: v for k, v in nh_counts.items() if v > 1}
    if nh_dupes:
        for (name, hood), count in nh_dupes.items():
            warnings.append(f"Possible duplicate: '{name}' in {hood} appears {count} times")

    # 4. Validate menu_tier values
    valid_tiers = {"confirmed", "likely", "none", None, ""}
    for r in data:
        if r.get("menu_tier") and r["menu_tier"] not in valid_tiers:
            errors.append(f"#{r['id']}: Invalid menu_tier '{r['menu_tier']}'")

    # 5. Validate coordinates
    for r in data:
        coords = r.get("coordinates", {})
        if coords and coords.get("lat"):
            lat, lng = coords["lat"], coords.get("lng", coords.get("lon"))
            if not (40.0 <= lat <= 42.0):
                warnings.append(f"#{r['id']}: Lat {lat} outside Barcelona range")
            if lng and not (1.5 <= lng <= 2.5):
                warnings.append(f"#{r['id']}: Lng {lng} outside Barcelona range")

    # 6. Price range validation
    for r in data:
        price = r.get("menu_price_range", "")
        if price:
            import re
            nums = re.findall(r"[\d.]+", price)
            for n in nums:
                val = float(n)
                if val > 50:
                    warnings.append(f"#{r['id']}: Unusually high price {val}€ in '{price}'")

    # 7. Stats
    tiers = Counter(r.get("menu_tier", "none") for r in data)
    hoods = len(set(r["neighborhood"] for r in data))
    cuisines = len(set(r["cuisine_type"] for r in data))
    has_coords = sum(1 for r in data if r.get("coordinates") and r["coordinates"].get("lat"))
    precise = sum(1 for r in data if r.get("coordinates") and r["coordinates"].get("lat")
                  and len(str(r["coordinates"]["lat"]).split(".")[-1]) >= 5)
    has_web = sum(1 for r in data if r.get("website"))
    has_phone = sum(1 for r in data if r.get("phone"))
    has_tags = sum(1 for r in data if r.get("tags") and len(r["tags"]) > 0)

    print(f"""
╔══════════════════════════════════════╗
║     MENUVERSO DATA VALIDATION        ║
╠══════════════════════════════════════╣
║ Total restaurants:  {total:<17}║
║ Neighborhoods:      {hoods:<17}║
║ Cuisine types:      {cuisines:<17}║
╠──────────────────────────────────────╣
║ Menu Tiers:                          ║
║   🟢 Confirmed:     {tiers.get('confirmed',0):<17}║
║   🟡 Likely:        {tiers.get('likely',0):<17}║
║   🔴 None:          {tiers.get('none',0) + tiers.get(None,0) + tiers.get('',0):<17}║
╠──────────────────────────────────────╣
║ Geocoding:                           ║
║   📌 Precise:       {precise:<17}║
║   📍 Centroid:      {has_coords-precise:<17}║
║   ❌ Missing:       {total-has_coords:<17}║
╠──────────────────────────────────────╣
║ Contact Data:                        ║
║   🌐 Website:       {has_web:<5} ({has_web/total*100:.0f}%)          ║
║   📞 Phone:         {has_phone:<5} ({has_phone/total*100:.0f}%)          ║
║   🏷️ Tags:          {has_tags:<5} ({has_tags/total*100:.0f}%)          ║
╚══════════════════════════════════════╝
""")

    if errors:
        print(f"\n❌ {len(errors)} ERRORS:")
        for e in errors[:20]:
            print(f"   • {e}")

    if warnings:
        print(f"\n⚠️  {len(warnings)} WARNINGS:")
        for w in warnings[:20]:
            print(f"   • {w}")

    if not errors and not warnings:
        print("✅ All checks passed! Data is clean.")

    return len(errors) == 0


if __name__ == "__main__":
    ok = validate()
    sys.exit(0 if ok else 1)
