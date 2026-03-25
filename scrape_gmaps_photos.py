#!/usr/bin/env python3
"""
Menuverso — Google Maps Photo Scraper
Scrapes restaurant photos from Google Maps search results using requests.
Extracts photo URLs from the initial HTML response (no browser needed).

Usage:
    python3 scrape_gmaps_photos.py                    # Scrape all missing
    python3 scrape_gmaps_photos.py --limit 50         # First N missing
    python3 scrape_gmaps_photos.py --ids 44,101       # Specific IDs
    python3 scrape_gmaps_photos.py --batch 0          # Batch 0 (0-49)
    python3 scrape_gmaps_photos.py --dry-run          # Preview only
"""

import sys
sys.path.insert(0, '/tmp/pylibs')

import json
import os
import re
import time
import argparse
from io import BytesIO
from urllib.parse import urlparse, quote_plus

try:
    from PIL import Image, ImageFile
    ImageFile.LOAD_TRUNCATED_IMAGES = True
except ImportError:
    print("❌ Pillow not found. Install: pip3 install --target=/tmp/pylibs Pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ Requests not found. Install: pip3 install --target=/tmp/pylibs requests")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────
INPUT = "restaurants.json"
PHOTOS_DIR = "assets/photos"
HERO_SIZE = (1200, 600)
CARD_SIZE = (400, 300)
BATCH_SIZE = 50

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Referer': 'https://www.google.com/',
}


def smart_crop_resize(img, target_size):
    """Center-crop and resize to target dimensions."""
    target_w, target_h = target_size
    target_ratio = target_w / target_h
    img_w, img_h = img.size
    img_ratio = img_w / img_h

    if img_ratio > target_ratio:
        new_w = int(img_h * target_ratio)
        left = (img_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, img_h))
    else:
        new_h = int(img_w / target_ratio)
        top = max(0, (img_h - new_h) // 4)
        img = img.crop((0, top, img_w, top + new_h))

    return img.resize(target_size, Image.LANCZOS)


def save_hero_card(img, restaurant_id):
    """Save image as hero + card WebP."""
    if img.mode in ('RGBA', 'P', 'LA'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    results = {}
    for label, size in [("hero", HERO_SIZE), ("card", CARD_SIZE)]:
        out_name = f"{restaurant_id}_{label}.webp"
        out_path = os.path.join(PHOTOS_DIR, out_name)
        cropped = smart_crop_resize(img.copy(), size)
        cropped.save(out_path, 'WEBP', quality=85, method=6)
        fsize = os.path.getsize(out_path)
        results[label] = out_name
        print(f"      ✅ {out_name} ({size[0]}×{size[1]}, {fsize:,}b)")
    return results


def extract_photo_urls_from_gmaps(html_text):
    """Extract photo URLs from Google Maps HTML response."""
    urls = []
    
    # Pattern 1: Look for lh3.googleusercontent.com URLs (Google's image CDN)
    patterns = [
        r'(https://lh[0-9]*\.googleusercontent\.com/[^\s"\'\\]+)',
        r'(https://streetviewpixels[^\s"\'\\]+)',
        r'(https://maps\.googleapis\.com/maps/api/place/photo[^\s"\'\\]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html_text)
        for url in matches:
            # Clean up escaped characters
            url = url.replace('\\u003d', '=').replace('\\u0026', '&')
            url = url.rstrip('\\')
            # Filter: require reasonable size params or no size restriction
            if 'lh' in url and 'googleusercontent' in url:
                # Make sure it's a place photo, not a tiny UI element
                if len(url) > 60:  # Place photos have longer URLs
                    urls.append(url)
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for url in urls:
        # Normalize by stripping size params for dedup
        base = url.split('=')[0] if '=' in url else url
        if base not in seen:
            seen.add(base)
            unique.append(url)
    
    return unique


def request_large_version(url):
    """Convert a Google photo URL to request a large version."""
    # Remove existing size constraints and request a large version
    # lh3 URLs often end with =s<size> or =w<w>-h<h>
    clean = re.sub(r'=s\d+', '=s1200', url)
    clean = re.sub(r'=w\d+-h\d+', '=w1200-h800', clean)
    if '=' not in clean:
        clean += '=s1200'
    elif not re.search(r'=[swh]', clean):
        clean = clean.rstrip('=') + '=s1200'
    return clean


def scrape_gmaps(r):
    """Scrape a photo from Google Maps for a restaurant."""
    rid = r['id']
    name = r.get('name', 'Unknown')
    maps_url = r.get('google_maps_url', '')
    
    if not maps_url:
        return None
    
    hero_path = os.path.join(PHOTOS_DIR, f"{rid}_hero.webp")
    if os.path.exists(hero_path) and os.path.getsize(hero_path) > 5000:
        return {"hero": f"{rid}_hero.webp", "card": f"{rid}_card.webp"}
    
    print(f"\n  [{rid}] {name}")
    
    try:
        # Request Google Maps page
        resp = requests.get(maps_url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            print(f"      ⚠️  HTTP {resp.status_code}")
            return None
        
        # Extract photo URLs
        photo_urls = extract_photo_urls_from_gmaps(resp.text)
        print(f"      🔍 Found {len(photo_urls)} candidate photo URLs")
        
        if not photo_urls:
            return None
        
        # Try the first few photos until one works
        for i, url in enumerate(photo_urls[:5]):
            try:
                large_url = request_large_version(url)
                img_resp = requests.get(large_url, headers=HEADERS, timeout=10)
                if img_resp.status_code != 200:
                    continue
                
                img = Image.open(BytesIO(img_resp.content))
                
                # Must be at least 300x200 to be useful
                if img.size[0] < 300 or img.size[1] < 200:
                    continue
                
                print(f"      📷 Photo #{i+1}: {img.size[0]}×{img.size[1]}")
                return save_hero_card(img, rid)
                
            except Exception as e:
                continue
        
        print(f"      ⚠️  No usable photos found")
        return None
        
    except Exception as e:
        print(f"      ❌ Error: {str(e)[:80]}")
        return None


def get_completeness(r):
    """Score how complete a restaurant profile is (for prioritization)."""
    score = 0
    if r.get('name'): score += 10
    if r.get('google_maps_rating'): score += 15
    if r.get('google_maps_review_count', 0) > 50: score += 10
    if r.get('website'): score += 15
    if r.get('phone'): score += 10
    if r.get('instagram'): score += 5
    if r.get('address_full'): score += 10
    if r.get('menu_price_range'): score += 10
    if r.get('notes') and len(r.get('notes', '')) > 20: score += 5
    if r.get('metro_station'): score += 5
    coords = r.get('coordinates', {})
    if coords.get('lat') and str(coords['lat']).replace('.', '').replace('-', '').isdigit():
        lat_str = str(coords['lat']).split('.')[1] if '.' in str(coords['lat']) else ''
        if len(lat_str) >= 5:
            score += 5
    return score


def main():
    parser = argparse.ArgumentParser(description="Scrape photos from Google Maps")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ids", type=str, default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch", type=int, default=-1, help="Batch number (each batch = 50)")
    args = parser.parse_args()

    with open(INPUT) as f:
        restaurants = json.load(f)

    # Filter to restaurants missing photos
    missing = [r for r in restaurants if not os.path.exists(
        os.path.join(PHOTOS_DIR, f"{r['id']}_hero.webp")
    )]
    
    # Sort by completeness (most complete first)
    missing.sort(key=lambda r: get_completeness(r), reverse=True)

    if args.ids:
        target_ids = set(int(x.strip()) for x in args.ids.split(","))
        missing = [r for r in missing if r['id'] in target_ids]

    if args.batch >= 0:
        start = args.batch * BATCH_SIZE
        end = start + BATCH_SIZE
        missing = missing[start:end]

    if args.limit > 0:
        missing = missing[:args.limit]

    print("=" * 60)
    print("📍 MENUVERSO GOOGLE MAPS PHOTO SCRAPER")
    print("=" * 60)
    print(f"\n📊 {len(missing)} restaurants to scrape")
    print(f"   (out of {len(restaurants)} total)\n")

    if args.dry_run:
        for r in missing:
            print(f"  ⬜ [{r['id']}] {r['name']} (score: {get_completeness(r)})")
            print(f"     {r.get('google_maps_url', 'N/A')[:80]}")
        return

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    success = 0
    failed = 0

    for i, r in enumerate(missing):
        result = scrape_gmaps(r)
        if result:
            success += 1
        else:
            failed += 1

        if (i + 1) % 10 == 0:
            print(f"\n  📊 Progress: {i+1}/{len(missing)} "
                  f"(✅ {success} | ❌ {failed})")

        time.sleep(1.0)  # Rate limiting for Google

    print(f"\n{'=' * 60}")
    print(f"✅ Google Maps scraping complete!")
    print(f"   New images: {success}")
    print(f"   Failed: {failed}")
    total_photos = len([f for f in os.listdir(PHOTOS_DIR) if f.endswith('_hero.webp')])
    print(f"   Total photos now: {total_photos}")

    # Update JSON
    update_count = 0
    for r in restaurants:
        hero_path = f"assets/photos/{r['id']}_hero.webp"
        if os.path.exists(hero_path) and os.path.getsize(hero_path) > 1000:
            if not r.get('image_url'):
                r['image_url'] = hero_path
                update_count += 1

    with open(INPUT, 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    with open('restaurants_data.js', 'w') as f:
        f.write('var RESTAURANT_DATA = ')
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(';\n')

    print(f"   📝 Updated {update_count} entries in restaurants.json + restaurants_data.js")


if __name__ == "__main__":
    main()
