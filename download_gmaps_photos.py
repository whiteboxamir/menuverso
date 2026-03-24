#!/usr/bin/env python3
"""
Menuverso — Google Maps Photo URL Downloader
Downloads restaurant photos from Google Maps CDN URLs.
Reads a JSON file of URLs produced by the browser scraper.

Usage:
    python3 download_gmaps_photos.py urls.json
"""

import sys
sys.path.insert(0, '/tmp/pylibs')

import json
import os
from io import BytesIO
import requests
from PIL import Image

PHOTOS_DIR = "assets/photos"
HERO_SIZE = (1200, 600)
CARD_SIZE = (400, 300)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'image/webp,image/*,*/*;q=0.8',
}


def smart_crop_resize(img, target_size):
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


def download_and_save(url, rid):
    """Download a Google Maps photo URL and save as hero+card."""
    try:
        # Request high-res version
        hi_res_url = url.split('=')[0] + '=w1200-h800-k-no'
        resp = requests.get(hi_res_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return False

        img = Image.open(BytesIO(resp.content))
        if img.size[0] < 200 or img.size[1] < 150:
            return False

        if img.mode in ('RGBA', 'P', 'LA'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        for label, size in [("hero", HERO_SIZE), ("card", CARD_SIZE)]:
            out_path = os.path.join(PHOTOS_DIR, f"{rid}_{label}.webp")
            cropped = smart_crop_resize(img.copy(), size)
            cropped.save(out_path, 'WEBP', quality=85, method=6)

        fsize = os.path.getsize(os.path.join(PHOTOS_DIR, f"{rid}_hero.webp"))
        print(f"  ✅ [{rid}] Downloaded ({img.size[0]}×{img.size[1]}) → hero {fsize:,}b")
        return True
    except Exception as e:
        print(f"  ❌ [{rid}] Error: {str(e)[:60]}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 download_gmaps_photos.py urls.json")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        url_data = json.load(f)

    os.makedirs(PHOTOS_DIR, exist_ok=True)
    success = 0
    for rid_str, url in url_data.items():
        rid = int(rid_str)
        hero_path = os.path.join(PHOTOS_DIR, f"{rid}_hero.webp")
        if os.path.exists(hero_path) and os.path.getsize(hero_path) > 5000:
            continue
        if download_and_save(url, rid):
            success += 1

    print(f"\nDownloaded {success} new photos")

    # Update restaurants.json
    with open('restaurants.json') as f:
        restaurants = json.load(f)
    updated = 0
    for r in restaurants:
        hero = f"assets/photos/{r['id']}_hero.webp"
        if os.path.exists(hero) and os.path.getsize(hero) > 3000 and not r.get('image_url'):
            r['image_url'] = hero
            updated += 1
    with open('restaurants.json', 'w') as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    with open('restaurants_data.js', 'w') as f:
        f.write('var RESTAURANT_DATA = ')
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(';\n')
    print(f"Updated {updated} restaurants in JSON")


if __name__ == "__main__":
    main()
