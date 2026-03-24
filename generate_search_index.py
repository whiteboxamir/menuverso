#!/usr/bin/env python3
"""
Menuverso Search Index Generator
Creates a lightweight JSON search index for client-side fuzzy search.
This avoids loading the full restaurants_data.js for search-only operations.
"""

import json

INPUT = "restaurants.json"
OUTPUT = "search_index.js"


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    # Build compact search entries
    index = []
    for r in restaurants:
        entry = {
            "i": r["id"],  # id
            "n": r.get("name", ""),  # name
            "h": r.get("neighborhood", ""),  # hood
            "c": r.get("cuisine_type", ""),  # cuisine
            "t": r.get("menu_tier", "none"),  # tier
            "p": r.get("menu_price_range", ""),  # price
            "r": r.get("google_maps_rating", 0),  # rating
            "m": r.get("metro_station", ""),  # metro
            "g": r.get("tags", []),  # tags
        }
        # Add notes keywords (first 60 chars)
        notes = r.get("notes", "")
        if notes:
            entry["k"] = notes[:60]
        index.append(entry)

    js = f"// Menuverso Search Index — {len(index)} entries\n"
    js += f"// Generated: lightweight index for instant client-side search\n"
    js += f"window.MENUVERSO_SEARCH_INDEX = {json.dumps(index, ensure_ascii=False, separators=(',', ':'))};\n"

    with open(OUTPUT, "w") as f:
        f.write(js)

    import os
    size_kb = os.path.getsize(OUTPUT) / 1024
    print(f"🔍 Generated search index: {OUTPUT} ({len(index)} entries, {size_kb:.0f}KB)")


if __name__ == "__main__":
    main()
