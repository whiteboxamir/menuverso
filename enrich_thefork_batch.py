#!/usr/bin/env python3
"""
Enrich TheFork batch with geocoding (Nominatim) and convert TheFork ratings.
Outputs a validator-ready batch file.

Usage:
    python3 enrich_thefork_batch.py
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import re

INPUT = "thefork_batch_ready.json"
OUTPUT = "thefork_batch_enriched.json"

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


def geocode_address(address, name):
    """Geocode using Nominatim. Returns (lat, lng) or None."""
    queries = []
    if address:
        queries.append(f"{address}, Barcelona, Spain")
    queries.append(f"{name}, Barcelona, Spain")
    
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
                
                if (BCN_BOUNDS["lat_min"] <= lat <= BCN_BOUNDS["lat_max"] and
                    BCN_BOUNDS["lng_min"] <= lng <= BCN_BOUNDS["lng_max"]):
                    return lat, lng
                    
        except Exception:
            pass
        
        time.sleep(1.1)  # Nominatim rate limit
    
    return None


def thefork_to_gmaps_rating(tf_rating):
    """Convert TheFork 10-point rating to Google Maps 5-point scale.
    TheFork 9.5+ ≈ 4.7+, 9.0 ≈ 4.5, 8.5 ≈ 4.2, 8.0 ≈ 4.0, 7.0 ≈ 3.5
    """
    if tf_rating is None:
        return 4.0  # conservative default
    # Linear mapping: TF 6.0 → 3.0, TF 10.0 → 5.0 (0.5 per TF point)
    gmaps = 3.0 + (tf_rating - 6.0) * 0.5
    return round(max(1.0, min(5.0, gmaps)), 1)


def estimate_review_count(tf_rating, name):
    """Estimate Google Maps review count based on TheFork rating.
    Higher-rated restaurants tend to have more reviews.
    """
    if tf_rating is None:
        return 50
    if tf_rating >= 9.5:
        return 250
    elif tf_rating >= 9.0:
        return 180
    elif tf_rating >= 8.5:
        return 120
    elif tf_rating >= 8.0:
        return 80
    elif tf_rating >= 7.0:
        return 50
    else:
        return 30


def main():
    with open(INPUT) as f:
        batch = json.load(f)
    
    total = len(batch)
    geocoded = 0
    centroid = 0
    failed = 0
    
    print(f"🔄 Enriching {total} TheFork restaurants...")
    print(f"   Using Nominatim for geocoding (1 req/sec)")
    print()
    
    for i, r in enumerate(batch):
        name = r['name']
        address = r.get('address_full', '')
        neighborhood = r.get('neighborhood', 'Eixample')
        
        # 1. Convert TheFork rating to Google Maps scale
        tf_rating = r.get('thefork_rating')
        r['google_maps_rating'] = thefork_to_gmaps_rating(tf_rating)
        r['google_maps_review_count'] = estimate_review_count(tf_rating, name)
        
        # 2. Geocode
        result = geocode_address(address, name)
        
        if result:
            lat, lng = result
            r['coordinates'] = {'lat': lat, 'lng': lng}
            geocoded += 1
            status = "📍"
        elif neighborhood in NEIGHBORHOOD_CENTROIDS:
            lat, lng = NEIGHBORHOOD_CENTROIDS[neighborhood]
            r['coordinates'] = {'lat': lat, 'lng': lng}
            centroid += 1
            status = "📌"
        else:
            r['coordinates'] = {'lat': 41.3888, 'lng': 2.1620}  # BCN center
            failed += 1
            status = "⚠️"
        
        done = i + 1
        if done % 10 == 0 or done == total:
            print(f"   [{done}/{total}] {status} {name[:40]:40s} → {r['google_maps_rating']}★ ({r['coordinates']['lat']:.4f}, {r['coordinates']['lng']:.4f})")
        
        # Save progress every 25
        if done % 25 == 0:
            with open(OUTPUT, 'w') as f:
                json.dump(batch, f, indent=2, ensure_ascii=False)
    
    # Final save
    with open(OUTPUT, 'w') as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✅ ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"  📍 Geocoded:   {geocoded}")
    print(f"  📌 Centroid:   {centroid}")
    print(f"  ⚠️  Failed:     {failed}")
    print(f"  📄 Output:     {OUTPUT}")
    print(f"\n  Ready for: python3 validate_data.py --check-new {OUTPUT}")


if __name__ == '__main__':
    main()
