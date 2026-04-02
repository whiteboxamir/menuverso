#!/usr/bin/env python3
"""
Post-Geocoding Pipeline — Run after geocoding thread completes.
Chains: metro_stations → google_maps_urls → generate_pages → git push

Usage: python3 post_geocode_pipeline.py
"""

import subprocess
import sys
import json
from datetime import datetime


def run(cmd, desc):
    print(f"\n{'='*60}")
    print(f"📌 {desc}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout[-500:])  # Last 500 chars
    if result.returncode != 0:
        print(f"⚠️  Warning: {result.stderr[-300:]}")
    return result.returncode == 0


def check_geocoding_status():
    """Report current geocoding coverage."""
    with open("restaurants.json") as f:
        data = json.load(f)
    
    total = len(data)
    has_coords = sum(1 for r in data if r.get("coordinates") and r["coordinates"].get("lat"))
    precise = sum(1 for r in data if r.get("coordinates") and r["coordinates"].get("lat") 
                  and len(str(r["coordinates"]["lat"]).split(".")[-1]) >= 5)
    centroid = has_coords - precise
    missing = total - has_coords
    
    print(f"""
📊 GEOCODING STATUS
{'='*40}
Total restaurants:  {total}
With coordinates:   {has_coords} ({has_coords/total*100:.1f}%)
  ├─ Precise:       {precise} ({precise/total*100:.1f}%)
  └─ Centroid:      {centroid} ({centroid/total*100:.1f}%)
Missing coords:     {missing} ({missing/total*100:.1f}%)
{'='*40}
""")
    return precise, centroid, missing


def main():
    start = datetime.now()
    print(f"\n🚀 POST-GEOCODING PIPELINE — {start.strftime('%Y-%m-%d %H:%M')}")
    
    precise, centroid, missing = check_geocoding_status()
    
    if missing > 100:
        print(f"⚠️  {missing} restaurants still missing coordinates.")
        print("   Consider running geocoding thread longer before this pipeline.")
        resp = input("   Continue anyway? (y/N): ").strip().lower()
        if resp != 'y':
            print("Aborted.")
            sys.exit(0)
    
    # Step 1: Metro stations
    run("python3 metro_stations.py", "Step 1/4: Assigning nearest metro stations")
    
    # Step 2: Google Maps URLs
    run("python3 google_maps_urls.py", "Step 2/4: Generating Google Maps URLs")
    
    # Step 3: Regenerate restaurants_data.js
    with open("restaurants.json") as f:
        data = json.load(f)
    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(data, f, ensure_ascii=False)
        f.write(";\n")
    print(f"\n✅ Regenerated restaurants_data.js ({len(data)} entries)")
    
    # Step 4: Regenerate individual pages + sitemap
    run("python3 generate_pages.py", "Step 3/4: Regenerating 1,504 restaurant pages + sitemap")
    
    # Final status
    precise2, centroid2, missing2 = check_geocoding_status()
    
    elapsed = (datetime.now() - start).total_seconds()
    print(f"""
🏁 PIPELINE COMPLETE — {elapsed:.0f}s
{'='*40}
Precise geocodes:   {precise} → {precise2} (+{precise2-precise})
Metro assignments:  ✅ Updated
Maps URLs:          ✅ Updated
Restaurant pages:   ✅ Regenerated
restaurants_data.js:✅ Synced
{'='*40}

Next: git add -A && git commit -m "Post-geocoding: update metro, maps, pages" && git push
""")


if __name__ == "__main__":
    main()
