#!/usr/bin/env python3
"""
Menuverso Google Maps URL Generator — Creates Google Maps URLs for all restaurants.
Always uses restaurant name + address for the search query so Google Maps finds the
actual business listing rather than dropping a pin at raw coordinates.
"""

import json
from urllib.parse import quote_plus

INPUT = "restaurants.json"


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    total = len(restaurants)
    generated = 0

    for r in restaurants:
        name = r.get("name", "")
        addr = r.get("address_full", "")
        city = r.get("city", "Barcelona")
        hood = r.get("neighborhood", "")

        if not name:
            continue

        # Always use name-based search so Google Maps finds the business listing
        # Include address if available for disambiguation
        parts = [name]
        if addr:
            parts.append(addr)
        parts.append(city)

        query = " ".join(parts).strip()
        r["google_maps_url"] = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
        generated += 1

    # Save
    with open(INPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(f"🗺️  Generated Google Maps URLs for {generated}/{total} restaurants")
    print(f"   All URLs use name-based search (finds business listing, not raw pin)")

    # Verify a few examples
    for r in restaurants[:3]:
        print(f"   #{r['id']} {r['name']}: {r['google_maps_url'][:80]}...")


if __name__ == "__main__":
    main()
