#!/usr/bin/env python3
"""
Menuverso Geocoder — Batch geocode all restaurants using Nominatim (free, no API key).
Uses address_full + postal_code + "Barcelona" to get lat/lng coordinates.
Respects Nominatim's 1 request/second rate limit.
MERGES only coordinates back into restaurants.json — does NOT overwrite other fields.
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


def merge_coordinates_into_file(coord_map):
    """Re-read the CURRENT restaurants.json and only update coordinates.
    This preserves tags, metro_station, google_maps_url, menu_tier, etc."""
    with open(INPUT) as f:
        current = json.load(f)
    for r in current:
        rid = str(r["id"])
        if rid in coord_map and coord_map[rid] is not None:
            r["coordinates"] = {"lat": coord_map[rid][0], "lng": coord_map[rid][1]}
    with open(OUTPUT, "w") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(current, f, indent=2, ensure_ascii=False)
        f.write(";\n")


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    total = len(restaurants)
    progress = load_progress()
    
    # Build a map of ALL coordinates (existing + new)
    coord_map = {}  # id -> [lat, lng] or None
    
    success = 0
    failed = 0
    skipped = 0
    fallback = 0
    already_done = 0
    
    print(f"🗺️  Geocoding {total} restaurants...")
    print(f"   Previous progress: {len(progress)} cached results")
    print(f"   ⚠️  Safe mode: will ONLY merge coordinates, not overwrite other fields\n")
    
    for i, r in enumerate(restaurants):
        rid = str(r["id"])
        name = r.get("name", "?")
        address = r.get("address_full", "")
        postal = r.get("postal_code", "")
        neighborhood = r.get("neighborhood", "")
        
        # Already has precise coordinates (5+ decimal places)?
        existing_lat = r.get("coordinates", {}).get("lat")
        if existing_lat:
            lat_str = str(existing_lat)
            decimals = len(lat_str.split('.')[-1]) if '.' in lat_str else 0
            if decimals >= 5:
                coord_map[rid] = [existing_lat, r["coordinates"]["lng"]]
                already_done += 1
                continue
        
        # Check progress cache
        if rid in progress:
            cached = progress[rid]
            if cached:
                coord_map[rid] = cached
                success += 1
            else:
                # Use neighborhood centroid as fallback
                if neighborhood in NEIGHBORHOOD_CENTROIDS:
                    centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                    coord_map[rid] = [centroid[0], centroid[1]]
                    fallback += 1
                else:
                    failed += 1
            continue
        
        # Need to geocode
        if not address:
            # No address — use neighborhood centroid
            if neighborhood in NEIGHBORHOOD_CENTROIDS:
                centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                coord_map[rid] = [centroid[0], centroid[1]]
                progress[rid] = None  # Mark as centroid fallback
                fallback += 1
            else:
                progress[rid] = None
                failed += 1
            continue
        
        result = geocode_address(address, postal, neighborhood)
        
        if result:
            lat, lng = result
            coord_map[rid] = [lat, lng]
            progress[rid] = [lat, lng]
            success += 1
        else:
            # Fallback to neighborhood centroid
            if neighborhood in NEIGHBORHOOD_CENTROIDS:
                centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                coord_map[rid] = [centroid[0], centroid[1]]
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
            
            # Merge intermediate results every 100 (safe merge, not overwrite)
            if done % 100 == 0:
                merge_coordinates_into_file(coord_map)
                print(f"   💾 Saved (coordinates only, other fields preserved)")
    
    # Final safe merge
    merge_coordinates_into_file(coord_map)
    
    print(f"\n{'='*50}")
    print(f"✅ Geocoding complete!")
    print(f"   Already had precise coords: {already_done}")
    print(f"   Successfully geocoded:      {success}")
    print(f"   Centroid fallback:          {fallback}")
    print(f"   Failed:                     {failed}")
    print(f"   Total with coords:          {len(coord_map)}/{total}")
    print(f"\n   Output: {OUTPUT} (coordinates merged safely)")
    print(f"   JS data: restaurants_data.js")


if __name__ == "__main__":
    main()
