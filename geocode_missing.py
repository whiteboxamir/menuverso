#!/usr/bin/env python3
"""
Geocode restaurants with missing coordinates using OpenStreetMap Nominatim.
Rate-limited to 1 request/second per Nominatim usage policy.
"""

import json
import time
import urllib.request
import urllib.parse
import sys

INPUT_FILE = "restaurants.json"
OUTPUT_FILE = "restaurants.json"
USER_AGENT = "Menuverso/1.0 (geocoding batch)"

def geocode_nominatim(query, city="Barcelona", country="Spain"):
    """Geocode a single address via Nominatim. Returns (lat, lng) or None."""
    params = urllib.parse.urlencode({
        "q": f"{query}, {city}, {country}",
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data and len(data) > 0:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                # Sanity check: must be within greater Barcelona area
                if 41.3 <= lat <= 41.5 and 2.0 <= lon <= 2.3:
                    return (lat, lon)
                else:
                    return None
            return None
    except Exception as e:
        print(f"  ⚠ Error: {e}")
        return None


def build_query(restaurant):
    """Build the best possible geocoding query from available fields."""
    name = restaurant.get("name", "")
    addr_full = restaurant.get("address_full", "")
    postal = restaurant.get("postal_code", "")
    neighborhood = restaurant.get("neighborhood", "")
    
    # Strategy 1: Full street address + postal code (most precise)
    if addr_full and addr_full not in ["", "N/A"]:
        if postal and postal not in ["", "N/A"]:
            return f"{addr_full}, {postal} Barcelona"
        return f"{addr_full}, Barcelona"
    
    # Strategy 2: Restaurant name + neighborhood
    return f"{name}, {neighborhood}, Barcelona"


def main():
    with open(INPUT_FILE) as f:
        restaurants = json.load(f)
    
    # Find restaurants missing coordinates
    missing = [
        r for r in restaurants 
        if not (r.get("coordinates") and r["coordinates"].get("lat"))
    ]
    
    print(f"=== Nominatim Geocoding ===")
    print(f"Total restaurants: {len(restaurants)}")
    print(f"Missing coordinates: {len(missing)}")
    print(f"Rate: 1 request/second (Nominatim policy)")
    print(f"Estimated time: ~{len(missing) // 60} min {len(missing) % 60} sec")
    print()
    
    success = 0
    failed = 0
    skipped = 0
    
    for i, r in enumerate(missing):
        rid = r.get("id", "?")
        name = r.get("name", "Unknown")
        
        # Build query
        query = build_query(r)
        
        sys.stdout.write(f"[{i+1}/{len(missing)}] #{rid} {name[:35]:35s} → ")
        sys.stdout.flush()
        
        coords = geocode_nominatim(query)
        
        if coords:
            lat, lng = coords
            r["coordinates"] = {"lat": lat, "lng": lng}
            print(f"✅ ({lat:.6f}, {lng:.6f})")
            success += 1
        else:
            # Try fallback: name + neighborhood
            fallback_query = f"{name}, {r.get('neighborhood', 'Barcelona')}, Barcelona"
            if fallback_query != query:
                time.sleep(1.1)  # Rate limit
                coords = geocode_nominatim(fallback_query)
                if coords:
                    lat, lng = coords
                    r["coordinates"] = {"lat": lat, "lng": lng}
                    print(f"✅ fallback ({lat:.6f}, {lng:.6f})")
                    success += 1
                else:
                    print(f"❌ not found")
                    failed += 1
            else:
                print(f"❌ not found")
                failed += 1
        
        # Rate limit: 1 request per second
        time.sleep(1.1)
        
        # Save progress every 25 restaurants
        if (i + 1) % 25 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(restaurants, f, indent=2, ensure_ascii=False)
            print(f"\n  💾 Progress saved ({success} geocoded, {failed} failed)\n")
    
    # Final save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== COMPLETE ===")
    print(f"  ✅ Geocoded: {success}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📊 New coverage: {len(restaurants) - len(missing) + success}/{len(restaurants)} ({(len(restaurants) - len(missing) + success)/len(restaurants)*100:.1f}%)")


if __name__ == "__main__":
    main()
