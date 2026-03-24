#!/usr/bin/env python3
"""
Menuverso — OG Image Scraper
Scrapes Open Graph images from restaurant websites.
Downloads and processes them into hero/card WebP files.

Usage:
    python3 scrape_og_images.py                    # Scrape all restaurants with websites
    python3 scrape_og_images.py --dry-run          # Show URLs only
    python3 scrape_og_images.py --ids 1,4,5        # Scrape specific IDs
    python3 scrape_og_images.py --limit 20         # Scrape first N
"""

import sys
sys.path.insert(0, '/tmp/pylibs')

import json
import os
import re
import time
import argparse
from io import BytesIO

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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
}

# Skip known bad domains
SKIP_DOMAINS = {'facebook.com', 'instagram.com', 'twitter.com', 'maps.google', 'youtube.com', 'tripadvisor'}


def extract_og_image(html, base_url=""):
    """Extract image URL from HTML — tries og:image, twitter:image, then large <img> tags."""
    # Try og:image
    patterns = [
        r'<meta\s+(?:property|name)=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']og:image["\']',
        r'<meta\s+(?:property|name)=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta\s+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']twitter:image["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = base_url.rstrip('/') + url
            return url

    # Fallback: look for large image in hero/banner/header area
    img_patterns = [
        r'<img[^>]*class=["\'][^"\']*(?:hero|banner|header|cover|main)[^"\']*["\'][^>]*src=["\']([^"\']+)["\']',
        r'<img[^>]*src=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*(?:hero|banner|header|cover|main)[^"\']*["\']',
    ]
    for pattern in img_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            url = match.group(1)
            if url.startswith('//'):
                url = 'https:' + url
            elif url.startswith('/'):
                url = base_url.rstrip('/') + url
            return url

    return None


def is_valid_image_url(url):
    """Check if URL looks like a real image (not an icon/logo)."""
    if not url:
        return False
    lower = url.lower()
    if any(skip in lower for skip in ['logo', 'favicon', 'icon', '1x1', 'pixel', 'blank', 'spacer']):
        return False
    if any(skip in lower for skip in SKIP_DOMAINS):
        return False
    return True


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


def download_and_process(image_url, restaurant_id):
    """Download image and process into hero + card WebP."""
    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None

        img = Image.open(BytesIO(resp.content))

        # Validate minimum size
        if img.size[0] < 200 or img.size[1] < 150:
            print(f"      ⚠️  Too small ({img.size[0]}×{img.size[1]})")
            return None

        # Convert to RGB
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

    except Exception as e:
        print(f"      ❌ Download error: {e}")
        return None


def scrape_restaurant(r):
    """Scrape OG image from a restaurant's website."""
    website = r.get('website', '')
    if not website:
        return None

    # Normalize URL
    if not website.startswith('http'):
        website = 'https://' + website

    rid = r['id']
    print(f"\n  [{rid}] {r['name']} — {website}")

    # Check if already scraped
    hero_path = os.path.join(PHOTOS_DIR, f"{rid}_hero.webp")
    if os.path.exists(hero_path) and os.path.getsize(hero_path) > 5000:
        print(f"      ⏭️  Already has images, skipping")
        return {"hero": f"{rid}_hero.webp", "card": f"{rid}_card.webp"}

    try:
        resp = requests.get(website, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            print(f"      ⚠️  HTTP {resp.status_code}")
            return None

        # Extract base URL for relative paths
        from urllib.parse import urlparse
        parsed = urlparse(resp.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Get OG image
        image_url = extract_og_image(resp.text, base_url)

        if not image_url or not is_valid_image_url(image_url):
            print(f"      ⚠️  No valid OG image found")
            return None

        print(f"      📷 Found: {image_url[:100]}")
        return download_and_process(image_url, rid)

    except requests.exceptions.RequestException as e:
        print(f"      ❌ Request error: {str(e)[:80]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Scrape OG images from restaurant websites")
    parser.add_argument("--dry-run", action="store_true", help="List URLs without scraping")
    parser.add_argument("--ids", type=str, default="", help="Comma-separated IDs")
    parser.add_argument("--limit", type=int, default=0, help="Process first N only")
    parser.add_argument("--update-json", action="store_true", help="Update restaurants.json with image paths")
    args = parser.parse_args()

    with open(INPUT) as f:
        restaurants = json.load(f)

    # Filter to restaurants with websites
    with_websites = [r for r in restaurants if r.get('website')]

    if args.ids:
        target_ids = set(int(x.strip()) for x in args.ids.split(","))
        with_websites = [r for r in with_websites if r['id'] in target_ids]

    if args.limit > 0:
        with_websites = with_websites[:args.limit]

    print("=" * 60)
    print("🌐 MENUVERSO OG IMAGE SCRAPER")
    print("=" * 60)
    print(f"\n📊 {len(with_websites)} restaurants with websites to scrape")
    print(f"   (out of {len(restaurants)} total)\n")

    if args.dry_run:
        for r in with_websites:
            exists = os.path.exists(os.path.join(PHOTOS_DIR, f"{r['id']}_hero.webp"))
            status = "✅" if exists else "⬜"
            print(f"  {status} [{r['id']}] {r['name']}: {r.get('website', 'N/A')}")
        print(f"\n🔍 DRY RUN — no scraping performed.")
        return

    os.makedirs(PHOTOS_DIR, exist_ok=True)

    # Scrape
    success = 0
    failed = 0
    skipped = 0

    for i, r in enumerate(with_websites):
        result = scrape_restaurant(r)
        if result:
            success += 1
        elif os.path.exists(os.path.join(PHOTOS_DIR, f"{r['id']}_hero.webp")):
            skipped += 1
        else:
            failed += 1

        # Progress every 20
        if (i + 1) % 20 == 0:
            print(f"\n  📊 Progress: {i+1}/{len(with_websites)} "
                  f"(✅ {success} | ⏭️ {skipped} | ❌ {failed})")

        time.sleep(0.5)  # Rate limiting

    print(f"\n{'=' * 60}")
    print(f"✅ Scraping complete!")
    print(f"   Successful: {success}")
    print(f"   Skipped (already had): {skipped}")
    print(f"   Failed: {failed}")
    print(f"   Total images in {PHOTOS_DIR}/: {len([f for f in os.listdir(PHOTOS_DIR) if f.endswith('.webp')])}")

    # Optionally update restaurants.json with image_url field
    if args.update_json or True:  # Always update
        update_count = 0
        for r in restaurants:
            rid = r['id']
            hero_path = f"assets/photos/{rid}_hero.webp"
            card_path = f"assets/photos/{rid}_card.webp"
            if os.path.exists(hero_path):
                r['image_url'] = hero_path
                update_count += 1
            else:
                # Fallback to cuisine stock
                cuisine = r.get('cuisine_type', 'Other')
                slug = cuisine.lower().replace("/", "_").replace(" ", "_")
                cuisine_hero = f"assets/cuisine/{slug}_hero.webp"
                if os.path.exists(cuisine_hero):
                    r['image_url'] = cuisine_hero
                    update_count += 1

        with open(INPUT, 'w') as f:
            json.dump(restaurants, f, indent=2, ensure_ascii=False)

        # Also update restaurants_data.js
        with open('restaurants_data.js', 'w') as f:
            f.write('var RESTAURANT_DATA = ')
            json.dump(restaurants, f, indent=2, ensure_ascii=False)
            f.write(';\n')

        print(f"\n   📝 Updated {update_count} restaurants with image_url in restaurants.json + restaurants_data.js")


if __name__ == "__main__":
    main()
