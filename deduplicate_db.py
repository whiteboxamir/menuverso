#!/usr/bin/env python3
"""
Menuverso Database Deduplication Script
=======================================
Identifies and removes duplicate restaurant entries from restaurants.json.

Strategy:
- For each duplicate group, KEEP the entry with the most complete data (lower ID usually = richer)
- Merge any unique non-empty fields from the duplicate into the keeper
- Remove the duplicate entry
- Re-generate restaurants_data.js from the cleaned JSON
- Clean up orphaned HTML pages in r/
"""

import json
import re
import os
import shutil
from collections import defaultdict
from datetime import datetime

DB_PATH = "restaurants.json"
JS_PATH = "restaurants_data.js"
PAGES_DIR = "r"
BACKUP_SUFFIX = f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def load_db():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_js(data):
    with open(JS_PATH, "w", encoding="utf-8") as f:
        f.write("const restaurantsData = ")
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write(";\n")

def normalize(name):
    """Normalize a restaurant name for comparison."""
    name = name.lower().strip()
    name = re.sub(r'[^a-záéíóúàèìòùüñç0-9\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def strip_neighborhood(name):
    """Remove trailing neighborhood suffixes from normalized name."""
    neighborhoods = [
        'eixample', 'gràcia', 'gracia', 'born', 'el born', 'raval', 'el raval',
        'barceloneta', 'gòtic', 'gotic', 'barri gòtic', 'barri gotic',
        'sant antoni', 'poble sec', 'poble nou', 'poblenou', 'clot',
        'sants', 'les corts', 'sarrià', 'sarria', 'sant gervasi',
        'horta', 'guinardó', 'guinardo', 'barcelona', 'sant martí'
    ]
    for n in sorted(neighborhoods, key=len, reverse=True):
        if name.endswith(' ' + n):
            name = name[:-(len(n) + 1)].strip()
    return name

def completeness_score(entry):
    """Score how complete/rich a restaurant entry is. Higher = better."""
    score = 0
    important_fields = [
        'name', 'address', 'neighborhood', 'cuisine_type', 'pricing_tier',
        'menu_del_dia_confirmed', 'menu_price_range', 'website', 'google_maps_url',
        'phone', 'opening_hours_lunch', 'notes', 'tags', 'amenities',
        'latitude', 'longitude', 'og_image', 'slug'
    ]
    for field in important_fields:
        val = entry.get(field)
        if val and val not in ['', 'N/A', 'Unknown', '[]', [], None]:
            score += 1
            # Bonus for rich fields
            if field == 'address' and len(str(val)) > 30:
                score += 1
            if field == 'tags' and isinstance(val, list) and len(val) > 0:
                score += len(val)
            if field == 'website' and 'http' in str(val):
                score += 1
            if field == 'phone' and len(str(val)) > 5:
                score += 1
    return score

def merge_entry(keeper, duplicate):
    """Merge non-empty fields from duplicate into keeper (don't overwrite existing)."""
    for key, val in duplicate.items():
        if key == 'id':
            continue
        keeper_val = keeper.get(key)
        # If keeper has empty/missing value but duplicate has data, take it
        if (not keeper_val or keeper_val in ['', 'N/A', 'Unknown', [], None]) and \
           val and val not in ['', 'N/A', 'Unknown', [], None]:
            keeper[key] = val

def find_duplicates(data):
    """Find all duplicate groups. Returns list of (keeper_id, remove_ids) tuples."""
    by_id = {r['id']: r for r in data}
    
    # === PASS 1: Automated fuzzy matching (same core name + same neighborhood) ===
    groups = defaultdict(list)
    for r in data:
        cn = strip_neighborhood(normalize(r.get('name', '')))
        hood = r.get('neighborhood', '')
        groups[(cn, hood)].append(r)
    
    auto_dupes = {}
    for (cn, hood), entries in groups.items():
        if len(entries) > 1:
            # Keep the one with highest completeness, break ties with lower ID
            entries_sorted = sorted(entries, key=lambda e: (-completeness_score(e), e['id']))
            keeper = entries_sorted[0]
            removes = entries_sorted[1:]
            for r in removes:
                auto_dupes[r['id']] = keeper['id']
    
    # === PASS 2: Manual/pattern-based duplicates not caught by fuzzy matching ===
    # These are cases where names differ too much for automated detection
    manual_groups = [
        # (keeper_id, [duplicate_ids])  — keeper = the one with the best data
        # Café/Cafè accent variant
        (180, [615]),       # Cafè de l'Acadèmia (id=180) + Café de l'Acadèmia (id=615)
        # "Els Quatre Gats" vs "Els 4Gats"
        (177, [808]),       # Els Quatre Gats + Els 4Gats
        # "Bar La Plata" vs "La Plata"
        (194, [806]),       # Bar La Plata + La Plata (same place in Gòtic)
        # "Lanto Restaurant" vs "Lanto"
        (62, [533]),        # Lanto Restaurant + Lanto (both Clot)
        # "La Vinateria del Call" vs "Vinateria del Call"  
        (490, [812]),       # same place, just missing "La"
        # "IRATI Taverna Basca" vs "Irati"
        (190, [612]),       # same place in Gòtic
        # "Milk Bar & Bistro" vs "Milk Bar Gòtic" (both Barri Gòtic)
        (200, [1162]),      # same place
        # "Restaurante Agut" — 3rd variant of Agut in Barri Gòtic
        # (380 or 1161 already caught, but 614 "Restaurante Agut" needs flagging too)
        (380, [614]),       # Agut + Restaurante Agut (1161 caught automatically)
        # "La Alcoba Azul" vs "L'Alcoba Azul"
        (193, [807]),       # accent/article variant
        # "Le Bistro Sensi" vs "Sensi Bistro" (both Barri Gòtic, same place)
        (810, [1190]),      # same restaurant
        # "Gourmet Sensi" vs "Sensi Tapas" — these could be different concepts
        # Skipping: they might be distinct restaurants sharing "Sensi" brand
        # "Federal Cafe Gotic" vs "Federal Café Gòtic" (accent difference)
        (201, [485]),       # same place
        # "Federal Café" vs "Federal Café Sant Antoni" (Sant Antoni — already caught)
        # "Cervecería Vaso de Oro" — 3rd variant of Vaso de Oro in Barceloneta
        (371, [1199]),      # Vaso de Oro + Cervecería Vaso de Oro (1169 caught automatically)
        # "Can Cortada" vs "Can Cortada Restaurant"
        # Already caught by automated pass, but confirming
        # "Nana Restaurant" vs "Nana Restaurant Brasa" — same place
        (64, [566]),        # both Clot
    ]
    
    for keeper_id, remove_ids in manual_groups:
        for rid in remove_ids:
            if rid not in auto_dupes:  # Don't double-count
                auto_dupes[rid] = keeper_id
    
    return auto_dupes

def main():
    data = load_db()
    print(f"Loaded {len(data)} restaurants")
    
    # Backup
    shutil.copy2(DB_PATH, DB_PATH + BACKUP_SUFFIX)
    shutil.copy2(JS_PATH, JS_PATH + BACKUP_SUFFIX)
    print(f"Backed up to {DB_PATH + BACKUP_SUFFIX}")
    
    # Find duplicates
    dupes = find_duplicates(data)
    print(f"\nFound {len(dupes)} duplicate entries to remove")
    
    by_id = {r['id']: r for r in data}
    
    # Merge data from duplicates into keepers, then remove
    removed_ids = set()
    removed_slugs = set()
    for remove_id, keeper_id in sorted(dupes.items()):
        if remove_id in by_id and keeper_id in by_id:
            keeper = by_id[keeper_id]
            duplicate = by_id[remove_id]
            print(f"  REMOVE id={remove_id} \"{duplicate['name']}\" → KEEP id={keeper_id} \"{keeper['name']}\"")
            merge_entry(keeper, duplicate)
            removed_ids.add(remove_id)
            slug = duplicate.get('slug', '')
            if slug:
                removed_slugs.add(slug)
    
    # Filter out removed entries
    cleaned = [r for r in data if r['id'] not in removed_ids]
    
    # Re-assign sequential IDs
    for i, r in enumerate(cleaned):
        r['id'] = i + 1
    
    print(f"\nCleaned database: {len(cleaned)} restaurants (removed {len(data) - len(cleaned)})")
    
    # Save
    save_db(cleaned)
    save_js(cleaned)
    print(f"Saved {DB_PATH} and {JS_PATH}")
    
    # Clean up orphaned HTML pages
    orphaned_pages = 0
    if os.path.isdir(PAGES_DIR):
        # Build set of valid page IDs from old data
        for rid in removed_ids:
            old_page = os.path.join(PAGES_DIR, f"{rid}.html")
            if os.path.exists(old_page):
                os.remove(old_page)
                orphaned_pages += 1
                print(f"  Removed orphaned page: {old_page}")
    
    print(f"\nRemoved {orphaned_pages} orphaned HTML pages")
    print(f"\n✅ Deduplication complete!")
    print(f"   Before: {len(data)} restaurants")
    print(f"   After:  {len(cleaned)} restaurants")
    print(f"   Removed: {len(removed_ids)} duplicates")

if __name__ == "__main__":
    main()
