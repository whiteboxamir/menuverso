#!/usr/bin/env python3
"""
Batch extract coordinates and basic data for TheFork entries by scraping
Google Maps via the browser. Generates a JavaScript bookmarklet that,
when run in the browser console, processes each Google Maps URL and
extracts the coordinates from the final resolved URL.

Since we can't run 108 browser sessions, this script takes a different
approach: it uses the Google Places Autocomplete-style lookups via
Nominatim with restaurant name + neighborhood combinations.

Strategy:
1. For entries with TheFork-enriched address_full: geocode that
2. For name-only entries: try Google Maps text search via public API
3. Fallback: use neighborhood centroid + random offset
"""

import json
import time
import urllib.request
import urllib.parse
import sys
import re

INPUT = "restaurants.json"
USER_AGENT = "Menuverso/1.0 (thefork-geocode)"
DELAY = 1.2

def geocode_nominatim(query):
    """Geocode via Nominatim. Returns (lat, lng) or None."""
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "es",
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                if 41.3 <= lat <= 41.5 and 2.0 <= lon <= 2.3:
                    return (lat, lon)
    except:
        pass
    return None


def try_multiple_queries(name, neighborhood, address_full=""):
    """Try multiple geocoding strategies for a restaurant."""
    
    queries = []
    
    # Strategy 1: Full address if available
    if address_full and address_full.strip():
        queries.append(f"{address_full}, Barcelona, Spain")
    
    # Strategy 2: Name + Barcelona (exact business search)
    queries.append(f"{name} restaurant, Barcelona, Spain")
    
    # Strategy 3: Name + neighborhood
    queries.append(f"{name}, {neighborhood}, Barcelona, Spain")
    
    # Strategy 4: Just the name in Barcelona
    queries.append(f"{name}, Barcelona")
    
    # Strategy 5: Simplified name (remove suffixes)
    simplified = re.sub(r'\s*[-–]\s.*$', '', name)  # Remove " - Location" suffixes
    simplified = re.sub(r'\s+Barcelona$', '', simplified, flags=re.IGNORECASE)
    if simplified != name:
        queries.append(f"{simplified} restaurant, Barcelona, Spain")
    
    for query in queries:
        result = geocode_nominatim(query)
        if result:
            return result, query
        time.sleep(DELAY)
    
    return None, None


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    # Target: TheFork entries missing coordinates
    tf_no_coords = [r for r in restaurants 
                    if r.get('source') == 'thefork' 
                    and not (r.get('coordinates') and r['coordinates'].get('lat'))]
    
    print("=" * 65)
    print("📍 THEFORK COORDINATE ENRICHMENT (Multi-Strategy Nominatim)")
    print("=" * 65)
    print(f"\nTheFork entries missing coords: {len(tf_no_coords)}")
    print(f"Using 5-strategy geocoding approach")
    print()
    
    success = 0
    failed = 0
    
    for i, r in enumerate(tf_no_coords):
        rid = r['id']
        name = r['name']
        hood = r.get('neighborhood', '')
        addr = r.get('address_full', '')
        
        sys.stdout.write(f"[{i+1}/{len(tf_no_coords)}] #{rid} {name[:38]:38s} → ")
        sys.stdout.flush()
        
        coords, query = try_multiple_queries(name, hood, addr)
        
        if coords:
            lat, lng = coords
            r['coordinates'] = {'lat': lat, 'lng': lng}
            print(f"✅ ({lat:.6f}, {lng:.6f})")
            success += 1
        else:
            print(f"❌ not found")
            failed += 1
        
        # Save every 20
        if (i + 1) % 20 == 0:
            with open(INPUT, 'w') as f:
                json.dump(restaurants, f, indent=2, ensure_ascii=False)
            print(f"\n  💾 Progress saved ({success} found, {failed} failed)\n")
    
    # Final save
    with open(INPUT, 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    # Regenerate JS
    js_content = 'const RESTAURANT_DATA = ' + json.dumps(restaurants, indent=2, ensure_ascii=False) + ';\n'
    with open('restaurants_data.js', 'w') as f:
        f.write(js_content)
    
    print(f"\n{'=' * 65}")
    print(f"  ✅ Found: {success}")
    print(f"  ❌ Failed: {failed}")

    # Final stats
    total = len(restaurants)
    has_coords = sum(1 for r in restaurants if r.get('coordinates') and r['coordinates'].get('lat'))
    print(f"\n  📊 TOTAL MAP COVERAGE: {has_coords}/{total} ({has_coords/total*100:.1f}%)")


if __name__ == "__main__":
    main()
