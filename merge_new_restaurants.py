#!/usr/bin/env python3
"""
Menuverso — Safe Restaurant Merge Script
==========================================
Merges a validated batch of new restaurants into the database.
Runs validation BEFORE and AFTER merge. Rolls back on any error.

Usage:
    python3 merge_new_restaurants.py scraped_batch_2026-03-25_183000.json
    python3 merge_new_restaurants.py scraped_batch_2026-03-25_183000.json --dry-run
"""

import json
import sys
import os
import shutil
from datetime import datetime

INPUT = "restaurants.json"
JS_OUTPUT = "restaurants_data.js"


def validate_batch(batch_file):
    """Run validate_data.py --check-new on the batch. Returns True if passed."""
    import subprocess
    result = subprocess.run(
        [sys.executable, 'validate_data.py', '--check-new', batch_file],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0


def validate_full_db():
    """Run validate_data.py on the full database. Returns True if passed."""
    import subprocess
    result = subprocess.run(
        [sys.executable, 'validate_data.py'],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0


def dedup_against_existing(new_records, existing):
    """Remove records that already exist in the database."""
    existing_names = {r.get('name', '').lower().strip() for r in existing}
    clean = []
    dupes = []
    for r in new_records:
        name = r.get('name', '').lower().strip()
        if name in existing_names:
            dupes.append(r.get('name', ''))
        else:
            clean.append(r)
            existing_names.add(name)
    return clean, dupes


def rebuild_js(data):
    """Rebuild restaurants_data.js from data."""
    with open(JS_OUTPUT, 'w') as f:
        f.write('var RESTAURANT_DATA = ')
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write(';\n')


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 merge_new_restaurants.py <batch_file.json> [--dry-run]")
        sys.exit(1)
    
    batch_file = sys.argv[1]
    dry_run = '--dry-run' in sys.argv
    
    print("=" * 60)
    print("  MENUVERSO SAFE MERGE")
    print("  🔒 Validation Required at Every Step")
    print("=" * 60)
    
    # ── Step 1: Load batch ──────────────────────────────────────
    print(f"\n📥 Loading batch: {batch_file}")
    with open(batch_file) as f:
        new_records = json.load(f)
    print(f"   {len(new_records)} new records")
    
    # ── Step 2: Gate 1 — Validate batch ─────────────────────────
    print(f"\n🔒 GATE 1: Validating batch...")
    if not validate_batch(batch_file):
        print("\n❌ GATE 1 FAILED — Batch rejected. Fix errors and retry.")
        sys.exit(1)
    print("   ✅ Gate 1 passed")
    
    # ── Step 3: Load existing database ──────────────────────────
    print(f"\n📊 Loading existing database...")
    with open(INPUT) as f:
        existing = json.load(f)
    print(f"   {len(existing)} existing records")
    
    # ── Step 4: Dedup ───────────────────────────────────────────
    clean, dupes = dedup_against_existing(new_records, existing)
    if dupes:
        print(f"\n⚠️  Removed {len(dupes)} duplicates:")
        for d in dupes[:10]:
            print(f"   - {d}")
        if len(dupes) > 10:
            print(f"   ... and {len(dupes) - 10} more")
    
    if not clean:
        print("\n⚠️  No new records to merge (all duplicates).")
        sys.exit(0)
    
    print(f"\n📊 {len(clean)} new records to merge")
    
    # ── Step 5: Assign IDs ──────────────────────────────────────
    max_id = max(r.get('id', 0) for r in existing)
    for i, r in enumerate(clean):
        r['id'] = max_id + 1 + i
    
    print(f"   Assigned IDs: {max_id + 1} → {max_id + len(clean)}")
    
    if dry_run:
        print(f"\n🏷  DRY RUN — would merge {len(clean)} records:")
        for r in clean:
            print(f"   [{r['id']}] {r['name']} | {r['neighborhood']} | ★{r.get('google_maps_rating', '?')}")
        return
    
    # ── Step 6: Backup ──────────────────────────────────────────
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"restaurants_BACKUP_{ts}.json"
    shutil.copy2(INPUT, backup_file)
    print(f"\n💾 Backup: {backup_file}")
    
    # ── Step 7: Merge ───────────────────────────────────────────
    merged = existing + clean
    
    with open(INPUT, 'w') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    
    rebuild_js(merged)
    print(f"\n✅ Merged! Database now has {len(merged)} records")
    
    # ── Step 8: Gate 2 — Full DB validation ─────────────────────
    print(f"\n🔒 GATE 2: Validating full database...")
    if not validate_full_db():
        print("\n❌ GATE 2 FAILED — Rolling back!")
        shutil.copy2(backup_file, INPUT)
        with open(INPUT) as f:
            rollback_data = json.load(f)
        rebuild_js(rollback_data)
        print(f"   ↩️  Rolled back to {len(existing)} records")
        sys.exit(1)
    
    print("   ✅ Gate 2 passed")
    
    # ── Summary ─────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  ✅ MERGE COMPLETE")
    print(f"  Previous: {len(existing)} records")
    print(f"  Added:    {len(clean)} records")
    print(f"  New total: {len(merged)} records")
    print(f"  Backup:   {backup_file}")
    print(f"{'─' * 60}")


if __name__ == '__main__':
    main()
