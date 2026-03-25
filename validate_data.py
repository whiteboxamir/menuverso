#!/usr/bin/env python3
"""
Menuverso Data Integrity Validator
===================================
Run this BEFORE and AFTER any data changes to restaurants.json.
This script catches AI-fabricated or low-quality records.

Usage:
    python3 validate_data.py                    # Full validation
    python3 validate_data.py --check-new FILE   # Validate new records before merging
    python3 validate_data.py --strict            # Strict mode (errors on warnings)
    python3 validate_data.py --check-new FILE --strict
"""

import json
import sys
import os
from collections import Counter

REQUIRED_FIELDS = [
    'id', 'name', 'city', 'source', 'neighborhood',
    'cuisine_type', 'google_maps_url', 'google_maps_rating',
    'google_maps_review_count', 'status'
]

# For new records, ID is not required (merge script assigns it)
REQUIRED_FIELDS_NEW = [
    'name', 'city', 'source', 'neighborhood',
    'cuisine_type', 'google_maps_url', 'google_maps_rating',
    'google_maps_review_count', 'status'
]

ADDRESS_FIELDS = ['address', 'address_full']

VALID_SOURCES = [
    'web_search', 'google_maps_scrape', 'thefork', 'tripadvisor',
    'manual_entry', 'eltenedor', 'menu_del_dia_site'
]

VALID_CITIES = ['Barcelona']

VALID_NEIGHBORHOODS = [
    'Eixample', 'Gràcia', 'Poblenou', 'El Raval', 'El Born',
    'Poble Sec', 'Barri Gòtic', 'Sants', 'Sarrià-Sant Gervasi',
    'Les Corts', 'Barceloneta', 'Sagrada Família', 'Horta-Guinardó',
    'Sant Antoni', 'Sant Martí', 'Nou Barris', 'Sant Andreu', 'Clot'
]

BCN_LAT_RANGE = (41.32, 41.47)
BCN_LNG_RANGE = (2.05, 2.23)


class DataValidator:
    def __init__(self, data, strict=False):
        self.data = data
        self.strict = strict
        self.errors = []
        self.warnings = []

    def error(self, record_id, name, msg):
        self.errors.append(f"❌ [{record_id}] {name}: {msg}")

    def warn(self, record_id, name, msg):
        self.warnings.append(f"⚠️  [{record_id}] {name}: {msg}")

    def validate_required_fields(self, fields_list=None):
        """Every record must have all required fields populated."""
        check_fields = fields_list or REQUIRED_FIELDS
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            for field in check_fields:
                val = r.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    self.error(rid, name, f"Missing required field: {field}")

    def validate_has_address(self):
        """Every record must have at least one address field."""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            has_addr = any(
                r.get(f, '').strip() for f in ADDRESS_FIELDS
            )
            if not has_addr:
                self.error(rid, name, "No address (neither 'address' nor 'address_full')")

    def validate_source(self):
        """Source must be from approved list — no mystery data."""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            source = r.get('source', '')
            if source and source not in VALID_SOURCES:
                self.warn(rid, name, f"Unknown source: '{source}'")

    def validate_city(self):
        """City must be Barcelona."""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            city = r.get('city', '')
            if city and city not in VALID_CITIES:
                self.error(rid, name, f"Invalid city: '{city}' (expected: Barcelona)")

    def validate_no_duplicates(self):
        """No duplicate names allowed."""
        names = [r.get('name', '') for r in self.data]
        dupes = [n for n, count in Counter(names).items() if count > 1]
        if dupes:
            for d in dupes:
                self.error('?', d, f"Duplicate restaurant name (appears {names.count(d)} times)")

    def validate_sequential_ids(self):
        """IDs must be sequential from 1 to N."""
        ids = sorted([r.get('id', 0) for r in self.data])
        expected = list(range(1, len(self.data) + 1))
        if ids != expected:
            gaps = set(expected) - set(ids)
            extras = set(ids) - set(expected)
            if gaps:
                self.error('?', 'DATABASE', f"Missing IDs: {sorted(list(gaps))[:10]}...")
            if extras:
                self.error('?', 'DATABASE', f"Extra IDs: {sorted(list(extras))[:10]}...")

    def validate_neighborhood_not_in_name(self):
        """Flag records where neighborhood appears suspiciously in name 
        (AI fabrication pattern: 'Real Name + Neighborhood')"""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', '')
            hood = r.get('neighborhood', '')
            if hood and name.endswith(' ' + hood):
                msg = f"Name ends with neighborhood '{hood}' — possible AI fabrication"
                if self.strict:
                    self.error(rid, name, msg)
                else:
                    self.warn(rid, name, msg)

    def validate_scrape_source_urls(self):
        """Records from google_maps_scrape must have real place URLs or
        at minimum a street address in the search URL — not just name+city."""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            source = r.get('source', '')
            url = r.get('google_maps_url', '')
            addr = r.get('address_full', '')
            
            if source == 'google_maps_scrape':
                # Must have a real address
                if not addr or len(addr) < 5:
                    self.error(rid, name,
                        "google_maps_scrape record missing real street address")
                
                # URL must exist
                if not url:
                    self.error(rid, name,
                        "google_maps_scrape record missing Google Maps URL")
                
                # Rating must be a real number > 0
                rating = r.get('google_maps_rating', 0)
                if not rating or float(rating) == 0:
                    self.warn(rid, name,
                        "google_maps_scrape record has no rating — verify manually")
                
                # Review count must be > 0
                reviews = r.get('google_maps_review_count', 0)
                if not reviews or int(reviews) == 0:
                    self.warn(rid, name,
                        "google_maps_scrape record has 0 reviews — verify manually")

    def validate_rating_range(self):
        """Ratings must be between 1.0 and 5.0."""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            rating = r.get('google_maps_rating')
            if rating is not None:
                try:
                    rating_f = float(rating)
                    if rating_f < 1.0 or rating_f > 5.0:
                        self.error(rid, name, f"Invalid rating: {rating}")
                except (ValueError, TypeError):
                    self.error(rid, name, f"Non-numeric rating: {rating}")

    def validate_coordinates(self):
        """Coordinates must be in Barcelona area."""
        for r in self.data:
            rid = r.get('id', '?')
            name = r.get('name', 'UNNAMED')
            coords = r.get('coordinates', {})
            if coords:
                lat = coords.get('lat')
                lng = coords.get('lng')
                if lat and lng:
                    if not (BCN_LAT_RANGE[0] <= lat <= BCN_LAT_RANGE[1]):
                        self.error(rid, name, f"Latitude {lat} outside Barcelona range")
                    if not (BCN_LNG_RANGE[0] <= lng <= BCN_LNG_RANGE[1]):
                        self.error(rid, name, f"Longitude {lng} outside Barcelona range")

    def run_all(self):
        """Run all validation checks."""
        print("=" * 60)
        print("  MENUVERSO DATA INTEGRITY VALIDATOR")
        print("=" * 60)
        print(f"\nValidating {len(self.data)} records...\n")

        self.validate_required_fields()
        self.validate_has_address()
        self.validate_source()
        self.validate_city()
        self.validate_no_duplicates()
        self.validate_sequential_ids()
        self.validate_neighborhood_not_in_name()
        self.validate_scrape_source_urls()
        self.validate_rating_range()
        self.validate_coordinates()

        if self.errors:
            print(f"🚫 ERRORS ({len(self.errors)}):")
            for e in self.errors[:30]:
                print(f"  {e}")
            if len(self.errors) > 30:
                print(f"  ... and {len(self.errors) - 30} more")
            print()

        if self.warnings:
            print(f"⚠️  WARNINGS ({len(self.warnings)}):")
            for w in self.warnings[:20]:
                print(f"  {w}")
            if len(self.warnings) > 20:
                print(f"  ... and {len(self.warnings) - 20} more")
            print()

        if not self.errors and not self.warnings:
            print("✅ ALL CHECKS PASSED — Database is clean!\n")

        # Summary
        print("─" * 60)
        print(f"  Records:    {len(self.data)}")
        print(f"  Errors:     {len(self.errors)}")
        print(f"  Warnings:   {len(self.warnings)}")
        print(f"  Status:     {'❌ FAILED' if self.errors else '✅ PASSED'}")
        print("─" * 60)

        return len(self.errors) == 0


def validate_new_records(filepath):
    """Validate a JSON file of NEW records before merging into the database."""
    print(f"\n🔎 Validating new records from: {filepath}")
    
    with open(filepath, 'r') as f:
        new_data = json.load(f)
    
    if not isinstance(new_data, list):
        new_data = [new_data]
    
    print(f"   Found {len(new_data)} new records\n")
    
    strict = '--strict' in sys.argv
    validator = DataValidator(new_data, strict=strict)
    
    validator.validate_required_fields(fields_list=REQUIRED_FIELDS_NEW)
    validator.validate_has_address()
    validator.validate_source()
    validator.validate_city()
    validator.validate_no_duplicates()
    validator.validate_neighborhood_not_in_name()
    validator.validate_scrape_source_urls()
    validator.validate_rating_range()
    validator.validate_coordinates()
    
    # Cross-reference with existing database
    if os.path.exists('restaurants.json'):
        with open('restaurants.json', 'r') as f:
            existing = json.load(f)
        existing_names = {r.get('name', '').lower() for r in existing}
        
        for r in new_data:
            name = r.get('name', '')
            if name.lower() in existing_names:
                validator.error(r.get('id', '?'), name, 
                    "DUPLICATE — already exists in restaurants.json")
    
    if validator.errors:
        print(f"🚫 BLOCKED — {len(validator.errors)} errors found:")
        for e in validator.errors:
            print(f"  {e}")
    elif validator.warnings:
        print(f"⚠️  WARNINGS ({len(validator.warnings)}):")
        for w in validator.warnings:
            print(f"  {w}")
        print("\n✅ No blocking errors. Review warnings before merging.")
    else:
        print("✅ New records pass validation. Safe to merge.")
    
    return len(validator.errors) == 0


if __name__ == '__main__':
    strict = '--strict' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--strict']
    
    if args and args[0] == '--check-new':
        if len(args) < 2:
            print("Usage: python3 validate_data.py --check-new <new_records.json> [--strict]")
            sys.exit(1)
        success = validate_new_records(args[1])
    else:
        with open('restaurants.json', 'r') as f:
            data = json.load(f)
        validator = DataValidator(data, strict=strict)
        success = validator.run_all()
    
    sys.exit(0 if success else 1)
