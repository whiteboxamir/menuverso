#!/usr/bin/env python3
"""
Menuverso — Restaurant Image Pipeline
Downloads cuisine-based stock photos from Unsplash Source API,
then processes them into hero (1200×600) and card (400×300) WebP images.

Usage:
    python3 fetch_restaurant_photos.py                  # Download + process all cuisines
    python3 fetch_restaurant_photos.py --dry-run        # Show cuisine mapping only
    python3 fetch_restaurant_photos.py --process-only   # Skip download, just re-process existing
"""

import sys
sys.path.insert(0, '/tmp/pylibs')

import json
import os
import argparse
import time

try:
    from PIL import Image
except ImportError:
    print("❌ Pillow not found. Install with: pip3 install --target=/tmp/pylibs Pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ Requests not found. Install with: pip3 install --target=/tmp/pylibs requests")
    sys.exit(1)


# ── Configuration ────────────────────────────────────────────────────────────

INPUT = "restaurants.json"
OUTPUT_DIR = "assets/cuisine"
RAW_DIR = "/tmp/cuisine_photos_raw"

HERO_SIZE = (1200, 600)
CARD_SIZE = (400, 300)

# Cuisine → Unsplash search terms (optimized for appetizing food photos)
CUISINE_SEARCH = {
    "Spanish":           "spanish tapas paella food",
    "Mediterranean":     "mediterranean food plate",
    "Catalan":           "catalan cuisine food",
    "Seafood":           "seafood platter restaurant",
    "Café":              "coffee cafe latte pastry",
    "Italian":           "italian pasta food restaurant",
    "Japanese":          "sushi japanese food",
    "Vegetarian/Vegan":  "vegan food bowl colorful",
    "Fusion":            "fusion cuisine plating",
    "Asian":             "asian noodles food",
    "Mexican":           "mexican tacos food",
    "Indian":            "indian curry food",
    "Gastropub":         "gastropub burger craft food",
    "Middle Eastern":    "falafel hummus food",
    "Basque":            "basque pintxos food",
    "French":            "french cuisine bistro food",
    "Argentine":         "argentine steak asado food",
    "Peruvian":          "peruvian ceviche food",
    "Chinese":           "chinese dumplings food",
    "Greek":             "greek food plate",
    "Lebanese":          "lebanese mezze food",
    "Thai":              "thai pad thai food",
    "Turkish":           "turkish kebab food",
    "Korean":            "korean bibimbap food",
    "Colombian":         "colombian food bandeja",
    "Cuban":             "cuban food restaurant",
    "Ethiopian":         "ethiopian injera food",
    "Other":             "restaurant food plate",
}


def smart_crop_resize(img, target_size):
    """Center-crop and resize to exact target dimensions."""
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
        top = max(0, (img_h - new_h) // 4)  # Favor upper portion
        img = img.crop((0, top, img_w, top + new_h))

    return img.resize(target_size, Image.LANCZOS)


def download_cuisine_photo(cuisine, search_term, raw_dir):
    """Download a photo from Unsplash Source API for a cuisine."""
    slug = cuisine.lower().replace("/", "_").replace(" ", "_")
    raw_path = os.path.join(raw_dir, f"{slug}.jpg")

    if os.path.exists(raw_path):
        size = os.path.getsize(raw_path)
        if size > 10000:  # Skip if already downloaded and valid
            print(f"  ⏭️  {cuisine} — already downloaded ({size:,} bytes)")
            return raw_path

    # Unsplash Source API — free, no key needed
    url = f"https://source.unsplash.com/1600x900/?{requests.utils.quote(search_term)}"

    print(f"  📥 Downloading {cuisine} → {search_term}")
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 200 and len(resp.content) > 5000:
            with open(raw_path, "wb") as f:
                f.write(resp.content)
            print(f"      ✅ Saved {len(resp.content):,} bytes → {raw_path}")
            return raw_path
        else:
            print(f"      ⚠️  Got {resp.status_code}, content size: {len(resp.content)} bytes")
            # Try alternative: picsum for generic food
            alt_url = f"https://picsum.photos/1600/900"
            resp2 = requests.get(alt_url, timeout=15, allow_redirects=True)
            if resp2.status_code == 200 and len(resp2.content) > 5000:
                with open(raw_path, "wb") as f:
                    f.write(resp2.content)
                print(f"      ✅ Fallback saved {len(resp2.content):,} bytes")
                return raw_path
    except requests.exceptions.RequestException as e:
        print(f"      ❌ Download failed: {e}")

    return None


def process_raw_to_webp(raw_path, cuisine, output_dir):
    """Process a raw downloaded image into hero + card WebP variants."""
    slug = cuisine.lower().replace("/", "_").replace(" ", "_")
    results = {}

    try:
        img = Image.open(raw_path)
        if img.mode in ('RGBA', 'P', 'LA'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        for label, size in [("hero", HERO_SIZE), ("card", CARD_SIZE)]:
            out_name = f"{slug}_{label}.webp"
            out_path = os.path.join(output_dir, out_name)
            cropped = smart_crop_resize(img.copy(), size)
            cropped.save(out_path, 'WEBP', quality=85, method=6)
            fsize = os.path.getsize(out_path)
            print(f"      ✅ {out_name} ({size[0]}×{size[1]}, {fsize:,} bytes)")
            results[label] = out_name

    except Exception as e:
        print(f"      ❌ Processing error: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Menuverso Image Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Show cuisine mapping only")
    parser.add_argument("--process-only", action="store_true", help="Skip downloads, re-process existing")
    args = parser.parse_args()

    # Load restaurants to get cuisine list
    with open(INPUT) as f:
        restaurants = json.load(f)

    # Get actual cuisines from data
    cuisines_in_data = sorted(set(r.get("cuisine_type", "Other") for r in restaurants))
    cuisine_counts = {}
    for r in restaurants:
        c = r.get("cuisine_type", "Other")
        cuisine_counts[c] = cuisine_counts.get(c, 0) + 1

    print("=" * 60)
    print("🖼️  MENUVERSO IMAGE PIPELINE")
    print("=" * 60)
    print(f"\n📊 {len(restaurants)} restaurants across {len(cuisines_in_data)} cuisine types\n")

    # Show mapping
    for cuisine in cuisines_in_data:
        count = cuisine_counts.get(cuisine, 0)
        search = CUISINE_SEARCH.get(cuisine, "restaurant food plate")
        slug = cuisine.lower().replace("/", "_").replace(" ", "_")
        status = "✅" if os.path.exists(os.path.join(OUTPUT_DIR, f"{slug}_hero.webp")) else "⬜"
        print(f"  {status} {cuisine:25s} ({count:4d} restaurants) → \"{search}\"")

    if args.dry_run:
        print(f"\n🔍 DRY RUN — no downloads performed.")
        return

    # Create directories
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    # Download phase
    downloaded = {}
    if not args.process_only:
        print(f"\n📥 Downloading {len(cuisines_in_data)} cuisine photos...\n")
        for cuisine in cuisines_in_data:
            search = CUISINE_SEARCH.get(cuisine, "restaurant food plate")
            raw_path = download_cuisine_photo(cuisine, search, RAW_DIR)
            if raw_path:
                downloaded[cuisine] = raw_path
            time.sleep(1)  # Rate limit courtesy
    else:
        # Gather existing raw files
        for cuisine in cuisines_in_data:
            slug = cuisine.lower().replace("/", "_").replace(" ", "_")
            raw_path = os.path.join(RAW_DIR, f"{slug}.jpg")
            if os.path.exists(raw_path):
                downloaded[cuisine] = raw_path

    # Process phase
    print(f"\n🔧 Processing {len(downloaded)} images into WebP...\n")
    manifest = {}
    for cuisine, raw_path in sorted(downloaded.items()):
        print(f"  🖼️  {cuisine}:")
        result = process_raw_to_webp(raw_path, cuisine, OUTPUT_DIR)
        if result:
            manifest[cuisine] = result

    # Save manifest
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Summary
    hero_count = sum(1 for m in manifest.values() if m.get("hero"))
    card_count = sum(1 for m in manifest.values() if m.get("card"))
    total_files = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.webp')])

    print(f"\n{'=' * 60}")
    print(f"✅ Pipeline complete!")
    print(f"   Cuisines covered: {len(manifest)}/{len(cuisines_in_data)}")
    print(f"   Hero images: {hero_count}")
    print(f"   Card images: {card_count}")
    print(f"   Total WebP files: {total_files}")
    print(f"   Output: {OUTPUT_DIR}/")
    print(f"   Manifest: {manifest_path}")

    # Coverage stats
    covered_restaurants = sum(
        cuisine_counts.get(c, 0) for c in manifest
    )
    print(f"\n   🎯 Restaurant coverage: {covered_restaurants}/{len(restaurants)} "
          f"({100*covered_restaurants/len(restaurants):.1f}%)")


if __name__ == "__main__":
    main()
