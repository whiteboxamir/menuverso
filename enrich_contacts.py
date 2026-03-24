#!/usr/bin/env python3
"""
Menuverso Contact Enrichment — Extract phone numbers, websites, Instagram handles
from the notes field and cross-reference existing data.
Also generates a contact lookup list for manual enrichment.
"""

import json
import re

INPUT = "restaurants.json"


def extract_phone(text):
    """Extract Spanish phone numbers from text."""
    if not text:
        return None
    # Match +34 xxx xxx xxx, 93x xxx xxx, 6xx xxx xxx patterns
    patterns = [
        r'\+34\s?\d{3}\s?\d{3}\s?\d{3}',
        r'\+34\s?\d{3}\s?\d{2}\s?\d{2}\s?\d{2}',
        r'(?<!\d)9[0-9]{1,2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)',
        r'(?<!\d)6[0-9]{2}[\s.-]?\d{3}[\s.-]?\d{3}(?!\d)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r'[\s.-]', '', match.group())
            if not phone.startswith('+34'):
                phone = '+34' + phone
            return phone
    return None


def extract_website(text):
    """Extract URLs from text."""
    if not text:
        return None
    match = re.search(r'https?://[^\s,;)]+', text)
    if match:
        url = match.group().rstrip('.')
        return url
    # Look for domain patterns
    match = re.search(r'(?<!\w)www\.[^\s,;)]+', text)
    if match:
        return 'http://' + match.group().rstrip('.')
    return None


def extract_instagram(text):
    """Extract Instagram handles from text."""
    if not text:
        return None
    # @handle pattern
    match = re.search(r'@([a-zA-Z0-9_.]{3,30})', text)
    if match:
        handle = match.group(1).lower()
        # Filter out email domains
        if '.' in handle and handle.split('.')[-1] in ('com', 'es', 'cat', 'org'):
            return None
        return '@' + handle
    # instagram.com/handle pattern
    match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', text)
    if match:
        return '@' + match.group(1).lower()
    return None


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    stats = {"phone_extracted": 0, "website_extracted": 0, "instagram_extracted": 0}
    changes = []

    for r in restaurants:
        notes = r.get("notes", "") or ""
        name = r.get("name", "")

        # Try to extract phone from notes
        if not r.get("phone"):
            phone = extract_phone(notes)
            if phone:
                r["phone"] = phone
                stats["phone_extracted"] += 1
                changes.append(f"  #{r['id']} {name}: phone={phone}")

        # Try to extract website from notes
        if not r.get("website"):
            website = extract_website(notes)
            if website:
                r["website"] = website
                stats["website_extracted"] += 1
                changes.append(f"  #{r['id']} {name}: web={website}")

        # Try to extract Instagram from notes
        if not r.get("instagram"):
            ig = extract_instagram(notes)
            if ig:
                r["instagram"] = ig
                stats["instagram_extracted"] += 1
                changes.append(f"  #{r['id']} {name}: ig={ig}")

    # Save
    with open(INPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    # Summary
    has_website = sum(1 for r in restaurants if r.get('website'))
    has_phone = sum(1 for r in restaurants if r.get('phone'))
    has_instagram = sum(1 for r in restaurants if r.get('instagram'))

    print(f"📇 CONTACT ENRICHMENT RESULTS")
    print(f"  Phones extracted from notes:    {stats['phone_extracted']}")
    print(f"  Websites extracted from notes:  {stats['website_extracted']}")
    print(f"  Instagram extracted from notes: {stats['instagram_extracted']}")
    print()
    print(f"📊 UPDATED COVERAGE:")
    print(f"  Websites:   {has_website}/{len(restaurants)} ({100*has_website/len(restaurants):.0f}%)")
    print(f"  Phones:     {has_phone}/{len(restaurants)} ({100*has_phone/len(restaurants):.0f}%)")
    print(f"  Instagram:  {has_instagram}/{len(restaurants)} ({100*has_instagram/len(restaurants):.0f}%)")

    if changes:
        print(f"\n📝 CHANGES ({len(changes)}):")
        for c in changes[:30]:
            print(c)
        if len(changes) > 30:
            print(f"  ... and {len(changes)-30} more")

    # Generate a lookup priority list for manual enrichment
    # Prioritize confirmed restaurants without contacts
    no_contact = [r for r in restaurants if not r.get("website") and not r.get("phone") and r.get("menu_tier") == "confirmed"]
    print(f"\n🔍 MANUAL ENRICHMENT PRIORITY:")
    print(f"  Confirmed restaurants with NO website AND NO phone: {len(no_contact)}")
    print(f"  Top 10 to manually look up:")
    for r in no_contact[:10]:
        print(f"    #{r['id']} {r['name']} ({r['neighborhood']}) — search: https://www.google.com/search?q={r['name'].replace(' ','+')}+Barcelona+restaurant")

    print(f"\n   Output: restaurants.json + restaurants_data.js")


if __name__ == "__main__":
    main()
