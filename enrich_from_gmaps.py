#!/usr/bin/env python3
"""
Menuverso — Google Maps Contact Enrichment Script
Extracts phone numbers, Instagram handles, and websites from Google Maps
for restaurants that are missing this data.

This script uses the browser subagent pattern — it generates a JSON batch
of Google Maps URLs to process, then the browser can be used to visit each.

For now, we use a requests-based approach to fetch Google Maps search result
pages and extract structured data from the HTML.

Usage:
    python3 enrich_from_gmaps.py                    # Process all missing
    python3 enrich_from_gmaps.py --limit 50         # First N
    python3 enrich_from_gmaps.py --start-id 100     # Start from ID
    python3 enrich_from_gmaps.py --dry-run           # Preview only
"""

import json
import re
import sys
import time
import argparse
import os
from urllib.parse import unquote

# ── Config ──────────────────────────────────────────────────────────────
INPUT = "restaurants.json"
OUTPUT_JS = "restaurants_data.js"
BATCH_SIZE = 50  # Save every N restaurants
DELAY = 1.5  # seconds between requests

try:
    import requests
except ImportError:
    sys.path.insert(0, '/tmp/pylibs')
    import requests

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}


def extract_phone_from_gmaps_html(html):
    """Extract phone number from Google Maps HTML."""
    patterns = [
        # Standard phone display patterns
        r'\"(\+34\s?\d{3}\s?\d{2,3}\s?\d{2,3}\s?\d{2,3})\"',
        r'\"(\+34\d{9})\"',
        r'(\+34[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3})',
        r'(\+34[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2})',
        r'(\+34[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})',
        # Without country code
        r'\"(9\d{2}\s?\d{2,3}\s?\d{2,3}\s?\d{2,3})\"',
        # tel: links
        r'tel:(\+?34?\d{9,12})',
        r'href=\"tel:([^\"]+)\"',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            phone = re.sub(r'[^\d+]', '', match)
            if len(phone) >= 9 and not phone.startswith('000'):
                # Normalize to +34 format
                if not phone.startswith('+'):
                    if phone.startswith('34'):
                        phone = '+' + phone
                    elif len(phone) == 9:
                        phone = '+34' + phone
                # Format nicely
                if phone.startswith('+34') and len(phone) == 12:
                    return f"+34 {phone[3:6]} {phone[6:8]} {phone[8:10]} {phone[10:12]}"
                return phone
    return None


def extract_instagram_from_gmaps_html(html):
    """Extract Instagram handle from Google Maps HTML."""
    patterns = [
        r'instagram\.com/([a-zA-Z0-9_.]{2,30})',
        r'instagr\.am/([a-zA-Z0-9_.]{2,30})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            handle = match.strip('/')
            # Skip common non-restaurant handles
            if handle.lower() in ('p', 'explore', 'accounts', 'about', 'reel', 'reels', 'stories', 'tv'):
                continue
            return f"@{handle}"
    return None


def extract_website_from_gmaps_html(html):
    """Extract website URL from Google Maps HTML."""
    # Google Maps stores website in various formats
    patterns = [
        r'"(https?://(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[^"\s]*)?)"[^"]*(?:website|sitio|web|página)',
        r'(?:website|sitio|web|página)[^"]*"(https?://(?:www\.)?[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}(?:/[^"\s]*)?)"',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            # Filter out Google/social URLs
            if any(s in match.lower() for s in ['google.com', 'facebook.com', 'instagram.com', 'twitter.com', 'tripadvisor', 'yelp.com', 'thefork.com']):
                continue
            return match
    return None


def fetch_gmaps_page(url):
    """Fetch a Google Maps page and return HTML."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        return None
    except requests.exceptions.RequestException:
        return None


def process_restaurant(r, stats):
    """Try to enrich a single restaurant from its Google Maps URL."""
    gmaps_url = r.get('google_maps_url', '')
    if not gmaps_url:
        stats['no_url'] += 1
        return False
    
    needs_phone = not r.get('phone') or not r['phone'].strip()
    needs_ig = not r.get('instagram') or not r['instagram'].strip()
    needs_website = not r.get('website') or not r['website'].strip()
    
    if not needs_phone and not needs_ig:
        stats['already_complete'] += 1
        return False
    
    html = fetch_gmaps_page(gmaps_url)
    if not html:
        stats['fetch_failed'] += 1
        return False
    
    updated = False
    
    if needs_phone:
        phone = extract_phone_from_gmaps_html(html)
        if phone:
            r['phone'] = phone
            stats['phones_found'] += 1
            updated = True
    
    if needs_ig:
        ig = extract_instagram_from_gmaps_html(html)
        if ig:
            r['instagram'] = ig
            stats['ig_found'] += 1
            updated = True
    
    if needs_website:
        website = extract_website_from_gmaps_html(html)
        if website:
            r['website'] = website
            stats['websites_found'] += 1
            updated = True
    
    if not updated:
        stats['no_data_found'] += 1
    
    return updated


def save_data(restaurants):
    """Save to both JSON and JS files."""
    with open(INPUT, 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    with open(OUTPUT_JS, 'w') as f:
        f.write('var RESTAURANT_DATA = ')
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(';\n')


def main():
    parser = argparse.ArgumentParser(description="Google Maps contact enrichment")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--limit", type=int, default=0, help="Max restaurants to process")
    parser.add_argument("--start-id", type=int, default=0, help="Start from this restaurant ID")
    parser.add_argument("--priority", action="store_true", help="Only process 4.0+ rated restaurants")
    args = parser.parse_args()
    
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    # Build target list - restaurants missing phone OR instagram
    targets = [r for r in restaurants if 
        (not r.get('phone') or not r['phone'].strip()) or
        (not r.get('instagram') or not r['instagram'].strip())
    ]
    
    if args.start_id:
        targets = [r for r in targets if r['id'] >= args.start_id]
    
    if args.priority:
        targets = [r for r in targets if r.get('google_maps_rating', 0) >= 4.0]
    
    if args.limit > 0:
        targets = targets[:args.limit]
    
    print("=" * 60)
    print("🔍 MENUVERSO — GOOGLE MAPS CONTACT ENRICHMENT")
    print("=" * 60)
    print(f"\n📊 Target: {len(targets)} restaurants to enrich")
    print(f"   Missing phones: {sum(1 for r in targets if not r.get('phone') or not r['phone'].strip())}")
    print(f"   Missing Instagram: {sum(1 for r in targets if not r.get('instagram') or not r['instagram'].strip())}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN — showing first 20 targets:")
        for r in targets[:20]:
            needs = []
            if not r.get('phone') or not r['phone'].strip():
                needs.append('📞')
            if not r.get('instagram') or not r['instagram'].strip():
                needs.append('📸')
            print(f"  [{r['id']:4d}] {r['name'][:35]:35s} needs: {' '.join(needs)}")
        return
    
    stats = {
        'processed': 0,
        'phones_found': 0,
        'ig_found': 0,
        'websites_found': 0,
        'already_complete': 0,
        'no_url': 0,
        'fetch_failed': 0,
        'no_data_found': 0,
    }
    
    for i, r in enumerate(targets):
        stats['processed'] += 1
        
        result = process_restaurant(r, stats)
        status = "✅" if result else "⬜"
        phone_str = r.get('phone', '—')[:16] if r.get('phone') else '—'
        ig_str = r.get('instagram', '') if r.get('instagram') else ''
        
        print(f"  {status} [{r['id']:4d}] {r['name'][:30]:30s} 📞 {phone_str:16s} {'📸 ' + ig_str if ig_str else ''}")
        
        # Save periodically
        if (i + 1) % BATCH_SIZE == 0:
            save_data(restaurants)
            print(f"\n  💾 Saved ({i+1}/{len(targets)}) — "
                  f"📞 {stats['phones_found']} phones, "
                  f"📸 {stats['ig_found']} IGs found\n")
        
        time.sleep(DELAY)
    
    # Final save
    save_data(restaurants)
    
    print(f"\n{'=' * 60}")
    print(f"✅ ENRICHMENT COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Processed:      {stats['processed']}")
    print(f"  📞 Phones found: {stats['phones_found']}")
    print(f"  📸 IGs found:    {stats['ig_found']}")
    print(f"  🌐 Websites:     {stats['websites_found']}")
    print(f"  ⬜ No data:      {stats['no_data_found']}")
    print(f"  ❌ Fetch failed:  {stats['fetch_failed']}")
    
    # Show new totals
    total = len(restaurants)
    has_phone = sum(1 for r in restaurants if r.get('phone') and r['phone'].strip())
    has_ig = sum(1 for r in restaurants if r.get('instagram') and r['instagram'].strip())
    print(f"\n  📊 NEW TOTALS:")
    print(f"     Phones: {has_phone}/{total} ({has_phone*100//total}%)")
    print(f"     Instagram: {has_ig}/{total} ({has_ig*100//total}%)")


if __name__ == "__main__":
    main()
