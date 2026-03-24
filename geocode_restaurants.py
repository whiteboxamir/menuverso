#!/usr/bin/env python3
"""
Menuverso Geocoder — Batch geocode all restaurants using Nominatim (free, no API key).
Uses address_full + postal_code + "Barcelona" to get lat/lng coordinates.
Respects Nominatim's 1 request/second rate limit.
Writes results back to restaurants.json with coordinates field populated.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import sys
import os

INPUT = "restaurants.json"
OUTPUT = "restaurants.json"
PROGRESS_FILE = "/tmp/geocode_progress.json"

# Barcelona bounding box for validation
BCN_BOUNDS = {
    "lat_min": 41.32, "lat_max": 41.47,
    "lng_min": 2.05, "lng_max": 2.25
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Menuverso-Geocoder/1.0 (restaurant-database; contact@menuverso.com)"

# Fallback neighborhood centroids for when geocoding fails
NEIGHBORHOOD_CENTROIDS = {
    "Eixample": (41.3888, 2.1620),
    "Gràcia": (41.4036, 2.1567),
    "El Raval": (41.3800, 2.1680),
    "Poblenou": (41.4030, 2.2010),
    "El Born": (41.3850, 2.1830),
    "Barri Gòtic": (41.3830, 2.1770),
    "Poble Sec": (41.3720, 2.1610),
    "Sants": (41.3740, 2.1340),
    "Barceloneta": (41.3800, 2.1890),
    "Sarrià-Sant Gervasi": (41.4010, 2.1350),
    "Les Corts": (41.3870, 2.1270),
    "Sant Antoni": (41.3790, 2.1590),
    "Sagrada Família": (41.4036, 2.1744),
    "Horta-Guinardó": (41.4180, 2.1650),
    "Sant Martí": (41.4100, 2.1910),
    "Nou Barris": (41.4410, 2.1770),
    "Sant Andreu": (41.4350, 2.1900),
    "Clot": (41.4090, 2.1870),
}


def geocode_address(address, postal_code, neighborhood="", retry=0):
    """Geocode an address using Nominatim. Returns (lat, lng) or None."""
    
    # Build search query - try most specific first
    queries = []
    
    if address and postal_code:
        queries.append(f"{address}, {postal_code} Barcelona, Spain")
    if address:
        queries.append(f"{address}, Barcelona, Spain")
    if address and neighborhood:
        queries.append(f"{address}, {neighborhood}, Barcelona, Spain")
    
    for query in queries:
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "es",
            "viewbox": f"{BCN_BOUNDS['lng_min']},{BCN_BOUNDS['lat_max']},{BCN_BOUNDS['lng_max']},{BCN_BOUNDS['lat_min']}",
            "bounded": 1
        })
        
        url = f"{NOMINATIM_URL}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
                
                # Validate within Barcelona bounds
                if (BCN_BOUNDS["lat_min"] <= lat <= BCN_BOUNDS["lat_max"] and
                    BCN_BOUNDS["lng_min"] <= lng <= BCN_BOUNDS["lng_max"]):
                    return lat, lng
                    
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError) as e:
            if retry < 2:
                time.sleep(2)
                return geocode_address(address, postal_code, neighborhood, retry + 1)
        
        # Rate limit: 1 req/sec
        time.sleep(1.1)
    
    return None


def load_progress():
    """Load geocoding progress to resume interrupted runs."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(progress):
    """Save geocoding progress."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f)


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    total = len(restaurants)
    progress = load_progress()
    
    success = 0
    failed = 0
    skipped = 0
    fallback = 0
    already_done = 0
    
    print(f"🗺️  Geocoding {total} restaurants...")
    print(f"   Previous progress: {len(progress)} cached results\n")
    
    for i, r in enumerate(restaurants):
        rid = str(r["id"])
        name = r.get("name", "?")
        address = r.get("address_full", "")
        postal = r.get("postal_code", "")
        neighborhood = r.get("neighborhood", "")
        
        # Already has coordinates?
        if r.get("coordinates", {}).get("lat"):
            already_done += 1
            continue
        
        # Check progress cache
        if rid in progress:
            cached = progress[rid]
            if cached:
                r["coordinates"] = {"lat": cached[0], "lng": cached[1]}
                success += 1
            else:
                # Use neighborhood centroid as fallback
                if neighborhood in NEIGHBORHOOD_CENTROIDS:
                    centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                    r["coordinates"] = {"lat": centroid[0], "lng": centroid[1]}
                    fallback += 1
                else:
                    failed += 1
            continue
        
        # Need to geocode
        if not address:
            # No address — use neighborhood centroid
            if neighborhood in NEIGHBORHOOD_CENTROIDS:
                centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                r["coordinates"] = {"lat": centroid[0], "lng": centroid[1]}
                progress[rid] = None  # Mark as centroid fallback
                fallback += 1
            else:
                progress[rid] = None
                failed += 1
            continue
        
        result = geocode_address(address, postal, neighborhood)
        
        if result:
            lat, lng = result
            r["coordinates"] = {"lat": lat, "lng": lng}
            progress[rid] = [lat, lng]
            success += 1
        else:
            # Fallback to neighborhood centroid
            if neighborhood in NEIGHBORHOOD_CENTROIDS:
                centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                r["coordinates"] = {"lat": centroid[0], "lng": centroid[1]}
                fallback += 1
            else:
                failed += 1
            progress[rid] = None
        
        # Progress update
        done = i + 1
        if done % 25 == 0 or done == total:
            pct = done / total * 100
            print(f"   [{done}/{total}] ({pct:.0f}%) — ✅ {success} geocoded, 📍 {fallback} centroid, ❌ {failed} failed")
            save_progress(progress)
            
            # Save intermediate results every 100
            if done % 100 == 0:
                with open(OUTPUT, "w") as f:
                    json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    # Final save
    with open(OUTPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    # Regenerate restaurants_data.js
    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")
    
    print(f"\n{'='*50}")
    print(f"✅ Geocoding complete!")
    print(f"   Already had coords:  {already_done}")
    print(f"   Successfully geocoded: {success}")
    print(f"   Centroid fallback:     {fallback}")
    print(f"   Failed:                {failed}")
    print(f"   Total with coords:     {success + fallback + already_done}/{total}")
    print(f"\n   Output: {OUTPUT}")
    print(f"   JS data: restaurants_data.js")


if __name__ == "__main__":
    main()
