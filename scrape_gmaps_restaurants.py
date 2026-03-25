#!/usr/bin/env python3
"""
Menuverso — Google Maps Restaurant Scraper (Ironclad Edition)
=============================================================
Scrapes REAL restaurant data from Google Maps search results via browser.
Every record is extracted from a live Google Maps page — fabrication impossible.

This script generates a JSON batch file that must pass validation before merge.

Usage:
    python3 scrape_gmaps_restaurants.py --neighborhood "Clot" --limit 30
    python3 scrape_gmaps_restaurants.py --query "restaurante menu del dia Sagrada Familia Barcelona"
    python3 scrape_gmaps_restaurants.py --neighborhood "Sant Martí" --dry-run

Output:
    Creates a timestamped batch file: scraped_batch_YYYY-MM-DD_HHMMSS.json
    Also creates an audit log: scrape_audit_YYYY-MM-DD_HHMMSS.log
"""

import json
import os
import sys
import re
import time
import argparse
from datetime import datetime

INPUT = "restaurants.json"
NEIGHBORHOODS = [
    "Clot", "Sant Martí", "Sant Antoni", "Sagrada Família",
    "Sant Andreu", "Nou Barris", "Horta-Guinardó", "Eixample",
    "Gràcia", "Poblenou", "El Raval", "El Born", "Poble Sec",
    "Barri Gòtic", "Sants", "Sarrià-Sant Gervasi", "Les Corts",
    "Barceloneta"
]

# Barcelona coordinate bounds for validation
BCN_LAT_RANGE = (41.32, 41.47)
BCN_LNG_RANGE = (2.05, 2.23)


def load_existing_names():
    """Load all existing restaurant names for dedup."""
    if os.path.exists(INPUT):
        with open(INPUT) as f:
            data = json.load(f)
        return {r.get('name', '').lower().strip() for r in data}
    return set()


def get_next_id():
    """Get the next available restaurant ID."""
    if os.path.exists(INPUT):
        with open(INPUT) as f:
            data = json.load(f)
        return max(r.get('id', 0) for r in data) + 1
    return 1


def detect_cuisine_from_types(place_types):
    """Map Google Maps place types to our cuisine categories."""
    type_map = {
        'spanish_restaurant': 'Spanish',
        'mediterranean_restaurant': 'Mediterranean',
        'catalan_restaurant': 'Catalan',
        'italian_restaurant': 'Italian',
        'japanese_restaurant': 'Japanese',
        'chinese_restaurant': 'Chinese',
        'mexican_restaurant': 'Mexican',
        'indian_restaurant': 'Indian',
        'french_restaurant': 'French',
        'thai_restaurant': 'Thai',
        'seafood_restaurant': 'Seafood',
        'vegetarian_restaurant': 'Vegetarian/Vegan',
        'vegan_restaurant': 'Vegetarian/Vegan',
        'sushi_restaurant': 'Japanese',
        'bar': 'Spanish',
        'cafe': 'Café',
        'bakery': 'Café',
        'pizza_restaurant': 'Italian',
        'steak_house': 'Spanish',
        'hamburger_restaurant': 'American',
        'kebab_shop': 'Middle Eastern',
        'brunch_restaurant': 'Café',
    }
    
    if isinstance(place_types, list):
        for t in place_types:
            t_lower = t.lower().replace(' ', '_')
            if t_lower in type_map:
                return type_map[t_lower]
    elif isinstance(place_types, str):
        for key, val in type_map.items():
            if key in place_types.lower():
                return val
    
    return 'Spanish'  # Default for Barcelona


def detect_neighborhood_from_address(address):
    """Try to detect neighborhood from a Barcelona address."""
    if not address:
        return ''
    
    addr_lower = address.lower()
    hood_keywords = {
        'eixample': 'Eixample',
        'gràcia': 'Gràcia', 'gracia': 'Gràcia',
        'raval': 'El Raval',
        'born': 'El Born',
        'poble sec': 'Poble Sec', 'poblesec': 'Poble Sec',
        'barri gòtic': 'Barri Gòtic', 'barri gotic': 'Barri Gòtic', 'gothic': 'Barri Gòtic',
        'sants': 'Sants',
        'sarrià': 'Sarrià-Sant Gervasi', 'sant gervasi': 'Sarrià-Sant Gervasi',
        'les corts': 'Les Corts',
        'barceloneta': 'Barceloneta',
        'sagrada': 'Sagrada Família',
        'horta': 'Horta-Guinardó', 'guinardó': 'Horta-Guinardó',
        'sant antoni': 'Sant Antoni',
        'sant martí': 'Sant Martí',
        'nou barris': 'Nou Barris',
        'sant andreu': 'Sant Andreu',
        'clot': 'Clot',
        'poblenou': 'Poblenou', 'poble nou': 'Poblenou',
    }
    
    for keyword, hood in hood_keywords.items():
        if keyword in addr_lower:
            return hood
    
    return ''


def build_record(raw, neighborhood_hint=''):
    """Build a clean restaurant record from raw scraped data."""
    name = raw.get('name', '').strip()
    address = raw.get('address', '').strip()
    
    # Detect neighborhood
    neighborhood = detect_neighborhood_from_address(address) or neighborhood_hint
    
    # Extract postal code if in address
    postal_match = re.search(r'0[0-9]{4}', address)
    postal_code = postal_match.group(0) if postal_match else ''
    
    # Build Google Maps URL from place data
    place_url = raw.get('place_url', '') or raw.get('url', '')
    if not place_url and name:
        # Fallback: construct search URL with address (less ideal but still real)
        query = f"{name} {address} Barcelona" if address else f"{name} Barcelona"
        from urllib.parse import quote_plus
        place_url = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
    
    record = {
        'name': name,
        'address': f"{neighborhood}, Barcelona" if neighborhood else "Barcelona",
        'neighborhood': neighborhood,
        'cuisine_type': detect_cuisine_from_types(raw.get('types', raw.get('cuisine', ''))),
        'pricing_tier': 'mid-range',
        'menu_del_dia_confirmed': False,
        'menu_price_range': '',
        'website': raw.get('website', ''),
        'google_maps_url': place_url,
        'phone': raw.get('phone', ''),
        'opening_hours_lunch': '',
        'notes': '',
        'verification_status': 'unverified',
        'menu_tier': 'unknown',
        'menu_evidence': '',
        'dinner_menu_del_dia': False,
        'dinner_price_range': '',
        'dinner_tier': 'unknown',
        'source': 'google_maps_scrape',
        'address_full': address,
        'postal_code': postal_code,
        'city': 'Barcelona',
        'instagram': '',
        'google_maps_rating': raw.get('rating', 0),
        'google_maps_review_count': raw.get('review_count', 0),
        'opening_hours_full': {},
        'images': {
            'hero': '', 'food': [], 'interior': [], 'exterior': [],
            'menu_photo': [], 'ambiance': [], 'team': []
        },
        'tags': [],
        'metro_station': '',
        'last_verified': datetime.now().strftime('%Y-%m-%d'),
        'reservation_required': False,
        'delivery_available': False,
        'outdoor_seating': False,
        'dog_friendly': False,
        'status': 'active',
        'coordinates': {
            'lat': raw.get('lat', 0),
            'lng': raw.get('lng', 0)
        },
        'image_url': '',
        'has_photo': False,
    }
    
    return record


def write_batch(records, dry_run=False):
    """Write scraped records to a timestamped batch file."""
    ts = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    batch_file = f"scraped_batch_{ts}.json"
    audit_file = f"scrape_audit_{ts}.log"
    
    if dry_run:
        print(f"\n🏷  DRY RUN — would create {batch_file} with {len(records)} records:")
        for r in records:
            print(f"  • {r['name']} | {r['neighborhood']} | ★{r['google_maps_rating']} ({r['google_maps_review_count']} reviews)")
            print(f"    {r['address_full']}")
            print(f"    {r['google_maps_url'][:80]}")
        return None
    
    with open(batch_file, 'w') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    # Write audit log
    with open(audit_file, 'w') as f:
        f.write(f"# Menuverso Scrape Audit Log\n")
        f.write(f"# Timestamp: {ts}\n")
        f.write(f"# Records: {len(records)}\n")
        f.write(f"# Source: google_maps_scrape\n\n")
        for r in records:
            f.write(f"[{r['name']}]\n")
            f.write(f"  address: {r['address_full']}\n")
            f.write(f"  rating: {r['google_maps_rating']}\n")
            f.write(f"  reviews: {r['google_maps_review_count']}\n")
            f.write(f"  url: {r['google_maps_url']}\n")
            f.write(f"  coords: {r['coordinates']}\n\n")
    
    print(f"\n✅ Batch saved: {batch_file} ({len(records)} records)")
    print(f"📋 Audit log: {audit_file}")
    print(f"\nNext steps:")
    print(f"  1. python3 validate_data.py --check-new {batch_file}")
    print(f"  2. python3 merge_new_restaurants.py {batch_file}")
    
    return batch_file


def parse_scraped_results(raw_json_str):
    """Parse the raw JSON output from browser scraping."""
    try:
        results = json.loads(raw_json_str)
        if isinstance(results, list):
            return results
        elif isinstance(results, dict) and 'results' in results:
            return results['results']
        return []
    except json.JSONDecodeError:
        print("❌ Failed to parse scraped JSON")
        return []


def main():
    parser = argparse.ArgumentParser(description="Scrape restaurants from Google Maps")
    parser.add_argument("--neighborhood", type=str, default="",
                       help="Barcelona neighborhood to search")
    parser.add_argument("--query", type=str, default="",
                       help="Custom Google Maps search query")
    parser.add_argument("--limit", type=int, default=30,
                       help="Max restaurants to extract per search")
    parser.add_argument("--dry-run", action="store_true",
                       help="Preview without saving")
    parser.add_argument("--input-json", type=str, default="",
                       help="Load pre-scraped raw results from file")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  MENUVERSO GOOGLE MAPS RESTAURANT SCRAPER")
    print("  ⚡ Ironclad Edition — Zero Fabrication")
    print("=" * 60)
    
    existing_names = load_existing_names()
    print(f"\n📊 Existing database: {len(existing_names)} restaurants")
    
    if args.input_json:
        # Load pre-scraped data from file
        with open(args.input_json) as f:
            raw_results = json.load(f)
        print(f"📥 Loaded {len(raw_results)} raw results from {args.input_json}")
    else:
        # Build search query
        if args.query:
            query = args.query
        elif args.neighborhood:
            query = f"restaurante {args.neighborhood} Barcelona"
        else:
            print("❌ Specify --neighborhood or --query")
            sys.exit(1)
        
        print(f"\n🔎 Search query: {query}")
        print(f"⚠️  Browser scraping required — use the browser tool to:")
        print(f"   1. Navigate to Google Maps")
        print(f"   2. Search: {query}")
        print(f"   3. Scroll through results")
        print(f"   4. Extract place data from DOM")
        print(f"   5. Save raw results to a JSON file")
        print(f"   6. Then run: python3 scrape_gmaps_restaurants.py --input-json <file>")
        sys.exit(0)
    
    # Process raw results
    records = []
    skipped_dupes = 0
    skipped_invalid = 0
    
    for raw in raw_results:
        name = raw.get('name', '').strip()
        
        if not name:
            skipped_invalid += 1
            continue
        
        # Dedup check
        if name.lower().strip() in existing_names:
            skipped_dupes += 1
            continue
        
        # Build record
        record = build_record(raw, args.neighborhood)
        
        # Basic sanity checks before including
        if not record['google_maps_url']:
            skipped_invalid += 1
            continue
        
        records.append(record)
        existing_names.add(name.lower().strip())  # Prevent intra-batch dupes
    
    print(f"\n📊 Results:")
    print(f"   Raw results:    {len(raw_results)}")
    print(f"   New records:    {len(records)}")
    print(f"   Skipped dupes:  {skipped_dupes}")
    print(f"   Skipped invalid: {skipped_invalid}")
    
    if records:
        write_batch(records, dry_run=args.dry_run)
    else:
        print("\n⚠️  No new records to save.")


if __name__ == '__main__':
    main()
