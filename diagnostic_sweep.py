#!/usr/bin/env python3
"""
Menuverso Deep Diagnostics — Sweeps for false positives, errors, and inconsistencies.
Focuses especially on menu_tier='confirmed' entries that may be wrongly classified.
"""

import json
import re
from collections import Counter

INPUT = "restaurants.json"

def parse_price(s):
    if not s: return None
    nums = re.findall(r'[\d.]+', s)
    return float(nums[0]) if nums else None

def main():
    with open(INPUT) as f:
        data = json.load(f)

    confirmed = [r for r in data if r.get("menu_tier") == "confirmed"]
    likely = [r for r in data if r.get("menu_tier") == "likely"]
    none_tier = [r for r in data if r.get("menu_tier") == "none"]

    print(f"{'='*80}")
    print(f"MENUVERSO DIAGNOSTIC REPORT — {len(data)} restaurants")
    print(f"{'='*80}\n")

    # =========================================================================
    # 1. CONFIRMED MENU DEL DIA — FALSE POSITIVE DETECTION
    # =========================================================================
    print(f"🔍 SECTION 1: CONFIRMED MENÚ DEL DÍA FALSE POSITIVE SCAN ({len(confirmed)} entries)")
    print(f"{'─'*80}")

    # 1a. Confirmed but no price
    no_price = [r for r in confirmed if not r.get("menu_price_range")]
    if no_price:
        print(f"\n⚠️  1a. CONFIRMED but NO PRICE ({len(no_price)}):")
        print(f"   These claim to have a confirmed menú but show no price — suspicious.")
        for r in no_price[:30]:
            print(f"   #{r['id']:4d} {r['name']:35s} | {r['neighborhood']:15s} | notes: {(r.get('notes','') or '')[:60]}")
    else:
        print(f"\n✅ 1a. All confirmed entries have prices")

    # 1b. Confirmed but no evidence
    no_evidence = [r for r in confirmed if not r.get("menu_evidence") or r["menu_evidence"] == "none"]
    if no_evidence:
        print(f"\n⚠️  1b. CONFIRMED but NO EVIDENCE ({len(no_evidence)}):")
        print(f"   These are marked confirmed but have no evidence source.")
        for r in no_evidence[:20]:
            print(f"   #{r['id']:4d} {r['name']:35s} | evidence: {r.get('menu_evidence','')}")
    else:
        print(f"\n✅ 1b. All confirmed entries have evidence sources")

    # 1c. Confirmed but notes suggest otherwise
    suspicious_notes_words = ["no menú", "no menu", "not confirmed", "unconfirmed", "no ofrece", "sin menú",
                              "doesn't offer", "does not offer", "no longer", "ya no", "closed",
                              "cerrado", "permanently closed", "chain", "franchise"]
    suspicious_confirmed = []
    for r in confirmed:
        notes = (r.get("notes", "") or "").lower()
        name = (r.get("name", "") or "").lower()
        for word in suspicious_notes_words:
            if word in notes:
                suspicious_confirmed.append((r, word))
                break
    if suspicious_confirmed:
        print(f"\n🔴 1c. CONFIRMED but NOTES CONTRADICT ({len(suspicious_confirmed)}):")
        print(f"   These have notes suggesting the menú might not exist.")
        for r, word in suspicious_confirmed:
            print(f"   #{r['id']:4d} {r['name']:35s} | trigger: '{word}' | notes: {(r.get('notes','') or '')[:60]}")
    else:
        print(f"\n✅ 1c. No confirmed entries have contradictory notes")

    # 1d. Confirmed but status is closed
    closed_confirmed = [r for r in confirmed if r.get("status") in ("permanently_closed", "temporarily_closed")]
    if closed_confirmed:
        print(f"\n🔴 1d. CONFIRMED but CLOSED ({len(closed_confirmed)}):")
        for r in closed_confirmed:
            print(f"   #{r['id']:4d} {r['name']:35s} | status: {r['status']}")
    else:
        print(f"\n✅ 1d. No closed restaurants with confirmed menú")

    # 1e. Confirmed with suspiciously high price for "confirmed"
    expensive_confirmed = [r for r in confirmed if parse_price(r.get("menu_price_range", "")) and parse_price(r["menu_price_range"]) > 30]
    if expensive_confirmed:
        print(f"\n⚠️  1e. CONFIRMED with HIGH PRICE >30€ ({len(expensive_confirmed)}):")
        print(f"   Very expensive for a menú del día — might be tasting menu or á la carte.")
        for r in expensive_confirmed:
            print(f"   #{r['id']:4d} {r['name']:35s} | {r['menu_price_range']:10s} | {r['pricing_tier']:10s} | {(r.get('notes','') or '')[:50]}")
    else:
        print(f"\n✅ 1e. No suspiciously expensive confirmed menús")

    # 1f. Confirmed but cuisine type is unlikely for menú del día
    unlikely_cuisines = ["Japanese", "Chinese", "Korean", "Thai", "Indian", "Ethiopian", "Turkish"]
    unlikely_cuisine_confirmed = [r for r in confirmed if r.get("cuisine_type") in unlikely_cuisines]
    if unlikely_cuisine_confirmed:
        print(f"\n⚠️  1f. CONFIRMED with UNUSUAL CUISINE for menú del día ({len(unlikely_cuisine_confirmed)}):")
        print(f"   These cuisines rarely offer traditional menú del día — worth verifying.")
        for r in unlikely_cuisine_confirmed:
            print(f"   #{r['id']:4d} {r['name']:35s} | {r['cuisine_type']:15s} | {r.get('menu_price_range',''):8s} | {(r.get('notes','') or '')[:45]}")
    else:
        print(f"\n✅ 1f. No unusual cuisine types with confirmed menú")

    # 1g. Confirmed but premium pricing tier
    premium_confirmed = [r for r in confirmed if r.get("pricing_tier") == "premium"]
    if premium_confirmed:
        print(f"\n⚠️  1g. CONFIRMED + PREMIUM tier ({len(premium_confirmed)}):")
        print(f"   Premium restaurants with confirmed menú — could be tasting menus, not menú del día")
        for r in premium_confirmed[:20]:
            print(f"   #{r['id']:4d} {r['name']:35s} | {r.get('menu_price_range',''):10s} | {(r.get('notes','') or '')[:50]}")

    # =========================================================================
    # 2. GENERAL DATA QUALITY
    # =========================================================================
    print(f"\n\n🔍 SECTION 2: GENERAL DATA QUALITY")
    print(f"{'─'*80}")

    # 2a. Duplicate names (possible real duplicates)
    name_counts = Counter(r["name"] for r in data)
    dupes = [(n, c) for n, c in name_counts.items() if c > 1]
    if dupes:
        print(f"\n⚠️  2a. DUPLICATE NAMES ({len(dupes)} names, {sum(c for _,c in dupes)} entries):")
        for name, count in sorted(dupes, key=lambda x: -x[1])[:15]:
            entries = [r for r in data if r["name"] == name]
            hoods = set(r["neighborhood"] for r in entries)
            addrs = set(r.get("address_full", "") for r in entries if r.get("address_full"))
            if len(hoods) == 1 and len(addrs) <= 1:
                flag = "🔴 LIKELY DUPLICATE"
            else:
                flag = "🟡 may be branches"
            print(f"   '{name}' x{count} | hoods: {hoods} | {flag}")
    else:
        print(f"\n✅ 2a. No duplicate names")

    # 2b. Missing address_full  
    no_addr = [r for r in data if not r.get("address_full")]
    print(f"\n📊 2b. Missing full address: {len(no_addr)}/{len(data)} ({100*len(no_addr)/len(data):.0f}%)")
    if no_addr:
        by_hood = Counter(r["neighborhood"] for r in no_addr)
        print(f"   By neighborhood: {dict(by_hood.most_common(8))}")

    # 2c. Postal code anomalies
    bad_postal = [r for r in data if r.get("postal_code") and not re.match(r'^08\d{3}$', r["postal_code"])]
    if bad_postal:
        print(f"\n⚠️  2c. NON-BARCELONA POSTAL CODES ({len(bad_postal)}):")
        for r in bad_postal[:10]:
            print(f"   #{r['id']:4d} {r['name']:35s} | postal: {r['postal_code']} | {r['neighborhood']}")
    else:
        print(f"\n✅ 2c. All postal codes are Barcelona (08xxx)")

    # 2d. Rating anomalies
    zero_rating = [r for r in data if r.get("google_maps_rating") == 0]
    high_rating = [r for r in data if r.get("google_maps_rating") and r["google_maps_rating"] > 4.8 and r.get("google_maps_review_count", 0) > 100]
    low_reviews = [r for r in data if r.get("google_maps_review_count", 0) < 10 and r.get("google_maps_rating", 0) > 0]
    print(f"\n📊 2d. Rating analysis:")
    print(f"   Zero-rated: {len(zero_rating)}")
    print(f"   Elite (>4.8, >100 reviews): {len(high_rating)}")
    if high_rating:
        for r in high_rating[:10]:
            print(f"      #{r['id']:4d} {r['name']:35s} | ⭐{r['google_maps_rating']} ({r['google_maps_review_count']} rev)")
    print(f"   Low reviews (<10): {len(low_reviews)}")

    # 2e. Evidence source distribution for confirmed
    evidence_dist = Counter(r.get("menu_evidence", "unknown") for r in confirmed)
    print(f"\n📊 2e. Evidence sources for CONFIRMED entries:")
    for src, count in evidence_dist.most_common():
        print(f"   {src:20s} {count:4d}  {'█' * (count // 5)}")

    # 2f. Pricing tier vs actual price mismatch
    tier_mismatches = []
    for r in data:
        price = parse_price(r.get("menu_price_range", ""))
        tier = r.get("pricing_tier", "")
        if price:
            if tier == "budget" and price > 16:
                tier_mismatches.append((r, f"budget but {r['menu_price_range']}"))
            elif tier == "premium" and price < 15:
                tier_mismatches.append((r, f"premium but {r['menu_price_range']}"))
            elif tier == "mid-range" and price < 8:
                tier_mismatches.append((r, f"mid-range but {r['menu_price_range']}"))
    if tier_mismatches:
        print(f"\n⚠️  2f. PRICING TIER MISMATCHES ({len(tier_mismatches)}):")
        for r, reason in tier_mismatches[:15]:
            print(f"   #{r['id']:4d} {r['name']:35s} | {reason}")

    # =========================================================================
    # 3. COORDINATE ANOMALIES
    # =========================================================================
    print(f"\n\n🔍 SECTION 3: COORDINATE ANOMALIES")
    print(f"{'─'*80}")

    BCN_LAT = (41.32, 41.47)
    BCN_LNG = (2.05, 2.23)
    outside_bcn = []
    for r in data:
        c = r.get("coordinates", {})
        if c.get("lat") and c.get("lng"):
            if not (BCN_LAT[0] <= c["lat"] <= BCN_LAT[1] and BCN_LNG[0] <= c["lng"] <= BCN_LNG[1]):
                outside_bcn.append(r)
    if outside_bcn:
        print(f"\n🔴 3a. COORDINATES OUTSIDE BARCELONA ({len(outside_bcn)}):")
        for r in outside_bcn[:10]:
            c = r["coordinates"]
            print(f"   #{r['id']:4d} {r['name']:35s} | ({c['lat']:.4f}, {c['lng']:.4f}) | {r['neighborhood']}")
    else:
        print(f"\n✅ 3a. All geocoded coordinates are within Barcelona")

    # 3b. Duplicate coordinates (different restaurants at same exact point)
    coord_map = {}
    for r in data:
        c = r.get("coordinates", {})
        if c.get("lat") and c.get("lng"):
            key = (round(c["lat"], 5), round(c["lng"], 5))
            coord_map.setdefault(key, []).append(r)
    dupe_coords = {k: v for k, v in coord_map.items() if len(v) > 1}
    if dupe_coords:
        print(f"\n⚠️  3b. DUPLICATE COORDINATES ({len(dupe_coords)} locations, {sum(len(v) for v in dupe_coords.values())} restaurants):")
        for key, restaurants in list(dupe_coords.items())[:10]:
            names = [f"#{r['id']} {r['name']}" for r in restaurants]
            print(f"   ({key[0]}, {key[1]}): {', '.join(names)}")
    else:
        print(f"\n✅ 3b. No duplicate coordinates")

    # =========================================================================
    # 4. LIKELY → CONFIRMED CANDIDATES (under-classified)
    # =========================================================================
    print(f"\n\n🔍 SECTION 4: LIKELY → CONFIRMED UPGRADE CANDIDATES")
    print(f"{'─'*80}")

    upgrade_candidates = []
    for r in likely:
        notes = (r.get("notes", "") or "").lower()
        price = r.get("menu_price_range", "")
        has_strong_signal = False
        signals = []
        if price and "€" in price:
            has_strong_signal = True
            signals.append(f"has price ({price})")
        if any(w in notes for w in ["three-course", "three course", "primer plato", "segundo plato",
                                      "starter", "main", "dessert", "postre", "drink included",
                                      "bebida incluida", "bread", "menu del dia", "menú del día"]):
            has_strong_signal = True
            signals.append("menu keywords in notes")
        if has_strong_signal:
            upgrade_candidates.append((r, signals))

    if upgrade_candidates:
        print(f"\n🟡 Found {len(upgrade_candidates)} 'likely' restaurants that may deserve 'confirmed':")
        for r, signals in upgrade_candidates[:20]:
            print(f"   #{r['id']:4d} {r['name']:35s} | {', '.join(signals)} | {(r.get('notes','') or '')[:50]}")
        if len(upgrade_candidates) > 20:
            print(f"   ... and {len(upgrade_candidates) - 20} more")

    # =========================================================================
    # 5. SUMMARY
    # =========================================================================
    print(f"\n\n{'='*80}")
    print(f"DIAGNOSTIC SUMMARY")
    print(f"{'='*80}")
    issues = {
        "Confirmed + no price": len(no_price),
        "Confirmed + no evidence": len(no_evidence),
        "Confirmed + contradictory notes": len(suspicious_confirmed),
        "Confirmed + closed": len(closed_confirmed),
        "Confirmed + price >30€": len(expensive_confirmed),
        "Confirmed + unusual cuisine": len(unlikely_cuisine_confirmed),
        "Confirmed + premium tier": len(premium_confirmed),
        "Duplicate names": len(dupes),
        "Pricing tier mismatches": len(tier_mismatches),
        "Coords outside BCN": len(outside_bcn),
        "Duplicate coordinates": len(dupe_coords),
        "Likely → confirmed candidates": len(upgrade_candidates),
    }
    total_issues = sum(v for k, v in issues.items() if "candidate" not in k)
    print(f"\n   Total flagged items: {total_issues}")
    for label, count in issues.items():
        icon = "🔴" if count > 0 and "closed" in label.lower() else ("⚠️ " if count > 0 else "✅")
        print(f"   {icon} {label}: {count}")
    print()


if __name__ == "__main__":
    main()
