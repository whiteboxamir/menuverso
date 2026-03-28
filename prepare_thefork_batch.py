#!/usr/bin/env python3
"""
Prepare TheFork Festival restaurants for Menuverso database.
Phase 1: Convert TheFork data → Menuverso schema format.
Phase 2: Enrich with Google Maps data (ratings, reviews, coordinates).

Usage:
    python3 prepare_thefork_batch.py
"""

import json
import re
import urllib.parse
from datetime import date

# ── Cuisine Mapping: TheFork (ES) → Menuverso Enum ────────────────────────
CUISINE_MAP = {
    'fusión': 'Fusion', 'fusion': 'Fusion', 'de fusión': 'Fusion',
    'castellano': 'Spanish', 'español': 'Spanish', 'spanish': 'Spanish',
    'argentino': 'Argentine', 'argentine': 'Argentine',
    'catalán': 'Catalan', 'catalan': 'Catalan',
    'mediterráneo': 'Mediterranean', 'mediterranean': 'Mediterranean',
    'indio': 'Indian', 'indian': 'Indian',
    'italiano': 'Italian', 'italian': 'Italian',
    'japonés': 'Japanese', 'japanese': 'Japanese',
    'mexicano': 'Mexican', 'mexican': 'Mexican',
    'internacional': 'Fusion', 'international': 'Fusion',
    'americano': 'Other', 'american': 'Other',
    'arrocería': 'Spanish', 'rice': 'Spanish',
    'asador': 'Argentine',
    'chino': 'Chinese', 'chinese': 'Chinese',
    'coreano': 'Korean', 'korean': 'Korean',
    'thai': 'Thai', 'tailandés': 'Thai',
    'francés': 'French', 'french': 'French',
    'griego': 'Greek', 'greek': 'Greek',
    'libanés': 'Lebanese', 'lebanese': 'Lebanese',
    'turco': 'Turkish', 'turkish': 'Turkish',
    'peruano': 'Peruvian', 'peruvian': 'Peruvian',
    'colombiano': 'Colombian', 'colombian': 'Colombian',
    'cubano': 'Cuban', 'cuban': 'Cuban',
    'etíope': 'Ethiopian', 'ethiopian': 'Ethiopian',
    'marroquí': 'Middle Eastern', 'moroccan': 'Middle Eastern',
    'vasco': 'Basque', 'basque': 'Basque',
    'vegetariano': 'Vegetarian/Vegan', 'vegano': 'Vegetarian/Vegan',
    'mariscos': 'Seafood', 'seafood': 'Seafood',
    'pizzería': 'Italian', 'pizza': 'Italian',
    'brunch': 'Café', 'café': 'Café', 'cafe': 'Café',
    'gastropub': 'Gastropub',
    'sushi': 'Japanese',
    'tapas': 'Spanish',
    'caribeño': 'Other', 'caribbean': 'Other',
}

# ── Neighborhood detection from address strings ───────────────────────────
NEIGHBORHOODS = {
    'born': 'El Born', 'el born': 'El Born',
    'raval': 'El Raval', 'el raval': 'El Raval',
    'gòtic': 'Barri Gòtic', 'gotic': 'Barri Gòtic', 'barri gòtic': 'Barri Gòtic',
    'eixample': 'Eixample',
    'gràcia': 'Gràcia', 'gracia': 'Gràcia',
    'poblenou': 'Poblenou', 'poble nou': 'Poblenou',
    'poble sec': 'Poble Sec', 'poblesec': 'Poble Sec',
    'barceloneta': 'Barceloneta',
    'sants': 'Sants',
    'sant antoni': 'Sant Antoni',
    'sant martí': 'Sant Martí',
    'les corts': 'Les Corts',
    'sarrià': 'Sarrià-Sant Gervasi', 'sant gervasi': 'Sarrià-Sant Gervasi',
    'sagrada': 'Sagrada Família', 'sagrada familia': 'Sagrada Família',
    'horta': 'Horta-Guinardó', 'guinardó': 'Horta-Guinardó',
    'nou barris': 'Nou Barris',
    'sant andreu': 'Sant Andreu',
    'clot': 'Clot',
    'zona franca': 'Sants',
}

# Street → neighborhood mapping for common Barcelona streets
STREET_NEIGHBORHOODS = {
    'aribau': 'Eixample', 'aragó': 'Eixample', 'arago': 'Eixample',
    'diputació': 'Eixample', 'consell de cent': 'Eixample',
    'gran via': 'Eixample', 'valencia': 'Eixample', 'mallorca': 'Eixample',
    'provença': 'Eixample', 'rosselló': 'Eixample', 'enric granados': 'Eixample',
    'rambla catalunya': 'Eixample', 'pau claris': 'Eixample',
    'passeig de gràcia': 'Eixample', 'balmes': 'Eixample',
    'comte d\'urgell': 'Eixample', 'urgell': 'Eixample', 'villarroel': 'Eixample',
    'rocafort': 'Eixample', 'entença': 'Eixample', 'calabria': 'Eixample',
    'calàbria': 'Eixample', 'comte borrell': 'Eixample', 'manso': 'Sant Antoni',
    'parlament': 'Sant Antoni',
    'marià cubí': 'Sarrià-Sant Gervasi', 'muntaner': 'Eixample',
    'francisco giner': 'Gràcia',
    'born': 'El Born', 'passeig del born': 'El Born', 'princesa': 'El Born',
    'rec comtal': 'El Born', 'rec': 'El Born',
    'ferran': 'Barri Gòtic', 'avinyó': 'Barri Gòtic', 'petritxol': 'Barri Gòtic',
    'bonsuccés': 'El Raval', 'ronda de sant pau': 'El Raval',
    'sant pau': 'El Raval', 'hospital': 'El Raval',
    'portal de l\'àngel': 'Barri Gòtic', 'plaça catalunya': 'Eixample',
    'pl. de catalunya': 'Eixample',
    'margarit': 'Poble Sec', 'poeta cabanyes': 'Poble Sec', 'blai': 'Poble Sec',
    'tapioles': 'Poble Sec', 'olzinelles': 'Sants',
    'pujades': 'Poblenou',
    'josep anselm clavé': 'Barri Gòtic',
    'sant antoni': 'Sant Antoni', 'pg. sant antoni': 'Sant Antoni',
    'mare de déu de port': 'Sants', 'zona franca': 'Sants',
    'cardenal reig': 'Les Corts',
    'bou de sant pere': 'El Born',
    'letamendi': 'Eixample', 'dr. letamendi': 'Eixample',
}


def guess_neighborhood(address):
    """Guess neighborhood from address string."""
    addr_lower = address.lower() if address else ''
    
    # Try street-based mapping first (more specific)
    for street, hood in STREET_NEIGHBORHOODS.items():
        if street in addr_lower:
            return hood
    
    # Fall back to general neighborhood names
    for key, hood in NEIGHBORHOODS.items():
        if key in addr_lower:
            return hood
    
    return 'Eixample'  # default for Barcelona


def guess_cuisine(name, thefork_cuisine):
    """Map TheFork cuisine to Menuverso enum."""
    if thefork_cuisine:
        cuisine_lower = thefork_cuisine.lower().strip()
        if cuisine_lower in CUISINE_MAP:
            return CUISINE_MAP[cuisine_lower]
    
    # Try to guess from restaurant name
    name_lower = name.lower()
    name_hints = {
        'sushi': 'Japanese', 'japanese': 'Japanese', 'nippon': 'Japanese',
        'pizza': 'Italian', 'ristorante': 'Italian', 'trattoria': 'Italian',
        'india': 'Indian', 'curry': 'Indian', 'tandoori': 'Indian',
        'steak': 'Argentine', 'asador': 'Argentine', 'grill': 'Argentine',
        'brasa': 'Argentine', 'gaucha': 'Argentine', 'argentin': 'Argentine',
        'tapas': 'Spanish', 'bodega': 'Spanish',
        'brunch': 'Café', 'café': 'Café', 'cafe': 'Café',
        'mexican': 'Mexican', 'taco': 'Mexican', 'adelita': 'Mexican',
        'marrakech': 'Middle Eastern', 'halal': 'Middle Eastern',
        'carib': 'Other',
        'gluten free': 'Other',
    }
    for hint, cuisine in name_hints.items():
        if hint in name_lower:
            return cuisine
    
    return 'Mediterranean'  # default


def derive_pricing_tier(price_str):
    """Derive pricing tier from average price string like '28€'."""
    if not price_str:
        return 'mid-range'
    nums = re.findall(r'(\d+)', price_str)
    if nums:
        price = int(nums[0])
        if price <= 15:
            return 'budget'
        elif price <= 25:
            return 'mid-range'
        else:
            return 'premium'
    return 'mid-range'


def clean_address(address):
    """Extract street address from full Barcelona address."""
    if not address:
        return ''
    # Remove ", Barcelona" suffix
    addr = re.sub(r',?\s*Barcelona\s*$', '', address).strip()
    return addr


def build_gmaps_url(name, address):
    """Build Google Maps search URL."""
    query = f"{name} {address} Barcelona"
    return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote_plus(query)}"


def main():
    # Load TheFork data
    with open('thefork_festival_barcelona.json') as f:
        tf_data = json.load(f)
    
    # Load existing DB to find duplicates
    with open('restaurants.json') as f:
        existing = json.load(f)
    existing_names = {r['name'].lower().strip() for r in existing}
    
    batch = []
    skipped = []
    today = date.today().isoformat()
    
    for r in tf_data['restaurants']:
        name = r['name'].strip()
        
        # Skip duplicates
        if name.lower() in existing_names:
            skipped.append(name)
            continue
        
        address_full = clean_address(r.get('address', ''))
        cuisine = guess_cuisine(name, r.get('cuisine', ''))
        neighborhood = guess_neighborhood(address_full or name)
        pricing_tier = derive_pricing_tier(r.get('avg_price', ''))
        
        record = {
            "name": name,
            "address": f"{neighborhood}, Barcelona",
            "address_full": address_full,
            "postal_code": "",
            "city": "Barcelona",
            "neighborhood": neighborhood,
            "cuisine_type": cuisine,
            "pricing_tier": pricing_tier,
            "menu_del_dia_confirmed": False,
            "menu_price_range": "",
            "menu_tier": "none",
            "menu_evidence": "none",
            "dinner_menu_del_dia": False,
            "dinner_price_range": r.get('avg_price', '').replace('€', '') + '€' if r.get('avg_price') else '',
            "dinner_tier": "unknown",
            "website": "",
            "phone": "",
            "instagram": "",
            "google_maps_url": build_gmaps_url(name, address_full),
            "google_maps_rating": None,  # Will be enriched from Google Maps
            "google_maps_review_count": None,  # Will be enriched
            "opening_hours_lunch": "13:00-16:00",
            "opening_hours_full": {
                "monday": "", "tuesday": "", "wednesday": "",
                "thursday": "", "friday": "", "saturday": "", "sunday": "",
                "closed_days": []
            },
            "images": {
                "hero": "", "food": [], "interior": [], "exterior": [],
                "menu_photo": [], "ambiance": [], "team": []
            },
            "notes": f"TheFork Festival 2026 participant. {r.get('avg_price', '')} avg. TheFork rating: {r.get('rating', 'N/A')}/10.",
            "verification_status": "active_no_menu_info",
            "source": "thefork",
            "last_verified": today,
            "reservation_required": False,
            "delivery_available": False,
            "outdoor_seating": False,
            "dog_friendly": False,
            "status": "active",
            "tags": ["thefork-festival"],
            "coordinates": {},
            "has_photo": False,
            "thefork_rating": r.get('rating'),
            "thefork_avg_price": r.get('avg_price', '')
        }
        
        batch.append(record)
    
    # Save batch
    output_file = 'thefork_batch_ready.json'
    with open(output_file, 'w') as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Prepared {len(batch)} new restaurants")
    print(f"⏭  Skipped {len(skipped)} duplicates: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")
    print(f"📄 Output: {output_file}")
    print(f"\n⚠️  Records need Google Maps enrichment before merging:")
    print(f"   - google_maps_rating (1-5 scale)")
    print(f"   - google_maps_review_count")
    print(f"   - coordinates (lat/lng)")
    
    # Stats
    cuisines = {}
    tiers = {}
    hoods = {}
    for r in batch:
        cuisines[r['cuisine_type']] = cuisines.get(r['cuisine_type'], 0) + 1
        tiers[r['pricing_tier']] = tiers.get(r['pricing_tier'], 0) + 1
        hoods[r['neighborhood']] = hoods.get(r['neighborhood'], 0) + 1
    
    print(f"\n📊 Cuisine breakdown:")
    for c, n in sorted(cuisines.items(), key=lambda x: -x[1]):
        print(f"   {c}: {n}")
    print(f"\n💰 Pricing tiers:")
    for t, n in sorted(tiers.items(), key=lambda x: -x[1]):
        print(f"   {t}: {n}")
    print(f"\n📍 Top neighborhoods:")
    for h, n in sorted(hoods.items(), key=lambda x: -x[1])[:8]:
        print(f"   {h}: {n}")


if __name__ == '__main__':
    main()
