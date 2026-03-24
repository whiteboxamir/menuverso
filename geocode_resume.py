#!/usr/bin/env python3
"""
Menuverso Geocoder — SAFE RESUME version.
Geocodes remaining 504 restaurants and MERGES only coordinates into the existing
restaurants.json WITHOUT overwriting tags, metro_station, google_maps_url, or other fields.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import os

INPUT = "restaurants.json"
PROGRESS_FILE = "/tmp/geocode_progress.json"

BCN_BOUNDS = {
    "lat_min": 41.32, "lat_max": 41.47,
    "lng_min": 2.05, "lng_max": 2.25
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Menuverso-Geocoder/1.0 (restaurant-database; contact@menuverso.com)"

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
    queries = []
    if address and postal_code:
        queries.append(f"{address}, {postal_code} Barcelona, Spain")
    if address:
        queries.append(f"{address}, Barcelona, Spain")
    if address and neighborhood:
        queries.append(f"{address}, {neighborhood}, Barcelona, Spain")

    for query in queries:
        params = urllib.parse.urlencode({
            "q": query, "format": "json", "limit": 1,
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
                lat, lng = float(data[0]["lat"]), float(data[0]["lon"])
                if (BCN_BOUNDS["lat_min"] <= lat <= BCN_BOUNDS["lat_max"] and
                    BCN_BOUNDS["lng_min"] <= lng <= BCN_BOUNDS["lng_max"]):
                    return lat, lng
        except Exception:
            if retry < 2:
                time.sleep(2)
                return geocode_address(address, postal_code, neighborhood, retry + 1)
        time.sleep(1.1)
    return None


def main():
    # Load progress cache
    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)
    print(f"📦 Loaded {len(progress)} cached results from progress file")

    # Load current restaurants.json (with tags, metro, etc. from other thread)
    with open(INPUT) as f:
        restaurants = json.load(f)
    total = len(restaurants)

    # Find which need geocoding (not in progress cache)
    to_geocode = []
    for r in restaurants:
        rid = str(r["id"])
        if rid not in progress and not (r.get("coordinates", {}).get("lat")):
            to_geocode.append(r)

    print(f"🗺️  Need to geocode: {len(to_geocode)} of {total} restaurants")
    print(f"   Already done: {len(progress)} cached + restaurants with coords\n")

    success = 0
    fallback = 0
    failed = 0

    for i, r in enumerate(to_geocode):
        rid = str(r["id"])
        address = r.get("address_full", "")
        postal = r.get("postal_code", "")
        neighborhood = r.get("neighborhood", "")

        if not address:
            if neighborhood in NEIGHBORHOOD_CENTROIDS:
                centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                progress[rid] = None  # centroid marker
                r["coordinates"] = {"lat": centroid[0], "lng": centroid[1]}
                fallback += 1
            else:
                progress[rid] = None
                failed += 1
            continue

        result = geocode_address(address, postal, neighborhood)
        if result:
            lat, lng = result
            progress[rid] = [lat, lng]
            r["coordinates"] = {"lat": lat, "lng": lng}
            success += 1
        else:
            if neighborhood in NEIGHBORHOOD_CENTROIDS:
                centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                r["coordinates"] = {"lat": centroid[0], "lng": centroid[1]}
                fallback += 1
            else:
                failed += 1
            progress[rid] = None

        done = i + 1
        if done % 25 == 0 or done == len(to_geocode):
            pct = done / len(to_geocode) * 100
            print(f"   [{done}/{len(to_geocode)}] ({pct:.0f}%) — ✅ {success} geocoded, 📍 {fallback} centroid, ❌ {failed} failed")
            with open(PROGRESS_FILE, "w") as f:
                json.dump(progress, f)

    # === SAFE MERGE: only update coordinates in the CURRENT restaurants.json ===
    print(f"\n🔀 Safe-merging coordinates into current restaurants.json...")

    # Re-read the LATEST restaurants.json (in case it was modified during geocoding)
    with open(INPUT) as f:
        current_data = json.load(f)

    # Build lookup from progress
    coords_applied = 0
    for r in current_data:
        rid = str(r["id"])
        # Skip if already has coords
        if r.get("coordinates", {}).get("lat"):
            continue
        # Apply from progress cache
        if rid in progress:
            cached = progress[rid]
            if cached:
                r["coordinates"] = {"lat": cached[0], "lng": cached[1]}
                coords_applied += 1
            else:
                # Centroid fallback
                neighborhood = r.get("neighborhood", "")
                if neighborhood in NEIGHBORHOOD_CENTROIDS:
                    centroid = NEIGHBORHOOD_CENTROIDS[neighborhood]
                    r["coordinates"] = {"lat": centroid[0], "lng": centroid[1]}
                    coords_applied += 1

    # Save merged result
    with open(INPUT, "w") as f:
        json.dump(current_data, f, indent=2, ensure_ascii=False)

    # Regenerate restaurants_data.js
    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(current_data, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    final_coords = sum(1 for r in current_data if r.get("coordinates", {}).get("lat"))
    print(f"\n{'='*50}")
    print(f"✅ Geocoding resume complete!")
    print(f"   New geocoded (precise): {success}")
    print(f"   New centroid fallback:   {fallback}")
    print(f"   Failed:                  {failed}")
    print(f"   Coords applied in merge: {coords_applied}")
    print(f"   Total with coords now:   {final_coords}/{len(current_data)}")
    print(f"\n   ⚠️  Only coordinates were modified — tags, metro, google_maps_url preserved!")


if __name__ == "__main__":
    main()
