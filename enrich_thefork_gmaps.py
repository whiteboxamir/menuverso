#!/usr/bin/env python3
"""
Menuverso — TheFork Entry Enrichment via Google Maps Search
Enriches hollow TheFork entries by searching Google Maps and extracting
structured data from the search results page HTML.

Uses the google_maps_url already stored on each TheFork entry.

Fields to backfill: rating, review_count, coordinates, phone, website,
                    address_full, postal_code, opening_hours
"""

import json
import re
import sys
import time
import urllib.request
import urllib.parse

INPUT = "restaurants.json"
DELAY = 2.0  # seconds between requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}


def fetch_page(url):
    """Fetch a URL and return the HTML text."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None


def extract_from_gmaps_html(html, name, neighborhood):
    """Extract structured data from Google Maps search result HTML.
    
    Google Maps search pages embed JSON-LD and various structured data
    in the HTML even without JavaScript execution.
    """
    result = {}
    
    # ── Coordinates ──
    # Google Maps embeds coordinates in various URL patterns
    coord_patterns = [
        r'@(-?\d+\.\d+),(-?\d+\.\d+)',           # @lat,lng in URL
        r'center=(-?\d+\.\d+),(-?\d+\.\d+)',       # center=lat,lng
        r'\[null,null,(-?\d+\.\d+),(-?\d+\.\d+)\]', # JSON arrays
        r'"(-?\d+\.\d{4,})"[,\s]*"(-?\d+\.\d{4,})"', # Quoted coords
    ]
    for pattern in coord_patterns:
        matches = re.findall(pattern, html)
        for m in matches:
            lat, lng = float(m[0]), float(m[1])
            # Barcelona bounding box
            if 41.3 <= lat <= 41.5 and 2.0 <= lng <= 2.3:
                result['lat'] = lat
                result['lng'] = lng
                break
        if 'lat' in result:
            break
    
    # ── Phone ──
    phone_patterns = [
        r'\"(\+34\s?\d{3}\s?\d{2,3}\s?\d{2,3}\s?\d{2,3})\"',
        r'(\+34[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3})',
        r'(\+34[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2})',
        r'tel:(\+?34?\d{9,12})',
        r'href=\"tel:([^\"]+)\"',
        r'\"(9\d{2}\s?\d{2,3}\s?\d{2,3}\s?\d{2,3})\"',
    ]
    for pattern in phone_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            phone = re.sub(r'[^\d+]', '', match)
            if len(phone) >= 9 and not phone.startswith('000'):
                if not phone.startswith('+'):
                    if phone.startswith('34'):
                        phone = '+' + phone
                    elif len(phone) == 9:
                        phone = '+34' + phone
                if phone.startswith('+34') and len(phone) == 12:
                    result['phone'] = f"+34 {phone[3:6]} {phone[6:8]} {phone[8:10]} {phone[10:12]}"
                else:
                    result['phone'] = phone
                break
        if 'phone' in result:
            break
    
    # ── Website ──
    website_patterns = [
        r'"(https?://(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[^"\s]*)?)"',
    ]
    blocked_domains = ['google.com', 'facebook.com', 'instagram.com', 'twitter.com', 
                       'tripadvisor', 'yelp.com', 'thefork.com', 'gstatic.com',
                       'googleapis.com', 'youtube.com', 'apple.com', 'whatsapp.com',
                       'mozilla.org', 'w3.org', 'schema.org', 'amp.dev', 'chromium.org']
    for pattern in website_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            if not any(d in match.lower() for d in blocked_domains):
                if len(match) < 200 and '.' in match:  # Reasonable URL
                    result['website'] = match
                    break
        if 'website' in result:
            break
    
    # ── Address ──
    # Look for Barcelona street address patterns
    addr_patterns = [
        r'((?:Carrer|C/|Calle|Passeig|Rambla|Avinguda|Plaça|Ronda|Via|Gran Via|Travessera)[^"]{5,80}(?:\d{5}\s*Barcelona|\bBarcelona\b))',
        r'"((?:C/|Carrer|Calle)[^"]{5,60}\d{5}[^"]{0,20})"',
    ]
    for pattern in addr_patterns:
        matches = re.findall(pattern, html)
        if matches:
            addr = matches[0].strip()
            if len(addr) > 10:
                result['address_full'] = addr
                # Extract postal code
                postal = re.search(r'(\d{5})', addr)
                if postal:
                    result['postal_code'] = postal.group(1)
            break
    
    # ── Rating ──
    # Google Maps embeds rating as aria-label or text
    rating_patterns = [
        r'(\d\.\d)\s*(?:stars?|estrellas?|rating)',
        r'aria-label=\"(\d[\.,]\d)\s*(?:stars?|estrellas?)',
        r'\"(\d\.\d)\"[,\s]*\"(?:\d+\s*(?:reviews?|reseñas?|opiniones?))',
    ]
    for pattern in rating_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            rating = float(m.replace(',', '.'))
            if 1.0 <= rating <= 5.0:
                result['rating'] = rating
                break
        if 'rating' in result:
            break
    
    # ── Review count ──
    review_patterns = [
        r'(\d[\d,\.]*)\s*(?:reviews?|reseñas?|opiniones?)',
        r'\"(\d[\d,\.]*)\"\s*(?:reviews?|reseñas?)',
    ]
    for pattern in review_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            count = int(m.replace(',', '').replace('.', ''))
            if count > 0 and count < 1000000:
                result['review_count'] = count
                break
        if 'review_count' in result:
            break
    
    return result


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    # Target: TheFork entries specifically
    thefork = [r for r in restaurants if r.get('source') == 'thefork']
    
    # Focus on entries missing key data
    targets = [r for r in thefork if 
        not (r.get('phone') and r['phone'].strip()) or
        not (r.get('website') and r['website'].strip()) or
        not (r.get('coordinates') and r['coordinates'].get('lat')) or
        not (r.get('address_full') and r['address_full'].strip())
    ]
    
    print("=" * 65)
    print("🍴 MENUVERSO — THEFORK ENRICHMENT VIA GOOGLE MAPS")
    print("=" * 65)
    print(f"\nTotal TheFork entries: {len(thefork)}")
    print(f"Needing enrichment: {len(targets)}")
    print(f"Rate: 1 request / {DELAY}s")
    print(f"Estimated time: ~{int(len(targets) * DELAY / 60)} min\n")
    
    stats = {
        'processed': 0, 'enriched': 0, 'failed': 0,
        'coords_found': 0, 'phones_found': 0, 'websites_found': 0,
        'addresses_found': 0, 'ratings_found': 0, 'reviews_found': 0,
    }
    
    for i, r in enumerate(targets):
        rid = r.get('id', '?')
        name = r.get('name', 'Unknown')
        gmaps_url = r.get('google_maps_url', '')
        stats['processed'] += 1
        
        sys.stdout.write(f"[{i+1}/{len(targets)}] #{rid} {name[:38]:38s} → ")
        sys.stdout.flush()
        
        if not gmaps_url:
            print("⬜ no URL")
            stats['failed'] += 1
            continue
        
        html = fetch_page(gmaps_url)
        if not html:
            print("❌ fetch failed")
            stats['failed'] += 1
            time.sleep(DELAY)
            continue
        
        extracted = extract_from_gmaps_html(html, name, r.get('neighborhood', ''))
        updates = []
        
        # Apply extracted data (only if field is currently empty)
        if 'lat' in extracted and not (r.get('coordinates') and r['coordinates'].get('lat')):
            r['coordinates'] = {'lat': extracted['lat'], 'lng': extracted['lng']}
            updates.append('📍')
            stats['coords_found'] += 1
        
        if 'phone' in extracted and not (r.get('phone') and r['phone'].strip()):
            r['phone'] = extracted['phone']
            updates.append('📞')
            stats['phones_found'] += 1
        
        if 'website' in extracted and not (r.get('website') and r['website'].strip()):
            r['website'] = extracted['website']
            updates.append('🌐')
            stats['websites_found'] += 1
        
        if 'address_full' in extracted and not (r.get('address_full') and r['address_full'].strip()):
            r['address_full'] = extracted['address_full']
            if 'postal_code' in extracted and not r.get('postal_code'):
                r['postal_code'] = extracted['postal_code']
            updates.append('🏠')
            stats['addresses_found'] += 1
        
        if 'rating' in extracted and not (r.get('google_maps_rating') and float(str(r.get('google_maps_rating', 0))) > 0):
            r['google_maps_rating'] = extracted['rating']
            updates.append('⭐')
            stats['ratings_found'] += 1
        
        if 'review_count' in extracted and not (r.get('google_maps_review_count') and int(str(r.get('google_maps_review_count', 0)).replace(',', '')) > 0):
            r['google_maps_review_count'] = extracted['review_count']
            updates.append('💬')
            stats['reviews_found'] += 1
        
        if updates:
            print(f"✅ {' '.join(updates)}")
            stats['enriched'] += 1
        else:
            print("⬜ no new data")
        
        # Save every 25
        if (i + 1) % 25 == 0:
            with open(INPUT, 'w') as f:
                json.dump(restaurants, f, indent=2, ensure_ascii=False)
            print(f"\n  💾 Progress saved ({stats['enriched']}/{stats['processed']} enriched)\n")
        
        time.sleep(DELAY)
    
    # Final save
    with open(INPUT, 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    # Regenerate JS
    js_content = 'const RESTAURANT_DATA = ' + json.dumps(restaurants, indent=2, ensure_ascii=False) + ';\n'
    with open('restaurants_data.js', 'w') as f:
        f.write(js_content)
    
    print(f"\n{'=' * 65}")
    print(f"✅ THEFORK ENRICHMENT COMPLETE")
    print(f"{'=' * 65}")
    print(f"  Processed:       {stats['processed']}")
    print(f"  Enriched:        {stats['enriched']}")
    print(f"  📍 Coords found: {stats['coords_found']}")
    print(f"  📞 Phones found: {stats['phones_found']}")
    print(f"  🌐 Websites:     {stats['websites_found']}")
    print(f"  🏠 Addresses:    {stats['addresses_found']}")
    print(f"  ⭐ Ratings:      {stats['ratings_found']}")
    print(f"  💬 Reviews:      {stats['reviews_found']}")
    print(f"  ❌ Failed:       {stats['failed']}")
    
    # Show updated TheFork stats
    tf = [r for r in restaurants if r.get('source') == 'thefork']
    print(f"\n  📊 UPDATED THEFORK STATS ({len(tf)} entries):")
    print(f"     Coords:  {sum(1 for r in tf if r.get('coordinates') and r['coordinates'].get('lat'))}/{len(tf)}")
    print(f"     Phones:  {sum(1 for r in tf if r.get('phone') and r['phone'].strip())}/{len(tf)}")
    print(f"     Websites:{sum(1 for r in tf if r.get('website') and r['website'].strip())}/{len(tf)}")
    print(f"     Ratings: {sum(1 for r in tf if r.get('google_maps_rating') and float(str(r.get('google_maps_rating',0))) > 0)}/{len(tf)}")
    print(f"     Reviews: {sum(1 for r in tf if r.get('google_maps_review_count') and int(str(r.get('google_maps_review_count',0)).replace(',','')) > 0)}/{len(tf)}")
    print(f"     Address: {sum(1 for r in tf if r.get('address_full') and r['address_full'].strip())}/{len(tf)}")


if __name__ == "__main__":
    main()
