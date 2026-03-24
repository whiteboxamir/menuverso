#!/usr/bin/env python3
"""
Menuverso Google Maps Enrichment Script
Fetches website, phone, instagram, and opening_hours from Google Maps Places API.

Prerequisites:
  pip install requests
  export GOOGLE_MAPS_API_KEY="your-key-here"

Usage:
  python3 enrich_from_gmaps.py              # Enrich all with missing data
  python3 enrich_from_gmaps.py --limit 50   # Enrich first 50
  python3 enrich_from_gmaps.py --resume     # Resume from last checkpoint

API Cost:
  Uses Place Details (Basic + Contact + Atmosphere) = ~$0.02/request
  Full 1520 restaurants ≈ $30 one-time cost
"""

import json
import os
import sys
import time
import argparse

INPUT = "restaurants.json"
CHECKPOINT = ".gmaps_enrichment_checkpoint.json"

# Fields we want to enrich
FIELDS = "name,formatted_phone_number,website,opening_hours,url"

DAYS_MAP = {
    0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday",
    4: "friday", 5: "saturday", 6: "sunday"
}


def find_place(name, address, api_key):
    """Find a place on Google Maps by name + address."""
    import requests

    query = f"{name} {address} Barcelona"
    url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id",
        "key": api_key,
    }
    resp = requests.get(url, params=params)
    data = resp.json()

    if data.get("candidates"):
        return data["candidates"][0].get("place_id")
    return None


def get_place_details(place_id, api_key):
    """Get detailed info for a place."""
    import requests

    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": FIELDS,
        "key": api_key,
    }
    resp = requests.get(url, params=params)
    return resp.json().get("result", {})


def extract_instagram(website_url):
    """Try to extract Instagram handle from website or social links."""
    if not website_url:
        return ""
    if "instagram.com" in website_url:
        parts = website_url.rstrip("/").split("/")
        return f"@{parts[-1]}" if parts[-1] else ""
    return ""


def parse_opening_hours(hours_data):
    """Convert Google Maps opening_hours to our schema format."""
    if not hours_data or "periods" not in hours_data:
        return None

    result = {d: "" for d in DAYS_MAP.values()}
    result["closed_days"] = []

    # Get weekday_text for simpler parsing
    if "weekday_text" in hours_data:
        weekday_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, text in enumerate(hours_data["weekday_text"]):
            day = weekday_names[i]
            # Format: "Monday: 1:00 – 4:00 PM, 8:00 – 11:30 PM" or "Monday: Closed"
            parts = text.split(": ", 1)
            if len(parts) == 2:
                hours_str = parts[1]
                if "Closed" in hours_str:
                    result[day] = "Closed"
                    result["closed_days"].append(day)
                else:
                    # Convert 12h to 24h format
                    result[day] = hours_str
    return result


def enrich_restaurant(r, api_key):
    """Enrich a single restaurant from Google Maps."""
    name = r.get("name", "")
    address = r.get("address_full", "")

    # Find place
    place_id = find_place(name, address, api_key)
    if not place_id:
        return False, "not_found"

    # Get details
    details = get_place_details(place_id, api_key)
    if not details:
        return False, "no_details"

    enriched = False

    # Enrich website (only if empty)
    if not r.get("website") and details.get("website"):
        r["website"] = details["website"]
        enriched = True

    # Enrich phone (only if empty)
    if not r.get("phone") and details.get("formatted_phone_number"):
        phone = details["formatted_phone_number"]
        # Normalize to +34 format
        if not phone.startswith("+"):
            phone = f"+34 {phone}"
        r["phone"] = phone
        enriched = True

    # Enrich opening hours (only if all empty)
    hours = r.get("opening_hours_full", {})
    is_heuristic = all(
        hours.get(d, "") in ("", "Closed") or "13:00" in hours.get(d, "")
        for d in ["monday", "tuesday", "wednesday"]
    )
    if details.get("opening_hours") and is_heuristic:
        parsed = parse_opening_hours(details["opening_hours"])
        if parsed:
            r["opening_hours_full"] = parsed
            enriched = True

    # Try to get Instagram from website
    if not r.get("instagram") and details.get("website"):
        ig = extract_instagram(details["website"])
        if ig:
            r["instagram"] = ig
            enriched = True

    return enriched, "ok"


def load_checkpoint():
    """Load enrichment checkpoint."""
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"completed_ids": [], "stats": {"enriched": 0, "not_found": 0, "errors": 0}}


def save_checkpoint(data):
    """Save enrichment checkpoint."""
    with open(CHECKPOINT, "w") as f:
        json.dump(data, f)


def main():
    parser = argparse.ArgumentParser(description="Enrich Menuverso DB from Google Maps")
    parser.add_argument("--limit", type=int, default=0, help="Max restaurants to process (0=all)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--dry-run", action="store_true", help="Don't save changes")
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("❌ Set GOOGLE_MAPS_API_KEY environment variable first:")
        print("   export GOOGLE_MAPS_API_KEY='your-key-here'")
        sys.exit(1)

    with open(INPUT) as f:
        restaurants = json.load(f)

    checkpoint = load_checkpoint() if args.resume else {"completed_ids": [], "stats": {"enriched": 0, "not_found": 0, "errors": 0}}
    completed = set(checkpoint["completed_ids"])
    stats = checkpoint["stats"]

    # Filter to restaurants needing enrichment
    needs_enrichment = [
        r for r in restaurants
        if r["id"] not in completed
        and r.get("status") != "permanently_closed"
        and (not r.get("website") or not r.get("phone"))
    ]

    if args.limit:
        needs_enrichment = needs_enrichment[:args.limit]

    total = len(needs_enrichment)
    print(f"🔍 Enriching {total} restaurants from Google Maps API...")
    print(f"   Already completed: {len(completed)}")
    print(f"   Estimated cost: ${total * 0.02:.2f}")
    print()

    for i, r in enumerate(needs_enrichment):
        try:
            enriched, status = enrich_restaurant(r, api_key)
            completed.add(r["id"])

            if enriched:
                stats["enriched"] += 1
                print(f"  ✅ {i+1}/{total} #{r['id']} {r['name']}")
            elif status == "not_found":
                stats["not_found"] += 1
                print(f"  ❓ {i+1}/{total} #{r['id']} {r['name']} — not found")
            else:
                print(f"  ⏭️  {i+1}/{total} #{r['id']} {r['name']} — already complete")

        except Exception as e:
            stats["errors"] += 1
            print(f"  ❌ {i+1}/{total} #{r['id']} {r['name']} — {e}")

        # Save checkpoint every 25 restaurants
        if (i + 1) % 25 == 0:
            checkpoint["completed_ids"] = list(completed)
            checkpoint["stats"] = stats
            save_checkpoint(checkpoint)
            if not args.dry_run:
                with open(INPUT, "w") as f:
                    json.dump(restaurants, f, indent=2, ensure_ascii=False)
            print(f"   💾 Checkpoint saved ({i+1}/{total})")

        # Rate limit: 10 requests/second max
        time.sleep(0.15)

    # Final save
    checkpoint["completed_ids"] = list(completed)
    checkpoint["stats"] = stats
    save_checkpoint(checkpoint)

    if not args.dry_run:
        with open(INPUT, "w") as f:
            json.dump(restaurants, f, indent=2, ensure_ascii=False)
        with open("restaurants_data.js", "w") as f:
            f.write("var RESTAURANT_DATA = ")
            json.dump(restaurants, f, indent=2, ensure_ascii=False)
            f.write(";\n")

    print(f"\n📊 Results:")
    print(f"   Enriched: {stats['enriched']}")
    print(f"   Not found: {stats['not_found']}")
    print(f"   Errors: {stats['errors']}")
    print(f"   Output: {INPUT}")


if __name__ == "__main__":
    main()
