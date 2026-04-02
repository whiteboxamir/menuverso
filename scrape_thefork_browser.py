#!/usr/bin/env python3
"""
Menuverso — TheFork Google Maps Browser Scraper
Uses Playwright (headless Chromium) to render Google Maps search pages
and extract structured data (coords, rating, reviews, phone, website, address).

This solves the "Google Maps requires JavaScript" blocker.
"""

import sys
sys.path.insert(0, '/tmp/pylibs')

import json
import re
import time

INPUT = "restaurants.json"

JS_EXTRACT = """
() => {
    var result = {};
    var text = document.body.innerText || '';
    
    // Rating: look for pattern like "4.8(10,065)"  or "4.8 stars"
    var ratingMatch = text.match(/(\\d\\.\\d)\\s*(?:\\(|stars|estrellas)/i);
    if (ratingMatch) result.rating = parseFloat(ratingMatch[1]);
    
    // Review count from various patterns
    var reviewPatterns = [
        /(\\d[\\d,\\.]+)\\s*(?:reviews?|reseñas?|opiniones?|Google reviews)/i,
        /\\((\\d[\\d,\\.]+)\\)/,
    ];
    for (var p of reviewPatterns) {
        var m = text.match(p);
        if (m) {
            var count = parseInt(m[1].replace(/[,\\.]/g, ''));
            if (count > 0 && count < 500000) {
                result.reviews = count;
                break;
            }
        }
    }
    
    // Coordinates from URL
    var url = window.location.href;
    var coordMatch = url.match(/@(-?\\d+\\.\\d+),(-?\\d+\\.\\d+)/);
    if (coordMatch) {
        result.lat = parseFloat(coordMatch[1]);
        result.lng = parseFloat(coordMatch[2]);
    }
    // Also from data params 
    var dataMatch = url.match(/!3d(-?\\d+\\.\\d+)!4d(-?\\d+\\.\\d+)/);
    if (dataMatch && !result.lat) {
        result.lat = parseFloat(dataMatch[1]);
        result.lng = parseFloat(dataMatch[2]);
    }
    
    // Phone - look for +34 patterns or tel: links
    var phoneEls = document.querySelectorAll('[data-item-id*="phone"], [data-tooltip*="phone"], [data-tooltip*="teléfono"], a[href^="tel:"]');
    for (var el of phoneEls) {
        var ph = (el.getAttribute('href') || el.textContent || '').replace('tel:', '').trim();
        if (ph && ph.match(/\\d{6,}/)) {
            result.phone = ph;
            break;
        }
    }
    // Fallback: regex on text
    if (!result.phone) {
        var phoneMatch = text.match(/(\\+34[\\s\\-]?\\d{3}[\\s\\-]?\\d{2,3}[\\s\\-]?\\d{2,3}[\\s\\-]?\\d{2,3})/);
        if (phoneMatch) result.phone = phoneMatch[1];
        else {
            phoneMatch = text.match(/(9\\d{2}[\\s\\-]?\\d{2,3}[\\s\\-]?\\d{2,3}[\\s\\-]?\\d{2,3})/);
            if (phoneMatch) result.phone = phoneMatch[1];
        }
    }
    
    // Website
    var webEls = document.querySelectorAll('[data-item-id="authority"], a[data-item-id="authority"]');
    for (var el of webEls) {
        var href = el.getAttribute('href') || el.textContent || '';
        if (href && !href.includes('google.com')) {
            result.website = href;
            break;
        }
    }
    
    // Address
    var addrEls = document.querySelectorAll('[data-item-id="address"], button[data-item-id="address"]');
    for (var el of addrEls) {
        var addr = el.textContent.trim();
        if (addr && addr.length > 5) {
            result.address = addr;
            break;
        }
    }
    // Fallback: look for Barcelona address in text
    if (!result.address) {
        var addrMatch = text.match(/((?:Carrer|C\\/|Calle|Passeig|Rambla|Av\\.|Plaça|Ronda)[^\\n]{5,60}(?:\\d{5})?)/);
        if (addrMatch) result.address = addrMatch[1].trim();
    }
    
    // Opening hours
    var hoursEls = document.querySelectorAll('[aria-label*="hour"], [aria-label*="hora"]');
    if (hoursEls.length > 0) {
        result.has_hours = true;
    }
    
    return JSON.stringify(result);
}
"""


def normalize_phone(phone):
    """Normalize phone number to +34 XXX XX XX XX format."""
    digits = re.sub(r'[^\d+]', '', phone)
    if not digits.startswith('+'):
        if digits.startswith('34'):
            digits = '+' + digits
        elif len(digits) == 9:
            digits = '+34' + digits
    if digits.startswith('+34') and len(digits) == 12:
        return f"+34 {digits[3:6]} {digits[6:8]} {digits[8:10]} {digits[10:12]}"
    return phone


def main():
    from playwright.sync_api import sync_playwright
    
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    # Build lookup for fast ID access
    by_id = {r['id']: r for r in restaurants}
    
    # Target all TheFork entries that need ANY enrichment
    tf = [r for r in restaurants if r.get('source') == 'thefork']
    targets = [r for r in tf if 
        not (r.get('coordinates') and r['coordinates'].get('lat')) or
        not (r.get('google_maps_rating') and float(str(r.get('google_maps_rating', 0))) > 0) or
        not (r.get('phone') and r['phone'].strip())
    ]
    
    print("=" * 65)
    print("🍴 THEFORK BROWSER ENRICHMENT via Playwright + Chromium")
    print("=" * 65)
    print(f"\nTargets: {len(targets)} TheFork entries")
    print(f"Headless Chromium — ~8s per entry ≈ {len(targets)*8//60} min\n")
    
    stats = {
        'processed': 0, 'enriched': 0, 'failed': 0,
        'coords': 0, 'rating': 0, 'reviews': 0,
        'phone': 0, 'website': 0, 'address': 0,
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='en-US',
        )
        page = context.new_page()
        
        for i, r in enumerate(targets):
            rid = r['id']
            name = r['name']
            url = r.get('google_maps_url', '')
            stats['processed'] += 1
            
            sys.stdout.write(f"[{i+1}/{len(targets)}] #{rid} {name[:38]:38s} → ")
            sys.stdout.flush()
            
            if not url:
                print("⬜ no URL")
                stats['failed'] += 1
                continue
            
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=15000)
                # Wait for Maps to render
                page.wait_for_timeout(4000)
                
                # Try clicking on the first result if it's a search results page
                try:
                    first_result = page.locator('a[data-cid]').first
                    if first_result.is_visible(timeout=2000):
                        first_result.click()
                        page.wait_for_timeout(3000)
                except:
                    pass
                
                # Extract data
                raw = page.evaluate(JS_EXTRACT)
                extracted = json.loads(raw)
                
                updates = []
                
                # Apply coordinates
                if extracted.get('lat') and not (r.get('coordinates') and r['coordinates'].get('lat')):
                    lat, lng = extracted['lat'], extracted['lng']
                    if 41.3 <= lat <= 41.5 and 2.0 <= lng <= 2.3:
                        r['coordinates'] = {'lat': lat, 'lng': lng}
                        updates.append('📍')
                        stats['coords'] += 1
                
                # Apply rating
                if extracted.get('rating') and not (r.get('google_maps_rating') and float(str(r.get('google_maps_rating', 0))) > 0):
                    if 1.0 <= extracted['rating'] <= 5.0:
                        r['google_maps_rating'] = extracted['rating']
                        updates.append('⭐')
                        stats['rating'] += 1
                
                # Apply reviews
                if extracted.get('reviews') and not (r.get('google_maps_review_count') and int(str(r.get('google_maps_review_count', 0)).replace(',', '')) > 0):
                    r['google_maps_review_count'] = extracted['reviews']
                    updates.append('💬')
                    stats['reviews'] += 1
                
                # Apply phone
                if extracted.get('phone') and not (r.get('phone') and r['phone'].strip()):
                    r['phone'] = normalize_phone(extracted['phone'])
                    updates.append('📞')
                    stats['phone'] += 1
                
                # Apply website
                if extracted.get('website') and not (r.get('website') and r['website'].strip()):
                    if 'google' not in extracted['website'].lower():
                        r['website'] = extracted['website']
                        updates.append('🌐')
                        stats['website'] += 1
                
                # Apply address
                if extracted.get('address') and not (r.get('address_full') and r['address_full'].strip()):
                    r['address_full'] = extracted['address']
                    updates.append('🏠')
                    stats['address'] += 1
                
                if updates:
                    print(f"✅ {' '.join(updates)}")
                    stats['enriched'] += 1
                else:
                    print("⬜ no new data found")
                    
            except Exception as e:
                print(f"❌ {str(e)[:50]}")
                stats['failed'] += 1
            
            # Save every 20
            if (i + 1) % 20 == 0:
                with open(INPUT, 'w') as f:
                    json.dump(restaurants, f, indent=2, ensure_ascii=False)
                print(f"\n  💾 Progress saved ({stats['enriched']}/{stats['processed']} enriched)\n")
        
        browser.close()
    
    # Final save
    with open(INPUT, 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    # Regenerate JS
    js_content = 'var RESTAURANT_DATA = ' + json.dumps(restaurants, indent=2, ensure_ascii=False) + ';\n'
    with open('restaurants_data.js', 'w') as f:
        f.write(js_content)
    
    print(f"\n{'=' * 65}")
    print(f"✅ BROWSER ENRICHMENT COMPLETE")
    print(f"{'=' * 65}")
    print(f"  Processed: {stats['processed']}")
    print(f"  Enriched:  {stats['enriched']}")
    print(f"  📍 Coords: {stats['coords']}")
    print(f"  ⭐ Ratings: {stats['rating']}")
    print(f"  💬 Reviews: {stats['reviews']}")
    print(f"  📞 Phones: {stats['phone']}")
    print(f"  🌐 Websites: {stats['website']}")
    print(f"  🏠 Addresses: {stats['address']}")
    print(f"  ❌ Failed:  {stats['failed']}")
    
    # Final DB stats
    total = len(restaurants)
    has_coords = sum(1 for r in restaurants if r.get('coordinates') and r['coordinates'].get('lat'))
    has_rating = sum(1 for r in restaurants if r.get('google_maps_rating') and float(str(r.get('google_maps_rating', 0))) > 0)
    has_phone = sum(1 for r in restaurants if r.get('phone') and r['phone'].strip())
    print(f"\n  📊 TOTAL DB STATS:")
    print(f"     Coords:  {has_coords}/{total} ({has_coords/total*100:.1f}%)")
    print(f"     Ratings: {has_rating}/{total} ({has_rating/total*100:.1f}%)")
    print(f"     Phones:  {has_phone}/{total} ({has_phone/total*100:.1f}%)")


if __name__ == "__main__":
    main()
