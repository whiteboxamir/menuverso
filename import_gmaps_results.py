#!/usr/bin/env python3
"""Import scraped Google Maps batch results into restaurants.json"""

import json
import re
import sys
import glob

INPUT = "restaurants.json"

def normalize_phone(phone):
    if not phone: return None
    digits = re.sub(r'[^\d+]', '', str(phone))
    if not digits or len(digits) < 9: return None
    if not digits.startswith('+'):
        if digits.startswith('34'): digits = '+' + digits
        elif len(digits) == 9: digits = '+34' + digits
    if digits.startswith('+34') and len(digits) == 12:
        return f"+34 {digits[3:6]} {digits[6:8]} {digits[8:10]} {digits[10:12]}"
    return digits

def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    by_id = {r['id']: r for r in restaurants}
    
    # Load all batch files
    batch_files = sorted(glob.glob('/tmp/gmaps_results_batch*.json'))
    print(f"Found {len(batch_files)} batch files")
    
    all_results = []
    for bf in batch_files:
        with open(bf) as f:
            batch = json.load(f)
        all_results.extend(batch)
        print(f"  {bf}: {len(batch)} entries")
    
    print(f"\nTotal results to import: {len(all_results)}")
    
    stats = {'coords': 0, 'rating': 0, 'reviews': 0, 'phone': 0, 'website': 0, 'address': 0}
    
    for result in all_results:
        rid = result['id']
        if rid not in by_id:
            print(f"  ⚠ ID {rid} not found in database")
            continue
        
        r = by_id[rid]
        updates = []
        
        # Coords
        if result.get('lat') and result.get('lng'):
            lat, lng = float(result['lat']), float(result['lng'])
            if 41.3 <= lat <= 41.5 and 2.0 <= lng <= 2.3:
                if not (r.get('coordinates') and r['coordinates'].get('lat')):
                    r['coordinates'] = {'lat': lat, 'lng': lng}
                    updates.append('📍')
                    stats['coords'] += 1
                elif abs(r['coordinates']['lat'] - lat) + abs(r['coordinates']['lng'] - lng) > 0.001:
                    # Update if significantly different (browser data is more accurate)
                    r['coordinates'] = {'lat': lat, 'lng': lng}
                    updates.append('📍↻')
        
        # Rating
        if result.get('rating'):
            rating = float(result['rating'])
            if 1.0 <= rating <= 5.0:
                old_rating = float(str(r.get('google_maps_rating', 0) or 0))
                if old_rating == 0 or abs(old_rating - rating) > 0.01:
                    r['google_maps_rating'] = rating
                    updates.append('⭐')
                    stats['rating'] += 1
        
        # Reviews
        if result.get('reviews'):
            count = int(str(result['reviews']).replace(',', '').replace('.', ''))
            if count > 0:
                old_count = int(str(r.get('google_maps_review_count', 0) or 0).replace(',', ''))
                if old_count == 0 or abs(old_count - count) > 5:
                    r['google_maps_review_count'] = count
                    updates.append('💬')
                    stats['reviews'] += 1
        
        # Phone
        phone = normalize_phone(result.get('phone'))
        if phone and not (r.get('phone') and r['phone'].strip()):
            r['phone'] = phone
            updates.append('📞')
            stats['phone'] += 1
        
        # Website
        if result.get('website') and not (r.get('website') and r['website'].strip()):
            if 'google' not in result['website'].lower():
                r['website'] = result['website']
                updates.append('🌐')
                stats['website'] += 1
        
        # Address
        if result.get('address') and not (r.get('address_full') and r['address_full'].strip()):
            r['address_full'] = result['address']
            # Extract postal code
            postal = re.search(r'(\d{5})', result['address'])
            if postal and not r.get('postal_code'):
                r['postal_code'] = postal.group(1)
            updates.append('🏠')
            stats['address'] += 1
        
        if updates:
            print(f"  ✅ #{rid} {r['name'][:30]:30s} {' '.join(updates)}")
    
    # Save
    with open(INPUT, 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    # Regenerate JS
    js_content = 'var RESTAURANT_DATA = ' + json.dumps(restaurants, indent=2, ensure_ascii=False) + ';\n'
    with open('restaurants_data.js', 'w') as f:
        f.write(js_content)
    
    print(f"\n=== IMPORT COMPLETE ===")
    print(f"  📍 Coords: {stats['coords']}")
    print(f"  ⭐ Ratings: {stats['rating']}")
    print(f"  💬 Reviews: {stats['reviews']}")
    print(f"  📞 Phones: {stats['phone']}")
    print(f"  🌐 Websites: {stats['website']}")
    print(f"  🏠 Addresses: {stats['address']}")
    
    # Final stats
    total = len(restaurants)
    has_coords = sum(1 for r in restaurants if r.get('coordinates') and r['coordinates'].get('lat'))
    has_rating = sum(1 for r in restaurants if r.get('google_maps_rating') and float(str(r.get('google_maps_rating',0))) > 0)
    has_phone = sum(1 for r in restaurants if r.get('phone') and r['phone'].strip())
    print(f"\n  📊 DB TOTALS:")
    print(f"     Coords:  {has_coords}/{total} ({has_coords/total*100:.1f}%)")
    print(f"     Ratings: {has_rating}/{total} ({has_rating/total*100:.1f}%)")
    print(f"     Phones:  {has_phone}/{total} ({has_phone/total*100:.1f}%)")

if __name__ == "__main__":
    main()
