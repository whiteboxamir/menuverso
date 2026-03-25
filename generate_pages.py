#!/usr/bin/env python3
"""
Menuverso Restaurant Page Generator — Partnership Pipeline Edition
Creates individual HTML pages for each restaurant with:
- Full-width cuisine hero image with gradient overlay
- Tabbed content layout (Info | Map | Reviews | Nearby)
- Partner Readiness profile card
- Premium typography, rounded corners, modern aesthetic
- Dark mode, share buttons, JSON-LD
"""

import json
import os
import math
from urllib.parse import quote_plus, quote

INPUT = "restaurants.json"
OUTPUT_DIR = "r"

# Cuisine emoji mapping for headers
CUISINE_EMOJI = {
    "Spanish": "🥘", "Mediterranean": "🥗", "Catalan": "🌶️", "Seafood": "🦐",
    "Café": "☕", "Italian": "🍝", "Japanese": "🍣", "Vegetarian/Vegan": "🥦",
    "Fusion": "🌍", "Asian": "🍜", "Mexican": "🌮", "Indian": "🍛",
    "Gastropub": "🍔", "Middle Eastern": "🧆", "Basque": "🥘",
    "French": "🧀", "Argentine": "🥩", "Peruvian": "🐟",
    "Chinese": "🥟", "Greek": "🥗", "Lebanese": "🧆",
    "Thai": "🍜", "Turkish": "🧆", "Korean": "🥢",
}


def get_cuisine_emoji(cuisine):
    return CUISINE_EMOJI.get(cuisine, "🍽️")


def haversine(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def find_nearby(restaurant, all_restaurants, n=3):
    if not restaurant.get("coordinates") or not restaurant["coordinates"].get("lat"):
        return []
    lat = restaurant["coordinates"]["lat"]
    lng = restaurant["coordinates"]["lng"]
    candidates = []
    for r in all_restaurants:
        if r["id"] == restaurant["id"]:
            continue
        if not r.get("coordinates") or not r["coordinates"].get("lat"):
            continue
        dist = haversine(lat, lng, r["coordinates"]["lat"], r["coordinates"]["lng"])
        candidates.append((dist, r))
    candidates.sort(key=lambda x: x[0])
    return [(d, r) for d, r in candidates[:n]]


def generate_page(r, all_restaurants, total_count):
    name = r.get("name", "Unknown")
    hood = r.get("neighborhood", "Barcelona")
    cuisine = r.get("cuisine_type", "")
    price = r.get("menu_price_range", "")
    tier = r.get("menu_tier", "none")
    rating = r.get("google_maps_rating", "")
    reviews = r.get("google_maps_review_count", 0)
    address = r.get("address_full", "")
    postal = r.get("postal_code", "")
    phone = r.get("phone", "")
    website = r.get("website", "")
    notes = r.get("notes", "")
    tags = r.get("tags", [])
    metro = r.get("metro_station", "")
    maps_url = r.get("google_maps_url", "")
    instagram = r.get("instagram", "")
    coords = r.get("coordinates", {})
    has_coords = coords.get("lat") and coords.get("lng")
    hours_lunch = r.get("opening_hours_lunch", "")
    cuisine_emoji = get_cuisine_emoji(cuisine)

    # Hero image: only real scraped photos — no fake stock images
    hero_img = None
    has_real_photo = False
    scraped_hero = f"assets/photos/{r['id']}_hero.webp"
    if os.path.exists(scraped_hero):
        hero_img = f"../{scraped_hero}"
        has_real_photo = True
    elif r.get("image_url") and os.path.exists(r["image_url"]):
        hero_img = f"../{r['image_url']}"
        has_real_photo = True

    # Profile completeness
    completeness = 0
    if name: completeness += 10
    if rating: completeness += 15
    if reviews and reviews > 50: completeness += 10
    if website: completeness += 15
    if phone: completeness += 10
    if instagram: completeness += 5
    if address: completeness += 10
    if price: completeness += 10
    if notes and len(notes) > 20: completeness += 5
    if metro: completeness += 5
    if has_coords: completeness += 5
    comp_pct = min(completeness, 100)

    tier_label = {"confirmed": "Deal-Ready", "likely": "High Potential", "none": "Prospect"}.get(tier, "")
    tier_emoji = {"confirmed": "🟢", "likely": "🟡", "none": "🔴"}.get(tier, "")
    tier_color = {"confirmed": "#059669", "likely": "#D97706", "none": "#DC2626"}.get(tier, "#94A3B8")
    tier_bg = {"confirmed": "#D1FAE5", "likely": "#FEF3C7", "none": "#FEE2E2"}.get(tier, "#F1F5F9")

    # Partner readiness score
    readiness = 0
    if phone: readiness += 20
    if website: readiness += 20
    if instagram: readiness += 15
    if has_real_photo: readiness += 10
    if rating and float(rating) >= 4.0: readiness += 15
    p_val = None
    if price:
        import re
        nums = re.findall(r'[\d.]+', price)
        if nums: p_val = float(nums[0])
    if p_val and 12 <= p_val <= 25: readiness += 20
    elif p_val and p_val > 25: readiness += 10
    readiness = min(readiness, 100)
    readiness_tier = 'high' if readiness >= 70 else 'mid' if readiness >= 40 else 'low'
    readiness_color = {'high': '#059669', 'mid': '#D97706', 'low': '#DC2626'}[readiness_tier]

    page_url = f"https://whiteboxamir.github.io/menuverso/r/{r['id']}.html"
    whatsapp_text = quote(f"Check out {name} in {hood}, Barcelona! {cuisine} restaurant. {page_url}")

    # JSON-LD
    jsonld = {
        "@context": "https://schema.org", "@type": "Restaurant",
        "name": name,
        "address": {"@type": "PostalAddress", "streetAddress": address, "addressLocality": "Barcelona", "postalCode": postal, "addressCountry": "ES"},
        "servesCuisine": cuisine,
    }
    if rating: jsonld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating, "reviewCount": reviews}
    if phone: jsonld["telephone"] = phone
    if website: jsonld["url"] = website
    if price: jsonld["priceRange"] = price
    if has_coords: jsonld["geo"] = {"@type": "GeoCoordinates", "latitude": coords["lat"], "longitude": coords["lng"]}

    # Stars HTML
    stars_html = ""
    if rating:
        rating_f = float(rating)
        full = int(rating_f)
        half = 1 if rating_f - full >= 0.3 else 0
        empty = 5 - full - half
        stars_html = '<span class="stars">' + ''.join(['<span class="star filled">★</span>'] * full)
        if half: stars_html += '<span class="star filled">★</span>'
        stars_html += ''.join(['<span class="star">★</span>'] * empty) + '</span>'

    # Tags HTML
    tag_html = "".join(f'<span class="tag">{t}</span>' for t in tags)

    # Contact links
    links = []
    if website: links.append(f'<a href="{website}" target="_blank" class="contact-link"><span class="link-icon">🌐</span> Website</a>')
    if maps_url: links.append(f'<a href="{maps_url}" target="_blank" class="contact-link"><span class="link-icon">📍</span> Google Maps</a>')
    if phone: links.append(f'<a href="tel:{phone}" class="contact-link"><span class="link-icon">📞</span> {phone}</a>')
    if instagram: links.append(f'<a href="https://instagram.com/{instagram.replace("@","")}" target="_blank" class="contact-link"><span class="link-icon">📸</span> {instagram}</a>')

    # Nearby restaurants
    nearby = find_nearby(r, all_restaurants)
    nearby_cards = []
    for dist, nr in nearby:
        nt = nr.get("menu_tier", "none")
        nl = {"confirmed": "🟢 Deal-Ready", "likely": "🟡 High Potential", "none": ""}.get(nt, "")
        dist_m = int(dist * 1000)
        dist_str = f"{dist_m}m" if dist_m < 1000 else f"{dist:.1f}km"
        nearby_cards.append(f'''<a href="{nr['id']}.html" class="nearby-card">
          <div class="nearby-icon">{get_cuisine_emoji(nr.get('cuisine_type',''))}</div>
          <div class="nearby-info">
            <div class="nearby-name">{nr['name']}</div>
            <div class="nearby-meta">{nl} {nr.get('cuisine_type','')} · {nr.get('menu_price_range','—')} · {dist_str}</div>
          </div>
        </a>''')
    nearby_html = f'''<div class="tab-content" id="tab-nearby">
      <h2>📍 Nearby Restaurants</h2>
      {''.join(nearby_cards) if nearby_cards else '<p class="empty-msg">No nearby restaurants with coordinates found.</p>'}
    </div>''' if True else ""

    # Map HTML
    map_content = ""
    map_script = ""
    leaflet_css = ""
    leaflet_js = ""
    if has_coords:
        leaflet_css = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />'
        leaflet_js = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></' + 'script>'
        map_content = f'''<div class="tab-content" id="tab-map">
      <div id="minimap"></div>
      <div class="map-address">
        <span class="link-icon">📍</span> {address}{f', {postal}' if postal else ''}, Barcelona
        {f'<br><span class="link-icon">🚇</span> {metro}' if metro else ''}
      </div>
    </div>'''
        map_script = f'''<script>
var m=L.map('minimap',{{zoomControl:true,scrollWheelZoom:false}}).setView([{coords["lat"]},{coords["lng"]}],16);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{maxZoom:19}}).addTo(m);
L.circleMarker([{coords["lat"]},{coords["lng"]}],{{radius:10,fillColor:'{tier_color}',color:'#fff',weight:3,fillOpacity:1}}).addTo(m);
if(document.documentElement.classList.contains('dark')){{document.querySelectorAll('.leaflet-tile').forEach(t=>t.style.filter='invert(1) hue-rotate(180deg) brightness(0.9)');}};
</script>'''
    else:
        map_content = '''<div class="tab-content" id="tab-map">
      <p class="empty-msg">📍 No precise coordinates available for this restaurant yet.</p>
    </div>'''

    # Reviews tab content
    reviews_content = ""
    if rating:
        reviews_content = f'''<div class="tab-content" id="tab-reviews">
      <div class="review-card">
        <div class="review-score">{rating}</div>
        <div class="review-details">
          <div>{stars_html}</div>
          <div class="review-count">{reviews:,} Google reviews</div>
        </div>
      </div>
      {f'<a href="{maps_url}" target="_blank" class="maps-review-link">View all reviews on Google Maps →</a>' if maps_url else ''}
    </div>'''
    else:
        reviews_content = '''<div class="tab-content" id="tab-reviews">
      <p class="empty-msg">No reviews data available yet.</p>
    </div>'''

    # Quick actions bar
    quick_btns = []
    if maps_url:
        quick_btns.append(f'<a href="{maps_url}" target="_blank" class="share-btn" style="flex:1;justify-content:center;">\U0001F4CD Directions</a>')
    if phone:
        quick_btns.append(f'<a href="tel:{phone}" class="share-btn" style="flex:1;justify-content:center;">\U0001F4DE Call</a>')
    if website:
        quick_btns.append(f'<a href="{website}" target="_blank" class="share-btn" style="flex:1;justify-content:center;">\U0001F310 Website</a>')
    quick_btns.append(f'<button class="share-btn" style="flex:1;justify-content:center;" onclick="toggleFav({r["id"]})">{chr(10084)}{chr(65039)} Save</button>')
    quick_actions_html = '<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.25rem;">' + '\n    '.join(quick_btns) + '</div>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — Barcelona Restaurant | Menuverso</title>
<meta name="description" content="{name} in {hood}, Barcelona. {cuisine} cuisine. {tier_label}. Partner readiness: {readiness}/100. Rating: {rating}/5 ({reviews} reviews).">
<meta property="og:title" content="{name} — {cuisine} in {hood} | Menuverso">
<meta property="og:description" content="{cuisine} in {hood}. {tier_label}. {'⭐ '+str(rating)+'/5' if rating else ''}">
<meta property="og:url" content="{page_url}">
<meta property="og:type" content="restaurant.restaurant">
<meta property="og:site_name" content="Menuverso">
<meta name="twitter:card" content="summary_large_image">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
{leaflet_css}
{leaflet_js}
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{
  --bg:#F8FAFC;--card:#FFFFFF;--text:#0F172A;--sub:#475569;--mut:#94A3B8;
  --border:#E2E8F0;--accent:#059669;--accent-bg:#D1FAE5;--accent-dark:#047857;
  --radius:16px;--radius-lg:24px;
  --shadow:0 4px 6px -1px rgba(0,0,0,0.1),0 2px 4px -2px rgba(0,0,0,0.1);
  --shadow-lg:0 10px 15px -3px rgba(0,0,0,0.1),0 4px 6px -4px rgba(0,0,0,0.1);
}}
:root.dark{{
  --bg:#0F172A;--card:#1E293B;--text:#F1F5F9;--sub:#94A3B8;--mut:#64748B;
  --border:#334155;--accent:#34D399;--accent-bg:#064E3B;--accent-dark:#6EE7B7;
  --shadow:0 4px 6px -1px rgba(0,0,0,0.3);--shadow-lg:0 10px 15px -3px rgba(0,0,0,0.4);
}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background 0.3s,color 0.3s;}}

/* Nav */
.topnav{{display:flex;align-items:center;justify-content:space-between;padding:0.6rem 1.5rem;border-bottom:1px solid var(--border);background:var(--card);position:sticky;top:0;z-index:100;backdrop-filter:blur(12px);}}
.nav-brand{{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);font-weight:700;font-size:1.1rem;}}
.nav-brand img{{width:28px;height:28px;border-radius:8px;}}
.nav-links{{display:flex;align-items:center;gap:1rem;}}
.nav-links a{{color:var(--sub);text-decoration:none;font-size:0.82rem;font-weight:500;padding:0.3rem 0.5rem;border-radius:8px;transition:all 0.2s;}}
.nav-links a:hover{{color:var(--text);background:var(--accent-bg);}}
.theme-btn{{background:none;border:1px solid var(--border);border-radius:20px;padding:0.3rem 0.55rem;cursor:pointer;font-size:0.85rem;color:var(--sub);transition:all 0.2s;}}
.theme-btn:hover{{border-color:var(--sub);color:var(--text);}}

/* Hero */
.hero{{position:relative;width:100%;height:320px;overflow:hidden;}}
.hero.has-photo img{{width:100%;height:100%;object-fit:cover;}}
.hero.no-photo{{background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 50%,#334155 100%);}}
.hero-emoji{{position:absolute;top:50%;left:50%;transform:translate(-50%,-70%);font-size:4rem;opacity:0.25;}}
.hero-overlay{{position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,0.7) 0%,rgba(0,0,0,0.1) 50%,rgba(0,0,0,0.0) 100%);}}
.hero-content{{position:absolute;bottom:0;left:0;right:0;padding:1.5rem 2rem;color:#fff;}}
.hero-back{{display:inline-flex;align-items:center;gap:4px;color:rgba(255,255,255,0.8);text-decoration:none;font-size:0.82rem;font-weight:500;margin-bottom:0.75rem;transition:color 0.2s;}}
.hero-back:hover{{color:#fff;}}
.hero h1{{font-size:clamp(1.5rem,4vw,2.2rem);font-weight:800;margin-bottom:0.4rem;text-shadow:0 2px 8px rgba(0,0,0,0.3);}}
.hero-meta{{display:flex;flex-wrap:wrap;gap:0.75rem;align-items:center;font-size:0.88rem;opacity:0.9;}}

/* Container */
.container{{max-width:720px;margin:-40px auto 0;padding:0 1rem 2rem;position:relative;z-index:2;}}

/* Partner Profile Card */
.deal-card{{background:{tier_bg};border:2px solid {tier_color}22;border-radius:var(--radius);padding:1.25rem 1.5rem;margin-bottom:1.25rem;box-shadow:var(--shadow);}}
.deal-header{{display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;}}
.deal-emoji{{font-size:1.5rem;}}
.deal-title{{font-size:1.1rem;font-weight:700;color:{tier_color};}}
.deal-price{{font-size:1.8rem;font-weight:800;color:var(--text);margin-bottom:0.25rem;}}
.deal-desc{{font-size:0.82rem;color:var(--sub);}}
.readiness-bar{{margin-top:0.75rem;}}
.readiness-label{{font-size:0.72rem;font-weight:600;color:var(--sub);text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px;}}
.readiness-track{{height:8px;background:var(--bg);border-radius:4px;overflow:hidden;}}
.readiness-fill{{height:100%;border-radius:4px;background:{readiness_color};transition:width 0.6s ease;}}
:root.dark .deal-card{{background:var(--card);border-color:{tier_color}44;}}

/* Open Status */
.open-status{{display:inline-flex;align-items:center;gap:5px;padding:0.3rem 0.75rem;border-radius:20px;font-size:0.75rem;font-weight:600;}}
.open-status.open{{background:#D1FAE5;color:#059669;}}
.open-status.closed{{background:#FEE2E2;color:#DC2626;}}
.open-status.unknown{{background:#F1F5F9;color:#94A3B8;}}
:root.dark .open-status.open{{background:#064E3B;color:#34D399;}}
:root.dark .open-status.closed{{background:#7F1D1D;color:#F87171;}}
:root.dark .open-status.unknown{{background:#1E293B;color:#64748B;}}
.open-dot{{width:7px;height:7px;border-radius:50%;display:inline-block;}}
.open .open-dot{{background:#059669;animation:pulse-green 2s infinite;}}
.closed .open-dot{{background:#DC2626;}}
@keyframes pulse-green{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:0.6;transform:scale(1.4);}}}}

/* Tabs */
.tabs{{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:1.25rem;overflow-x:auto;}}
.tab-btn{{padding:0.75rem 1.25rem;background:none;border:none;border-bottom:2px solid transparent;margin-bottom:-2px;font-family:Inter,sans-serif;font-size:0.88rem;font-weight:600;color:var(--mut);cursor:pointer;transition:all 0.2s;white-space:nowrap;}}
.tab-btn:hover{{color:var(--text);}}
.tab-btn.active{{color:var(--accent);border-bottom-color:var(--accent);}}
.tab-content{{display:none;animation:fadeIn 0.3s ease;}}
.tab-content.active{{display:block;}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(8px);}}to{{opacity:1;transform:translateY(0);}}}}

/* Info Section */
.info-section{{margin-bottom:1.5rem;}}
.info-section h3{{font-size:0.78rem;font-weight:600;color:var(--mut);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.75rem;}}
.info-row{{display:flex;gap:0.5rem;align-items:center;font-size:0.9rem;color:var(--sub);margin-bottom:0.5rem;}}
.link-icon{{font-size:1rem;flex-shrink:0;}}
.tags{{display:flex;flex-wrap:wrap;gap:0.35rem;margin-bottom:1.25rem;}}
.tag{{font-size:0.72rem;padding:4px 10px;border-radius:20px;background:var(--accent-bg);color:var(--accent);font-weight:600;border:1px solid var(--accent)22;}}
.notes{{font-size:0.88rem;color:var(--sub);line-height:1.7;padding:1rem 1.25rem;background:var(--bg);border-radius:var(--radius);border:1px solid var(--border);margin-bottom:1.25rem;}}
.contact-links{{display:flex;flex-wrap:wrap;gap:0.6rem;margin-bottom:1.25rem;}}
.contact-link{{padding:0.6rem 1.1rem;border:1px solid var(--border);border-radius:var(--radius);text-decoration:none;color:var(--accent);font-size:0.85rem;font-weight:600;transition:all 0.2s;display:inline-flex;align-items:center;gap:6px;background:var(--card);}}
.contact-link:hover{{background:var(--accent-bg);border-color:var(--accent);transform:translateY(-1px);box-shadow:var(--shadow);}}

/* Reviews */
.review-card{{display:flex;align-items:center;gap:1rem;padding:1.5rem;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);margin-bottom:1rem;}}
.review-score{{font-size:2.5rem;font-weight:800;color:var(--text);line-height:1;}}
.review-count{{font-size:0.85rem;color:var(--sub);font-weight:500;margin-top:0.25rem;}}
.stars{{display:inline-flex;gap:1px;}}
.star{{color:var(--border);font-size:1.2rem;}}
.star.filled{{color:#FBBF24;}}
.maps-review-link{{display:inline-block;color:var(--accent);text-decoration:none;font-size:0.85rem;font-weight:600;}}
.maps-review-link:hover{{text-decoration:underline;}}

/* Map */
#minimap{{width:100%;height:280px;border-radius:var(--radius);border:1px solid var(--border);margin-bottom:1rem;z-index:1;}}
:root.dark .leaflet-tile{{filter:invert(1) hue-rotate(180deg) brightness(0.9) contrast(0.9);}}
.map-address{{font-size:0.88rem;color:var(--sub);line-height:1.6;}}

/* Nearby */
.nearby-card{{display:flex;gap:1rem;padding:0.75rem;border:1px solid var(--border);border-radius:var(--radius);margin-bottom:0.6rem;text-decoration:none;color:var(--text);transition:all 0.2s;background:var(--card);}}
.nearby-card:hover{{border-color:var(--accent);transform:translateX(4px);box-shadow:var(--shadow);}}
.nearby-img{{width:80px;height:60px;border-radius:12px;object-fit:cover;flex-shrink:0;}}
.nearby-info{{display:flex;flex-direction:column;justify-content:center;}}
.nearby-name{{font-weight:700;font-size:0.9rem;margin-bottom:3px;}}
.nearby-meta{{font-size:0.78rem;color:var(--sub);}}
.empty-msg{{color:var(--mut);font-size:0.88rem;padding:2rem;text-align:center;}}

/* Share */
.share-section{{display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.25rem;}}
.share-btn{{padding:0.5rem 1rem;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--sub);font-size:0.82rem;font-weight:600;cursor:pointer;transition:all 0.2s;font-family:Inter,sans-serif;display:inline-flex;align-items:center;gap:5px;text-decoration:none;}}
.share-btn:hover{{border-color:var(--accent);color:var(--accent);background:var(--accent-bg);transform:translateY(-1px);}}

/* Community */
.community{{margin-top:0.5rem;}}
.visited-btn{{padding:0.7rem 1.25rem;border:2px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--sub);font-size:0.88rem;font-weight:600;cursor:pointer;transition:all 0.2s;font-family:Inter,sans-serif;display:flex;align-items:center;gap:8px;width:100%;margin-bottom:0.75rem;}}
.visited-btn:hover{{border-color:var(--accent);}}
.visited-btn.checked{{border-color:var(--accent);background:var(--accent-bg);color:var(--accent);}}

/* Footer */
footer{{text-align:center;padding:2rem;color:var(--mut);font-size:0.78rem;}}
footer a{{color:var(--sub);text-decoration:none;}}

img[src*="logo.png"]{{mix-blend-mode:multiply;}}
:root.dark img[src*="logo.png"]{{mix-blend-mode:normal;filter:brightness(1.2);}}
@media(max-width:640px){{
  .hero{{height:240px;}}
  .hero h1{{font-size:1.4rem;}}
  .container{{margin-top:-30px;}}
  .nav-links a span{{display:none;}}
  .tabs{{gap:0;}}
  .tab-btn{{padding:0.6rem 0.8rem;font-size:0.8rem;}}
}}
</style>
</head>
<body>
<nav class="topnav">
  <a href="../index.html" class="nav-brand">
    <img src="../assets/logo.png" alt="Menuverso">
    <span>Menuverso</span>
  </a>
  <div class="nav-links">
    <a href="../index.html"><span>📋 </span>Database</a>
    <a href="../analytics.html"><span>📊 </span>Market Intel</a>
    <a href="../lists.html"><span>🎯 </span>Target Lists</a>
    <a href="../landing.html"><span>💰 </span>Pitch</a>
  </div>
  <div>
    <button class="theme-btn" id="theme-toggle" onclick="toggleTheme()" title="Toggle dark mode">🌙</button>
  </div>
</nav>

<!-- Hero Section -->
<div class="hero {'has-photo' if has_real_photo else 'no-photo'}">
  {'<img src="' + hero_img + '" alt="' + name + '" loading="eager">' if has_real_photo else '<div class="hero-emoji">' + cuisine_emoji + '</div>'}
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <a href="../index.html?hood={quote_plus(hood)}" class="hero-back">← {hood}</a>
    <h1>{name}</h1>
    <div class="hero-meta">
      <span>{cuisine}</span>
      {'<span>·</span><span>' + stars_html + ' ' + str(rating) + '</span>' if rating else ''}
      {'<span>·</span><span>' + price + '</span>' if price else ''}
      <span>·</span>
      <div class="open-status unknown" id="open-status"><span class="open-dot"></span> <span id="open-text">Checking...</span></div>
    </div>
  </div>
</div>

<div class="container">
  <!-- Partner Profile Card -->
  <div class="deal-card">
    <div class="deal-header">
      <span class="deal-emoji">{tier_emoji}</span>
      <span class="deal-title">{tier_label}</span>
    </div>
    {f'<div class="deal-price">{price}</div>' if price else ''}
    <div class="deal-desc">{hood}{f' · {metro}' if metro else ''}{f' · {cuisine}' if cuisine else ''}</div>
    <div class="readiness-bar">
      <div class="readiness-label">Partner Readiness: {readiness}/100</div>
      <div class="readiness-track"><div class="readiness-fill" style="width:{readiness}%"></div></div>
    </div>
  </div>

  {quick_actions_html}

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('info')">Info</button>
    <button class="tab-btn" onclick="switchTab('map')">Map</button>
    <button class="tab-btn" onclick="switchTab('reviews')">Reviews{f' ({rating})' if rating else ''}</button>
    <button class="tab-btn" onclick="switchTab('nearby')">Nearby</button>
  </div>

  <!-- Tab: Info -->
  <div class="tab-content active" id="tab-info">
    {f'<div class="tags">{tag_html}</div>' if tags else ''}

    <div class="info-section">
      <h3>Details</h3>
      <div class="info-row"><span class="link-icon">📍</span> {hood}{f' · {address}' if address else ''}{f' · {postal}' if postal else ''}</div>
      <div class="info-row"><span class="link-icon">🍽️</span> {cuisine}{f' · ' + r.get("pricing_tier","") if r.get("pricing_tier") else ''}</div>
      {f'<div class="info-row"><span class="link-icon">🕐</span> {hours_lunch}</div>' if hours_lunch else ''}
      {f'<div class="info-row"><span class="link-icon">🚇</span> {metro}</div>' if metro else ''}
    </div>

    {f'<div class="notes">{notes}</div>' if notes else ''}

    {f'<div class="contact-links">{"".join(links)}</div>' if links else ''}

    <div class="share-section">
      <button class="share-btn" onclick="shareNative()">📤 Share</button>
      <button class="share-btn" onclick="copyLink(this)">🔗 Copy Link</button>
      <a class="share-btn" href="https://wa.me/?text={whatsapp_text}" target="_blank">💬 WhatsApp</a>
    </div>

    <div class="community">
      <button class="visited-btn" id="visit-btn" onclick="toggleVisited({r['id']})">☐ I've been here</button>
    </div>
  </div>

  <!-- Tab: Map -->
  {map_content}

  <!-- Tab: Reviews -->
  {reviews_content}

  <!-- Tab: Nearby -->
  {nearby_html}
</div>

<footer>
  <a href="../index.html">Menuverso</a> · <a href="../analytics.html">Market Intel</a> · <a href="../lists.html">Target Lists</a> · Restaurant #{r['id']} of {total_count:,}
</footer>

<script>
// Theme
function initTheme(){{
  var s=localStorage.getItem('menuverso_theme');
  if(s==='dark'||(!s&&window.matchMedia('(prefers-color-scheme:dark)').matches)){{
    document.documentElement.classList.add('dark');
    document.getElementById('theme-toggle').textContent='☀️';
  }}
}}
function toggleTheme(){{
  var d=document.documentElement.classList.toggle('dark');
  localStorage.setItem('menuverso_theme',d?'dark':'light');
  document.getElementById('theme-toggle').textContent=d?'☀️':'🌙';
}}

// Tabs
function switchTab(id){{
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+id).classList.add('active');
  event.target.classList.add('active');
  if(id==='map'&&window.m){{setTimeout(()=>m.invalidateSize(),100);}}
}}

// Share
function shareNative(){{
  if(navigator.share){{navigator.share({{title:'{name} — Menuverso',text:'{cuisine} in {hood}. {price}.',url:window.location.href}})}}
  else{{copyLink(document.querySelector('.share-btn'))}}
}}
function copyLink(btn){{
  navigator.clipboard.writeText(window.location.href).then(function(){{
    btn.textContent='✅ Copied!';setTimeout(function(){{btn.textContent='🔗 Copy Link'}},1500);
  }})
}}

// Open Now
(function(){{
  var hoursStr='{hours_lunch}';
  var el=document.getElementById('open-status');
  var txt=document.getElementById('open-text');
  if(!hoursStr||!hoursStr.trim()){{el.className='open-status unknown';txt.textContent='Hours unavailable';return;}}
  function checkOpen(){{
    var now=new Date();var h=now.getHours(),m=now.getMinutes();var nowMin=h*60+m;var dayOfWeek=now.getDay();
    var dayMatch=hoursStr.match(/\\(([^)]+)\\)/);
    if(dayMatch){{
      var dayStr=dayMatch[1].toLowerCase();
      var dayAbbr=['sun','mon','tue','wed','thu','fri','sat'];
      var dayAbbr2=['dom','lun','mar','mie','jue','vie','sab'];
      var rangeM=dayStr.match(/(\\w+)-(\\w+)/);
      if(rangeM){{
        var s=-1,e=-1;
        [dayAbbr,dayAbbr2].forEach(function(arr){{arr.forEach(function(d,i){{if(rangeM[1].startsWith(d))s=i;if(rangeM[2].startsWith(d))e=i;}});}});
        if(s>=0&&e>=0){{
          var inR=s<=e?(dayOfWeek>=s&&dayOfWeek<=e):(dayOfWeek>=s||dayOfWeek<=e);
          if(!inR){{el.className='open-status closed';txt.textContent='Closed today';return;}}
        }}
      }}
    }}
    var timeRanges=hoursStr.replace(/\\([^)]+\\)/g,'').match(/\\d{{1,2}}:\\d{{2}}\\s*-\\s*\\d{{1,2}}:\\d{{2}}/g);
    if(!timeRanges){{el.className='open-status unknown';txt.textContent='Hours unclear';return;}}
    var isOpen=false,closesAt=null;
    timeRanges.forEach(function(range){{
      var parts=range.split('-').map(function(s){{return s.trim();}});
      var sP=parts[0].split(':'),eP=parts[1].split(':');
      var sMin=parseInt(sP[0])*60+parseInt(sP[1]);var eMin=parseInt(eP[0])*60+parseInt(eP[1]);
      if(nowMin>=sMin&&nowMin<eMin){{isOpen=true;closesAt=parts[1];}}
    }});
    if(isOpen){{el.className='open-status open';txt.textContent='Open · closes '+closesAt;}}
    else{{el.className='open-status closed';txt.textContent='Closed';}}
  }}
  checkOpen();setInterval(checkOpen,60000);
}})();

// Visited
var visitKey='menuverso_visited';
function getVisited(){{return JSON.parse(localStorage.getItem(visitKey)||'{{}}');}}
function toggleVisited(id){{var v=getVisited();if(v[id]){{delete v[id]}}else{{v[id]=new Date().toISOString().slice(0,10)}};localStorage.setItem(visitKey,JSON.stringify(v));renderVisited(id);}}
function renderVisited(id){{var v=getVisited();var btn=document.getElementById('visit-btn');if(v[id]){{btn.classList.add('checked');btn.textContent='✅ Visited on '+v[id]}}else{{btn.classList.remove('checked');btn.textContent='☐ I have been here'}}}}

// Favorites (shared with app.html)
function toggleFav(id){{var favs=JSON.parse(localStorage.getItem('menuverso_favs')||'[]');var idx=favs.indexOf(id);if(idx>-1)favs.splice(idx,1);else favs.push(id);localStorage.setItem('menuverso_favs',JSON.stringify(favs));event.target.textContent=favs.includes(id)?'❤️ Saved':'❤️ Save';}}
(function(){{var favs=JSON.parse(localStorage.getItem('menuverso_favs')||'[]');var btns=document.querySelectorAll('[onclick*="toggleFav"]');btns.forEach(function(b){{if(favs.includes({r['id']}))b.textContent='❤️ Saved';}});}})();

initTheme();
renderVisited({r['id']});
</script>
{map_script}
</body>
</html>"""


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = len(restaurants)

    for r in restaurants:
        html = generate_page(r, restaurants, total)
        path = os.path.join(OUTPUT_DIR, f"{r['id']}.html")
        with open(path, "w") as f:
            f.write(html)

    # Generate sitemap
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/</loc><priority>1.0</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/analytics.html</loc><priority>0.9</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/lists.html</loc><priority>0.9</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/landing.html</loc><priority>1.0</priority></url>\n'
    for r in restaurants:
        sitemap += f'  <url><loc>https://whiteboxamir.github.io/menuverso/r/{r["id"]}.html</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>'

    with open("sitemap.xml", "w") as f:
        f.write(sitemap)

    print(f"🏗️  Generated {total} partnership pipeline restaurant profiles in /{OUTPUT_DIR}/")
    print(f"   Features: hero images, tabbed layout, readiness scores, dark mode, OG tags")
    print(f"📋 Generated sitemap.xml with {total + 4} URLs")


if __name__ == "__main__":
    main()
