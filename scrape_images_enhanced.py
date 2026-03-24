#!/usr/bin/env python3
"""
Menuverso — Enhanced Image Scraper (No API Key Required)
Aggressively scrapes restaurant images from multiple sources:
1. OG/Twitter meta images (existing)
2. ALL img tags — picks the largest one
3. CSS background-image URLs
4. JSON-LD schema images
5. Favicon/apple-touch-icon as last resort (skipped - too small)

Usage:
    python3 scrape_images_enhanced.py                  # Scrape all missing
    python3 scrape_images_enhanced.py --ids 3,4,5      # Specific IDs
    python3 scrape_images_enhanced.py --limit 20       # First N
    python3 scrape_images_enhanced.py --dry-run        # Preview only
"""

import sys
sys.path.insert(0, '/tmp/pylibs')

import json
import os
import re
import time
import argparse
from io import BytesIO
from urllib.parse import urlparse, urljoin

try:
    from PIL import Image
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
MIN_IMG_WIDTH = 400
MIN_IMG_HEIGHT = 250

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

SKIP_TERMS = ['logo', 'favicon', 'icon', '1x1', 'pixel', 'blank', 'spacer',
              'avatar', 'sprite', 'button', 'arrow', 'loading', 'spinner',
              'badge', 'map', 'marker', 'pin', 'social', 'share', 'email',
              'facebook', 'instagram', 'twitter', 'youtube', 'tripadvisor',
              'google', 'analytics', 'tracking', 'pixel', 'banner-cookie']


def normalize_url(url, base_url):
    """Make a URL absolute."""
    if not url:
        return None
    url = url.strip()
    if url.startswith('data:'):
        return None
    if url.startswith('//'):
        url = 'https:' + url
    elif url.startswith('/'):
        url = base_url.rstrip('/') + url
    elif not url.startswith('http'):
        url = base_url.rstrip('/') + '/' + url
    return url


def is_valid_image_url(url):
    """Filter out icons, logos, and tracking pixels."""
    if not url:
        return False
    lower = url.lower()
    return not any(skip in lower for skip in SKIP_TERMS)


def extract_all_images(html, base_url):
    """Extract ALL candidate image URLs from HTML, ranked by likelihood of being a hero image."""
    candidates = []

    # 1. OG / Twitter meta images (highest priority)
    og_patterns = [
        r'<meta\s+(?:property|name)=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']og:image["\']',
        r'<meta\s+(?:property|name)=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']twitter:image["\']',
    ]
    for pattern in og_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            url = normalize_url(match.group(1), base_url)
            if url and is_valid_image_url(url):
                candidates.append(('og', url))

    # 2. JSON-LD schema.org image
    jsonld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    for match in re.finditer(jsonld_pattern, html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                data = data[0] if data else {}
            img = data.get('image')
            if isinstance(img, str):
                url = normalize_url(img, base_url)
                if url and is_valid_image_url(url):
                    candidates.append(('jsonld', url))
            elif isinstance(img, list) and img:
                url = normalize_url(img[0] if isinstance(img[0], str) else img[0].get('url', ''), base_url)
                if url and is_valid_image_url(url):
                    candidates.append(('jsonld', url))
            elif isinstance(img, dict):
                url = normalize_url(img.get('url', ''), base_url)
                if url and is_valid_image_url(url):
                    candidates.append(('jsonld', url))
        except (json.JSONDecodeError, AttributeError, IndexError):
            pass

    # 3. Hero/banner/header images (class-based)
    hero_patterns = [
        r'<img[^>]*class=["\'][^"\']*(?:hero|banner|header|cover|main|featured|full)[^"\']*["\'][^>]*src=["\']([^"\']+)["\']',
        r'<img[^>]*src=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*(?:hero|banner|header|cover|main|featured|full)[^"\']*["\']',
    ]
    for pattern in hero_patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = normalize_url(match.group(1), base_url)
            if url and is_valid_image_url(url):
                candidates.append(('hero_class', url))

    # 4. CSS background images in hero/header sections
    bg_patterns = [
        r'(?:hero|banner|header|cover|parallax)[^{]*\{[^}]*background(?:-image)?:\s*url\(["\']?([^"\')\s]+)["\']?\)',
        r'style=["\'][^"\']*background(?:-image)?:\s*url\(["\']?([^"\')\s]+)["\']?\)[^"\']*["\']',
    ]
    for pattern in bg_patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = normalize_url(match.group(1), base_url)
            if url and is_valid_image_url(url):
                candidates.append(('css_bg', url))

    # 5. Large data-src/data-lazy images (lazy loaded)
    lazy_patterns = [
        r'<img[^>]*(?:data-src|data-lazy|data-original)=["\']([^"\']+)["\']',
        r'<source[^>]*srcset=["\']([^\s"\']+)',
    ]
    for pattern in lazy_patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            url = normalize_url(match.group(1), base_url)
            if url and is_valid_image_url(url):
                candidates.append(('lazy', url))

    # 6. All remaining img tags (lowest priority)
    all_imgs = re.findall(r'<img[^>]*src=["\']([^"\']+)["\']', html, re.IGNORECASE)
    for img_url in all_imgs:
        url = normalize_url(img_url, base_url)
        if url and is_valid_image_url(url):
            # Skip tiny known extensions
            if not any(ext in url.lower() for ext in ['.svg', '.gif', '.ico']):
                candidates.append(('img_tag', url))

    return candidates


def download_and_validate(url, min_width=MIN_IMG_WIDTH, min_height=MIN_IMG_HEIGHT):
    """Download image and check if it meets minimum size requirements."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True, stream=True)
        if resp.status_code != 200:
            return None

        # Check content type
        ct = resp.headers.get('content-type', '').lower()
        if not any(t in ct for t in ['image/', 'octet-stream']):
            return None

        # Read content (limit to 5MB)
        content = resp.content[:5 * 1024 * 1024]
        img = Image.open(BytesIO(content))

        if img.size[0] < min_width or img.size[1] < min_height:
            return None

        return img
    except Exception:
        return None


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


def scrape_restaurant(r):
    """Try all strategies to find an image for a restaurant."""
    website = r.get('website', '')
    if not website:
        return None

    if not website.startswith('http'):
        website = 'https://' + website

    rid = r['id']
    hero_path = os.path.join(PHOTOS_DIR, f"{rid}_hero.webp")
    if os.path.exists(hero_path) and os.path.getsize(hero_path) > 5000:
        return {"hero": f"{rid}_hero.webp", "card": f"{rid}_card.webp"}

    print(f"\n  [{rid}] {r['name']} — {website}")

    try:
        resp = requests.get(website, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            print(f"      ⚠️  HTTP {resp.status_code}")
            return None

        parsed = urlparse(resp.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        candidates = extract_all_images(resp.text, base_url)
        print(f"      🔍 Found {len(candidates)} candidate images")

        # Try candidates in priority order
        seen = set()
        for source, url in candidates:
            if url in seen:
                continue
            seen.add(url)

            img = download_and_validate(url)
            if img:
                print(f"      📷 [{source}] {url[:80]} ({img.size[0]}×{img.size[1]})")
                return save_hero_card(img, rid)

        print(f"      ⚠️  No valid images found after trying {len(seen)} URLs")
        return None

    except requests.exceptions.RequestException as e:
        print(f"      ❌ Request error: {str(e)[:80]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Enhanced image scraper")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ids", type=str, default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    with open(INPUT) as f:
        restaurants = json.load(f)

    # Only process restaurants that are missing AND have websites
    targets = [r for r in restaurants if r.get('website') and not r.get('image_url')]

    if args.ids:
        target_ids = set(int(x.strip()) for x in args.ids.split(","))
        targets = [r for r in targets if r['id'] in target_ids]

    if args.limit > 0:
        targets = targets[:args.limit]

    print("=" * 60)
    print("🔍 MENUVERSO ENHANCED IMAGE SCRAPER")
    print("=" * 60)
    print(f"\n📊 {len(targets)} restaurants to scrape (missing photos + have website)\n")

    if args.dry_run:
        for r in targets:
            print(f"  ⬜ [{r['id']}] {r['name']}: {r.get('website', 'N/A')}")
        return

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    success = 0
    failed = 0
    skipped = 0

    for i, r in enumerate(targets):
        result = scrape_restaurant(r)
        if result:
            success += 1
        elif os.path.exists(os.path.join(PHOTOS_DIR, f"{r['id']}_hero.webp")):
            skipped += 1
        else:
            failed += 1

        if (i + 1) % 20 == 0:
            print(f"\n  📊 Progress: {i+1}/{len(targets)} "
                  f"(✅ {success} | ⏭️ {skipped} | ❌ {failed})")

        time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print(f"✅ Enhanced scraping complete!")
    print(f"   New images: {success}")
    print(f"   Failed: {failed}")
    print(f"   Total photos: {len([f for f in os.listdir(PHOTOS_DIR) if f.endswith('_hero.webp')])}")

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

    print(f"   📝 Updated {update_count} new entries in restaurants.json")


if __name__ == "__main__":
    main()
