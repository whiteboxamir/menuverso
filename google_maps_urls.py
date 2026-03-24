#!/usr/bin/env python3
"""
Menuverso Google Maps URL Generator — Creates Google Maps URLs for geocoded restaurants.
Also generates search URLs for restaurants without coordinates using name + address.
"""

import json
from urllib.parse import quote_plus

INPUT = "restaurants.json"


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    total = len(restaurants)
    from_coords = 0
    from_search = 0

    for r in restaurants:
        coords = r.get("coordinates", {})
        lat = coords.get("lat")
        lng = coords.get("lng")
        name = r.get("name", "")
        addr = r.get("address_full", "")
        city = r.get("city", "Barcelona")

        if lat and lng:
            # Direct coordinate URL
            r["google_maps_url"] = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            from_coords += 1
        elif name:
            # Search-based URL
            query = f"{name} {addr} {city}".strip()
            r["google_maps_url"] = f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"
            from_search += 1

    # Save
    with open(INPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    print(f"🗺️  Generated Google Maps URLs for {from_coords + from_search}/{total} restaurants")
    print(f"   From coordinates: {from_coords}")
    print(f"   From search query: {from_search}")


if __name__ == "__main__":
    main()
