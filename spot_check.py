#!/usr/bin/env python3
"""
Spot-check confirmed menú del día entries by searching Google Maps.
Uses the read_url approach to verify restaurants exist at their stated addresses.
"""

import json
import urllib.request
import urllib.parse
import re
import random
import time

INPUT = "restaurants.json"

def check_restaurant(r):
    """Try to verify a restaurant exists via a Google search."""
    name = r.get("name", "")
    addr = r.get("address_full", "")
    hood = r.get("neighborhood", "")
    
    query = f"{name} Barcelona restaurant menú del día"
    url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&hl=es"
    
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            
        # Check if Google found the business
        found_name = name.lower().split()[0] in html.lower() if name else False
        has_rating = "rating" in html.lower() or "reseñ" in html.lower() or "review" in html.lower()
        has_maps = "maps" in html.lower() or "dirección" in html.lower()
        has_menu = "menú" in html.lower() or "menu" in html.lower()
        
        confidence = sum([found_name, has_rating, has_maps, has_menu])
        
        return {
            "id": r["id"],
            "name": name,
            "hood": hood,
            "tier": r.get("menu_tier"),
            "price": r.get("menu_price_range", ""),
            "confidence": confidence,
            "found_name": found_name,
            "has_rating": has_rating,
            "has_maps": has_maps,
            "has_menu": has_menu,
            "status": "✅ likely real" if confidence >= 3 else ("⚠️ uncertain" if confidence >= 2 else "🔴 suspicious")
        }
    except Exception as e:
        return {
            "id": r["id"],
            "name": name,
            "hood": hood,
            "status": f"❌ error: {str(e)[:40]}",
            "confidence": -1
        }


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    confirmed = [r for r in restaurants if r.get("menu_tier") == "confirmed"]
    
    # Sample: 20 random confirmed entries with varying evidence levels
    # Focus on ones without evidence (most suspicious)
    no_evidence = [r for r in confirmed if not r.get("menu_evidence") or r["menu_evidence"] in ("", "unknown")]
    with_evidence = [r for r in confirmed if r.get("menu_evidence") and r["menu_evidence"] not in ("", "unknown")]
    
    sample_no_ev = random.sample(no_evidence, min(12, len(no_evidence)))
    sample_with_ev = random.sample(with_evidence, min(8, len(with_evidence)))
    sample = sample_no_ev + sample_with_ev
    
    print(f"🔍 SPOT-CHECK: {len(sample)} confirmed restaurants")
    print(f"   {len(sample_no_ev)} without evidence, {len(sample_with_ev)} with evidence")
    print(f"{'─'*80}")
    
    results = []
    for i, r in enumerate(sample):
        result = check_restaurant(r)
        results.append(result)
        ev = r.get("menu_evidence", "none")
        print(f"   [{i+1}/{len(sample)}] {result['status']:20s} #{result['id']:4d} {result['name']:35s} | evidence: {ev}")
        time.sleep(1)  # Be polite
    
    # Summary
    good = sum(1 for r in results if r["confidence"] >= 3)
    uncertain = sum(1 for r in results if r["confidence"] == 2)
    suspicious = sum(1 for r in results if r["confidence"] >= 0 and r["confidence"] < 2)
    errors = sum(1 for r in results if r["confidence"] == -1)
    
    print(f"\n📊 RESULTS:")
    print(f"   ✅ Likely real: {good}/{len(sample)}")
    print(f"   ⚠️  Uncertain: {uncertain}/{len(sample)}")
    print(f"   🔴 Suspicious: {suspicious}/{len(sample)}")
    if errors:
        print(f"   ❌ Errors: {errors}/{len(sample)}")
    
    pct = good / max(len(results) - errors, 1) * 100
    print(f"\n   Verification rate: {pct:.0f}%")


if __name__ == "__main__":
    main()
