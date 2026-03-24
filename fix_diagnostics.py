#!/usr/bin/env python3
"""
Menuverso Data Fixer — Auto-fixes diagnostic issues and upgrades likely→confirmed candidates.
"""

import json
import re

INPUT = "restaurants.json"

def parse_price(s):
    if not s: return None
    nums = re.findall(r'[\d.]+', s)
    return float(nums[0]) if nums else None

def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    fixes = []
    upgrades = []

    # =========================================================================
    # FIX 1: Contradictory notes (3 entries)
    # =========================================================================
    for r in restaurants:
        if r.get("menu_tier") != "confirmed":
            continue
        notes = (r.get("notes", "") or "").lower()
        name = r.get("name", "")

        # Morgentau — "closed" in notes but not actually permanently closed
        if r["id"] == 54:
            # Keep as confirmed but note review needed
            pass

        # Fresc Co & Wok Garden — chain buffets, not traditional menú del día
        if r["id"] in (880, 881):
            r["menu_tier"] = "likely"
            r["menu_evidence"] = r.get("menu_evidence", "") or "auto_diagnostic"
            r["notes"] = (r.get("notes", "") or "") + " [Auto-review: chain buffet, downgraded from confirmed]"
            fixes.append(f"#{r['id']} {name}: confirmed → likely (chain buffet)")

    # =========================================================================
    # FIX 2: Tasting menus mislabeled as menú del día (3 entries)
    # =========================================================================
    tasting_ids = {75, 80, 1393}  # Angle, Mont Bar, Restaurant Gaig
    for r in restaurants:
        if r["id"] in tasting_ids and r.get("menu_tier") == "confirmed":
            # These are legitimate lunch offerings but they're tasting menus, not menú del día
            if "tasting" not in (r.get("tags") or []):
                r.setdefault("tags", []).append("tasting-menu")
            r["notes"] = (r.get("notes", "") or "") + " [Note: tasting menu format, not traditional menú del día]"
            fixes.append(f"#{r['id']} {r['name']}: tagged as tasting-menu, noted distinction")

    # =========================================================================
    # FIX 3: Upgrade 102 likely → confirmed candidates
    # =========================================================================
    for r in restaurants:
        if r.get("menu_tier") != "likely":
            continue

        notes = (r.get("notes", "") or "").lower()
        price = r.get("menu_price_range", "")
        has_price = bool(price and "€" in price)
        has_menu_keywords = any(w in notes for w in [
            "three-course", "three course", "primer plato", "segundo plato",
            "starter", "main", "dessert", "postre", "drink included",
            "bebida incluida", "bread", "menu del dia", "menú del día",
            "menu of the day", "daily menu", "lunch menu"
        ])

        if has_price and has_menu_keywords:
            r["menu_tier"] = "confirmed"
            r["menu_evidence"] = "auto_diagnostic"
            upgrades.append(f"#{r['id']} {r['name']}: likely → confirmed (price + keywords)")
        elif has_menu_keywords and not has_price:
            # Weaker signal — only upgrade if notes are really clear
            strong_keywords = ["three-course", "primer plato", "menú del día", "menu del dia"]
            if any(w in notes for w in strong_keywords):
                r["menu_tier"] = "confirmed"
                r["menu_evidence"] = "auto_diagnostic"
                upgrades.append(f"#{r['id']} {r['name']}: likely → confirmed (strong keywords)")

    # =========================================================================
    # Re-run tags to pick up any new tag-worthy changes
    # =========================================================================
    # Import tag logic
    from tag_restaurants import detect_tags
    tagged = 0
    for r in restaurants:
        tags = detect_tags(r)
        r["tags"] = tags
        if tags:
            tagged += 1

    # =========================================================================
    # Save
    # =========================================================================
    with open(INPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    # Report
    print(f"🔧 FIXES APPLIED ({len(fixes)}):")
    for fix in fixes:
        print(f"   {fix}")

    print(f"\n⬆️  UPGRADES ({len(upgrades)}):")
    for u in upgrades[:20]:
        print(f"   {u}")
    if len(upgrades) > 20:
        print(f"   ... and {len(upgrades) - 20} more")

    print(f"\n🏷️  Re-tagged: {tagged}/{len(restaurants)} restaurants")

    # New totals
    confirmed = sum(1 for r in restaurants if r["menu_tier"] == "confirmed")
    likely = sum(1 for r in restaurants if r["menu_tier"] == "likely")
    none_t = len(restaurants) - confirmed - likely
    print(f"\n📊 New distribution:")
    print(f"   Confirmed: {confirmed}")
    print(f"   Likely: {likely}")
    print(f"   None: {none_t}")
    print(f"\n   Output: {INPUT} + restaurants_data.js")


if __name__ == "__main__":
    main()
