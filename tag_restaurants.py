#!/usr/bin/env python3
"""
Menuverso Smart Tagger — Auto-generates tags from notes, cuisine, pricing, and other metadata.
Also detects outdoor seating, reservation requirements, and other features.
Writes enriched tags back to restaurants.json and regenerates restaurants_data.js.
"""

import json
import re

INPUT = "restaurants.json"

# Tag detection rules: (tag_name, detection_function)
# Each function takes a restaurant dict and returns True/False

def detect_tags(r):
    """Generate tags for a restaurant based on all available fields."""
    tags = set()
    notes = (r.get("notes", "") or "").lower()
    name = (r.get("name", "") or "").lower()
    cuisine = (r.get("cuisine_type", "") or "")
    tier = (r.get("pricing_tier", "") or "")
    menu_tier = (r.get("menu_tier", "") or "")
    price = (r.get("menu_price_range", "") or "")
    
    # === DIETARY ===
    veg_words = ["vegetarian", "veggie", "vegan", "plant-based", "flexitarian"]
    if any(w in notes for w in veg_words) or cuisine == "Vegetarian/Vegan":
        tags.add("vegetarian")
    if "vegan" in notes or "plant-based" in notes:
        tags.add("vegan")
    if "gluten" in notes or "gf " in notes or "celiac" in notes:
        tags.add("gluten-free")
    if "organic" in notes or "ecológico" in notes:
        tags.add("organic")
    if "healthy" in notes or "nutritious" in notes:
        tags.add("healthy")
    
    # === CUISINE TAGS ===
    if "tapas" in notes or "pintxos" in notes or "montaditos" in notes:
        tags.add("tapas")
    if "paella" in notes or "arroz" in notes or "rice" in notes or "fideuà" in notes:
        tags.add("rice-dishes")
    if "ramen" in notes or "ramen" in name:
        tags.add("ramen")
    if "sushi" in notes:
        tags.add("sushi")
    if "pizza" in notes or "pizza" in name:
        tags.add("pizza")
    if "burger" in notes or "burger" in name:
        tags.add("burgers")
    if "brunch" in notes or "brunch" in name:
        tags.add("brunch")
    if "ceviche" in notes:
        tags.add("ceviche")
    if "taco" in notes or "taquería" in name:
        tags.add("tacos")
    if "seafood" in notes or cuisine == "Seafood" or "fish" in notes or "mariscos" in notes:
        tags.add("seafood")
    if "homemade" in notes or "home-style" in notes or "casera" in notes:
        tags.add("homemade")
    if "market" in notes or "mercado" in notes or "market-fresh" in notes or "boqueria" in notes:
        tags.add("market-fresh")
    
    # === EXPERIENCE ===
    if "tasting menu" in notes or "menú degustación" in notes:
        tags.add("tasting-menu")
    if "michelin" in notes:
        tags.add("michelin")
    if any(w in notes for w in ["terrace", "terraza", "outdoor", "garden", "patio", "exterior"]):
        tags.add("terrace")
        r["outdoor_seating"] = True
    if any(w in notes for w in ["cozy", "acogedor", "intimate", "small"]):
        tags.add("cozy")
    if "historic" in notes or "since 19" in notes or "since 18" in notes or "120+" in notes or "60+" in notes or "50+" in notes or "years" in notes:
        tags.add("historic")
    if any(w in notes for w in ["family-run", "family-owned", "familiar"]):
        tags.add("family-run")
    if any(w in notes for w in ["modern", "contemporary", "creative", "avant-garde", "innovative"]):
        tags.add("creative")
    if "reservation" in notes or "reserv" in notes:
        tags.add("reservations")
        r["reservation_required"] = True
    if "views" in notes or "sea view" in notes or "overlooking" in notes:
        tags.add("views")
    if "instagram" in notes or "instagrammable" in notes:
        tags.add("instagrammable")
    if "live music" in notes:
        tags.add("live-music")
    if any(w in notes for w in ["dog-friendly", "dog friendly", "pet"]):
        tags.add("dog-friendly")
        r["dog_friendly"] = True
    
    # === VALUE ===
    if tier == "budget":
        tags.add("budget-friendly")
    if "great value" in notes or "good value" in notes or "affordable" in notes or "cheap" in notes or "spectacular prices" in notes:
        tags.add("great-value")
    
    # === SPECIAL ===
    if "chain" in notes.upper() or "CHAIN" in (r.get("notes", "") or ""):
        tags.add("chain")
    if "closed" in notes.lower() and ("permanently" in notes.lower() or "2020" in notes or "2021" in notes):
        r["status"] = "permanently_closed"
        tags.add("closed")
    if menu_tier == "confirmed":
        tags.add("menú-del-día")
    
    # === MEAL TYPE ===
    hours = (r.get("opening_hours_lunch", "") or "")
    if "mon-fri" in hours.lower() or "tue-fri" in hours.lower():
        tags.add("weekday-lunch")
    
    # === EXPANDED TAGS ===
    hood = (r.get("neighborhood", "") or "")
    address = (r.get("address_full", "") or "").lower()
    
    # Wine bar
    if any(w in notes for w in ["wine bar", "wine list", "wine selection", "natural wine",
                                  "vinos", "wine pairing", "sommelier", "bodega"]):
        tags.add("wine-bar")
    if any(w in name for w in ["bodega", "vinoteca", "vins", "celler"]):
        tags.add("wine-bar")
    
    # Date night
    if any(w in notes for w in ["romantic", "intimate", "candlelit", "date",
                                  "special occasion", "elegant", "fine dining"]):
        tags.add("date-night")
    if tier == "premium" and any(w in notes for w in ["tasting", "ambiance", "atmosphere"]):
        tags.add("date-night")
    
    # Business lunch
    if any(w in notes for w in ["business", "corporate", "professional",
                                  "executive", "working lunch", "working day"]):
        tags.add("business-lunch")
    if "menú-del-día" in tags and hood in ("Eixample", "Les Corts", "Sarrià-Sant Gervasi"):
        if tier in ("mid-range", "premium"):
            tags.add("business-lunch")
    
    # Solo-friendly
    if any(w in notes for w in ["counter", "bar seating", "bar service",
                                  "standing", "stand-up", "solo"]):
        tags.add("solo-friendly")
    if "pintxos" in notes or "tapas bar" in notes:
        tags.add("solo-friendly")
    
    # Late night
    if any(w in notes for w in ["late night", "late-night", "until 2", "until 3",
                                  "midnight", "cocktail bar", "opens late"]):
        tags.add("late-night")
    
    # Waterfront
    if any(w in notes for w in ["sea view", "port", "marina", "harbor",
                                  "waterfront", "beachside", "seafront", "overlooking port"]):
        tags.add("waterfront")
    if hood == "Barceloneta" and ("port" in notes or "sea" in notes or "beach" in notes):
        tags.add("waterfront")
    if "passeig de joan de borbó" in address or "pg. marítim" in address:
        tags.add("waterfront")
    
    # Rooftop
    if any(w in notes for w in ["rooftop", "top floor", "azotea", "terraza superior"]):
        tags.add("rooftop")
    
    # Kid-friendly
    if any(w in notes for w in ["family", "families", "kids", "children", "child-friendly"]):
        tags.add("kid-friendly")
    
    # Group dining
    if any(w in notes for w in ["group", "sharing", "for sharing", "large groups",
                                  "communal", "banquet", "party"]):
        tags.add("group-dining")
    
    # Breakfast
    if any(w in notes for w in ["breakfast", "desayuno", "morning"]):
        tags.add("breakfast")
    if cuisine == "Café" and "brunch" not in tags:
        tags.add("breakfast")
    
    # Craft beer
    if any(w in notes for w in ["craft beer", "cerveza artesanal", "microbrewery",
                                  "draft beer", "craft beers", "cerveseria"]):
        tags.add("craft-beer")
    if "cervecería" in name or "cerveseria" in name:
        tags.add("craft-beer")
    
    # Cocktails
    if any(w in notes for w in ["cocktail", "cocktails", "mixology", "mixologist"]):
        tags.add("cocktails")
    
    # Natural wine
    if any(w in notes for w in ["natural wine", "natural wines", "vi natural", "vins naturals"]):
        tags.add("natural-wine")
    
    # Churros
    if any(w in notes for w in ["churros", "chocolate caliente", "xocolata"]):
        tags.add("churros")
    
    return sorted(tags)


def detect_outdoor_seating(r):
    """Detect outdoor seating from notes."""
    notes = (r.get("notes", "") or "").lower()
    return any(w in notes for w in ["terrace", "terraza", "outdoor", "garden", "patio", "backyard", "exterior"])


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)
    
    total = len(restaurants)
    tag_counts = {}
    tagged = 0
    
    for r in restaurants:
        tags = detect_tags(r)
        r["tags"] = tags
        if tags:
            tagged += 1
        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    
    # Save
    with open(INPUT, "w") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    
    with open("restaurants_data.js", "w") as f:
        f.write("var RESTAURANT_DATA = ")
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
        f.write(";\n")
    
    print(f"🏷️  Tagged {tagged}/{total} restaurants ({tagged/total*100:.0f}%)")
    print(f"\n📊 Tag distribution:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        bar = "█" * (count // 10)
        print(f"   {tag:20s} {count:4d}  {bar}")
    
    print(f"\n   Total unique tags: {len(tag_counts)}")
    print(f"   Avg tags per restaurant: {sum(tag_counts.values())/total:.1f}")
    
    # Feature detection summary
    outdoor = sum(1 for r in restaurants if r.get("outdoor_seating"))
    reservation = sum(1 for r in restaurants if r.get("reservation_required"))
    dog = sum(1 for r in restaurants if r.get("dog_friendly"))
    closed = sum(1 for r in restaurants if r.get("status") == "permanently_closed")
    
    print(f"\n🔍 Feature detection:")
    print(f"   Outdoor seating: {outdoor}")
    print(f"   Reservation required: {reservation}")
    print(f"   Dog-friendly: {dog}")
    print(f"   Permanently closed: {closed}")
    
    print(f"\n   Output: {INPUT}")
    print(f"   JS data: restaurants_data.js")


if __name__ == "__main__":
    main()
