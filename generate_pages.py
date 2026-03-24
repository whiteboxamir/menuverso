#!/usr/bin/env python3
"""
Menuverso Restaurant Page Generator — Enhanced Edition
Creates individual HTML pages for each restaurant with:
- Mini Leaflet map (if geocoded)
- Nearby restaurants section (3 closest by coordinates)
- Share buttons (Web Share API + WhatsApp + clipboard)
- Dark mode support
- Open Graph meta tags
- JSON-LD structured data
"""

import json
import os
import math
from urllib.parse import quote_plus, quote

INPUT = "restaurants.json"
OUTPUT_DIR = "r"


def haversine(lat1, lng1, lat2, lng2):
    """Distance in km between two lat/lng points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def find_nearby(restaurant, all_restaurants, n=3):
    """Find n nearest restaurants by coordinates."""
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


def build_reviews_html(rating, reviews, maps_url):
    """Build a visual Google Reviews card."""
    if not rating:
        return ""
    rating_f = float(rating)
    full_stars = int(rating_f)
    half = 1 if rating_f - full_stars >= 0.3 else 0
    empty = 5 - full_stars - half
    star_html = ''.join(['<span class="star">★</span>'] * full_stars)
    if half:
        star_html += '<span class="star">★</span>'  # close enough
    star_html += ''.join(['<span class="star empty">★</span>'] * empty)
    maps_link = f'<a href="{maps_url}" target="_blank" style="color:var(--accent);font-size:0.72rem;text-decoration:none;font-weight:500;">View on Google Maps →</a>' if maps_url else ''
    return f'''<div class="reviews-card">
      <div class="reviews-header">
        <div class="reviews-score">{rating}</div>
        <div>
          <div class="reviews-stars">{star_html}</div>
          <div class="reviews-count">{reviews:,} Google reviews</div>
        </div>
      </div>
      <div class="reviews-source">📍 Source: Google Maps {maps_link}</div>
    </div>'''


def generate_page(r, all_restaurants, total_count):
    """Generate an enhanced standalone HTML page for a restaurant."""
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

    tier_label = {"confirmed": "🟢 Menú del Día Confirmed", "likely": "🟡 Likely Menú del Día", "none": "🔴 No Menú del Día"}.get(tier, "")
    tier_color = {"confirmed": "#059669", "likely": "#D97706", "none": "#DC2626"}.get(tier, "#94A3B8")

    page_url = f"https://whiteboxamir.github.io/menuverso/r/{r['id']}.html"
    whatsapp_text = quote(f"Check out {name} in {hood}, Barcelona! {price} menú del día. {page_url}")

    # Build JSON-LD
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": name,
        "address": {"@type": "PostalAddress", "streetAddress": address, "addressLocality": "Barcelona", "postalCode": postal, "addressCountry": "ES"},
        "servesCuisine": cuisine,
    }
    if rating:
        jsonld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": rating, "reviewCount": reviews}
    if phone:
        jsonld["telephone"] = phone
    if website:
        jsonld["url"] = website
    if price:
        jsonld["priceRange"] = price
    if has_coords:
        jsonld["geo"] = {"@type": "GeoCoordinates", "latitude": coords["lat"], "longitude": coords["lng"]}

    links = []
    if website:
        links.append(f'<a href="{website}" target="_blank">🌐 Website</a>')
    if maps_url:
        links.append(f'<a href="{maps_url}" target="_blank">📍 Google Maps</a>')
    if phone:
        links.append(f'<a href="tel:{phone}">📞 {phone}</a>')
    if instagram:
        links.append(f'<a href="https://instagram.com/{instagram.replace("@","")}" target="_blank">📸 {instagram}</a>')

    tag_html = "".join(f'<span class="tag">{t}</span>' for t in tags)

    # Nearby restaurants
    nearby = find_nearby(r, all_restaurants)
    nearby_html = ""
    if nearby:
        nearby_cards = []
        for dist, nr in nearby:
            nt = nr.get("menu_tier", "none")
            nc = {"confirmed": "#059669", "likely": "#D97706", "none": "#DC2626"}.get(nt, "#94A3B8")
            nl = {"confirmed": "🟢", "likely": "🟡", "none": "🔴"}.get(nt, "")
            dist_m = int(dist * 1000)
            dist_str = f"{dist_m}m" if dist_m < 1000 else f"{dist:.1f}km"
            nearby_cards.append(f'''<a href="{nr['id']}.html" class="nearby-card">
          <div class="nearby-name">{nr['name']}</div>
          <div class="nearby-meta">{nl} {nr.get('cuisine_type','')} · {nr.get('menu_price_range','—')} · {dist_str}</div>
        </a>''')
        nearby_html = f'''<div class="nearby">
      <h2>📍 Nearby Restaurants</h2>
      {''.join(nearby_cards)}
    </div>'''

    # Map HTML
    map_html = ""
    map_script = ""
    leaflet_css = ""
    leaflet_js = ""
    if has_coords:
        leaflet_css = '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />'
        leaflet_js = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></' + 'script>'
        map_html = '<div id="minimap"></div>'
        map_script = f'''<script>
var m=L.map('minimap',{{zoomControl:false,scrollWheelZoom:false,dragging:false}}).setView([{coords["lat"]},{coords["lng"]}],16);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{maxZoom:19}}).addTo(m);
L.circleMarker([{coords["lat"]},{coords["lng"]}],{{radius:8,fillColor:'{tier_color}',color:'#fff',weight:2,fillOpacity:1}}).addTo(m);
if(document.documentElement.classList.contains('dark')){{document.querySelectorAll('.leaflet-tile').forEach(t=>t.style.filter='invert(1) hue-rotate(180deg) brightness(0.9)');}};
</script>'''

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — Menú del Día Barcelona | Menuverso</title>
<meta name="description" content="{name} in {hood}, Barcelona. {cuisine} cuisine. {price} menú del día. {tier_label}. Rating: {rating}/5 ({reviews} reviews).">
<meta property="og:title" content="{name} — Menú del Día | Menuverso">
<meta property="og:description" content="{cuisine} in {hood}. {price} menú del día. {'⭐ '+str(rating)+'/5' if rating else ''}">
<meta property="og:url" content="{page_url}">
<meta property="og:type" content="restaurant.restaurant">
<meta property="og:site_name" content="Menuverso">
<meta name="twitter:card" content="summary">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
{leaflet_css}
{leaflet_js}
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--bg:#F8FAFC;--card:#FFF;--text:#1E293B;--sub:#64748B;--mut:#94A3B8;--border:#E2E8F0;--accent:#2563EB;--accent-sub:#DBEAFE;--radius:12px;--shadow:0 2px 8px rgba(0,0,0,0.06);}}
:root.dark{{--bg:#0F172A;--card:#1E293B;--text:#F1F5F9;--sub:#94A3B8;--mut:#64748B;--border:#334155;--accent:#3B82F6;--accent-sub:#1E3A5F;--shadow:0 2px 8px rgba(0,0,0,0.3);}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background 0.3s,color 0.3s;}}
.topnav{{display:flex;align-items:center;justify-content:space-between;padding:0.6rem 1.5rem;border-bottom:1px solid var(--border);background:var(--card);position:sticky;top:0;z-index:100;backdrop-filter:blur(12px);}}
.nav-brand{{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);font-weight:700;font-size:1.1rem;}}
.nav-brand img{{width:28px;height:28px;border-radius:8px;}}
.nav-links{{display:flex;align-items:center;gap:1rem;}}
.nav-links a{{color:var(--sub);text-decoration:none;font-size:0.82rem;font-weight:500;padding:0.3rem 0.5rem;border-radius:8px;transition:all 0.2s;}}
.nav-links a:hover{{color:var(--text);background:var(--accent-sub);}}
.controls-bar{{display:flex;gap:0.5rem;align-items:center;}}
.theme-btn{{background:none;border:1px solid var(--border);border-radius:20px;padding:0.3rem 0.55rem;cursor:pointer;font-size:0.85rem;color:var(--sub);transition:all 0.2s;}}
.theme-btn:hover{{border-color:var(--sub);color:var(--text);}}
.container{{max-width:700px;margin:0 auto;padding:1.5rem;}}
.back{{display:inline-flex;align-items:center;gap:6px;color:var(--sub);text-decoration:none;font-size:0.85rem;font-weight:500;margin-bottom:1.5rem;transition:color 0.2s;}}
.back:hover{{color:var(--text);}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:2rem;box-shadow:var(--shadow);}}
h1{{font-size:clamp(1.3rem,3vw,1.8rem);margin-bottom:0.5rem;}}
.badge{{display:inline-flex;padding:4px 10px;border-radius:6px;font-size:0.75rem;font-weight:600;margin-bottom:1rem;color:#fff;background:{tier_color};}}
.meta{{margin-bottom:1.5rem;}}
.meta-row{{display:flex;gap:0.5rem;align-items:center;font-size:0.88rem;color:var(--sub);margin-bottom:0.4rem;}}
.tags{{display:flex;flex-wrap:wrap;gap:0.3rem;margin-bottom:1.25rem;}}
.tag{{font-size:0.72rem;padding:3px 8px;border-radius:6px;background:var(--accent-sub);color:var(--accent);border:1px solid var(--border);font-weight:500;}}
.price{{font-size:1.5rem;font-weight:700;color:var(--text);margin-bottom:0.25rem;}}
.notes{{font-size:0.88rem;color:var(--sub);line-height:1.6;padding:1rem;background:var(--bg);border-radius:8px;border:1px solid var(--border);margin-bottom:1.25rem;}}
.links{{display:flex;flex-wrap:wrap;gap:0.75rem;margin-bottom:1.25rem;}}
.links a{{padding:0.5rem 1rem;border:1px solid var(--border);border-radius:8px;text-decoration:none;color:var(--accent);font-size:0.85rem;font-weight:500;transition:all 0.2s;}}
.links a:hover{{background:var(--accent-sub);border-color:var(--accent);}}
/* Open Now badge */
.open-status{{display:inline-flex;align-items:center;gap:5px;padding:0.35rem 0.85rem;border-radius:20px;font-size:0.78rem;font-weight:600;transition:all 0.3s;}}
.open-status.open{{background:#D1FAE5;color:#059669;border:1px solid #A7F3D0;}}
.open-status.closed{{background:#FEE2E2;color:#DC2626;border:1px solid #FECACA;}}
.open-status.unknown{{background:var(--bg);color:var(--sub);border:1px solid var(--border);}}
:root.dark .open-status.open{{background:#064E3B;color:#34D399;border-color:#065F46;}}
:root.dark .open-status.closed{{background:#7F1D1D;color:#F87171;border-color:#991B1B;}}
.open-dot{{width:8px;height:8px;border-radius:50%;}}
.open .open-dot{{background:#059669;animation:pulse-green 2s infinite;}}
.closed .open-dot{{background:#DC2626;}}
@keyframes pulse-green{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:0.6;transform:scale(1.3);}}}}
/* Google Reviews card */
.reviews-card{{padding:1.25rem;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:1.25rem;}}
.reviews-header{{display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem;}}
.reviews-score{{font-size:2rem;font-weight:700;color:var(--text);line-height:1;}}
.reviews-stars{{display:flex;gap:1px;}}
.reviews-stars .star{{color:#FBBF24;font-size:1.1rem;}}
.reviews-stars .star.empty{{color:var(--border);}}
.reviews-count{{font-size:0.82rem;color:var(--sub);font-weight:500;}}
.reviews-source{{font-size:0.72rem;color:var(--mut);margin-top:0.5rem;display:flex;align-items:center;gap:4px;}}
/* Share */
.share{{display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.25rem;}}
.share-btn{{padding:0.45rem 0.9rem;border:1px solid var(--border);border-radius:8px;background:var(--card);color:var(--sub);font-size:0.8rem;font-weight:500;cursor:pointer;transition:all 0.2s;font-family:Inter,sans-serif;display:inline-flex;align-items:center;gap:4px;}}
.share-btn:hover{{border-color:var(--accent);color:var(--accent);background:var(--accent-sub);}}
.share-btn.whatsapp:hover{{border-color:#25D366;color:#25D366;}}
/* QR Code */
.qr-section{{margin-top:1.25rem;padding:1.25rem;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);text-align:center;}}
.qr-section h3{{font-size:0.82rem;color:var(--sub);font-weight:600;margin-bottom:0.75rem;}}
#qrcode{{display:inline-block;padding:12px;background:#fff;border-radius:8px;margin-bottom:0.5rem;}}
.qr-section small{{display:block;color:var(--mut);font-size:0.72rem;}}
/* Visited & Tips */
.community{{margin-top:1.25rem;display:flex;flex-direction:column;gap:0.75rem;}}
.visited-btn{{padding:0.6rem 1rem;border:2px solid var(--border);border-radius:8px;background:var(--card);color:var(--sub);font-size:0.85rem;font-weight:600;cursor:pointer;transition:all 0.2s;font-family:Inter,sans-serif;display:flex;align-items:center;gap:8px;width:100%;}}
.visited-btn:hover{{border-color:var(--green);}}
.visited-btn.checked{{border-color:var(--green);background:var(--green-bg);color:var(--green);}}
.tips-box{{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;}}
.tips-box h3{{font-size:0.82rem;color:var(--sub);font-weight:600;margin-bottom:0.5rem;}}
.tip-list{{display:flex;flex-direction:column;gap:0.4rem;margin-bottom:0.5rem;}}
.tip-item{{font-size:0.82rem;padding:0.4rem 0.6rem;background:var(--card);border-radius:6px;border:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}}
.tip-text{{flex:1;}}
.tip-delete{{background:none;border:none;color:var(--mut);cursor:pointer;font-size:0.7rem;padding:2px;}}
.tip-delete:hover{{color:var(--red);}}
.tip-input{{display:flex;gap:0.4rem;}}
.tip-input input{{flex:1;padding:0.4rem 0.6rem;border:1px solid var(--border);border-radius:6px;font-size:0.8rem;font-family:Inter,sans-serif;background:var(--card);color:var(--text);}}
.tip-input input:focus{{outline:none;border-color:var(--accent);}}
.tip-input button{{padding:0.4rem 0.8rem;border:1px solid var(--accent);border-radius:6px;background:var(--accent);color:#fff;font-size:0.78rem;font-weight:600;cursor:pointer;font-family:Inter,sans-serif;}}
/* Mini map */
#minimap{{width:100%;height:200px;border-radius:var(--radius);border:1px solid var(--border);margin-bottom:1.25rem;z-index:1;}}
:root.dark .leaflet-tile{{filter:invert(1) hue-rotate(180deg) brightness(0.9) contrast(0.9);}}
/* Nearby */
.nearby{{margin-top:0.5rem;}}
.nearby h2{{font-size:0.9rem;font-weight:600;color:var(--sub);margin-bottom:0.75rem;}}
.nearby-card{{display:block;padding:0.75rem 1rem;border:1px solid var(--border);border-radius:8px;margin-bottom:0.5rem;text-decoration:none;color:var(--text);transition:all 0.2s;}}
.nearby-card:hover{{border-color:var(--accent);transform:translateX(4px);background:var(--accent-sub);}}
.nearby-name{{font-weight:600;font-size:0.9rem;margin-bottom:2px;}}
.nearby-meta{{font-size:0.78rem;color:var(--sub);}}
footer{{text-align:center;padding:2rem;color:var(--mut);font-size:0.78rem;}}
footer a{{color:var(--sub);text-decoration:none;}}
img[src*="logo.png"]{{mix-blend-mode:multiply;}}
:root.dark img[src*="logo.png"]{{mix-blend-mode:normal;filter:brightness(1.2);}}
@media(max-width:640px){{.nav-links a span{{display:none;}}}}
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
    <a href="../finder.html"><span>🔍 </span>Finder</a>
    <a href="../analytics.html"><span>📊 </span>Analytics</a>
    <a href="../lists.html"><span>🏆 </span>Best Of</a>
    <a href="../crawl.html"><span>🚶 </span>Crawl</a>
  </div>
  <div class="controls-bar">
    <button class="theme-btn" id="theme-toggle" onclick="toggleTheme()" title="Toggle dark mode">🌙</button>
  </div>
</nav>
<div class="container">
  <a href="../index.html?hood={quote_plus(hood)}" class="back">← {hood} restaurants</a>
  <div class="card">
    <h1>{name}</h1>
    <div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;margin-bottom:0.75rem;">
      <div class="badge">{tier_label}</div>
      <div class="open-status unknown" id="open-status"><span class="open-dot"></span> <span id="open-text">Checking...</span></div>
    </div>
    <div class="meta">
      <div class="meta-row">📍 {hood}{f' · {address}' if address else ''}{f' · {postal}' if postal else ''}</div>
      <div class="meta-row">🍽️ {cuisine}{f' · {r.get("pricing_tier","")}' if r.get("pricing_tier") else ''}</div>
      {f'<div class="meta-row">🕐 {hours_lunch}</div>' if hours_lunch else ''}
      {f'<div class="meta-row">🚇 {metro}</div>' if metro else ''}
    </div>
    {f'<div class="price">{price}</div><p style="font-size:0.78rem;color:var(--sub);margin-bottom:1.25rem;">Menú del día price range</p>' if price else ''}
    {f'<div class="tags">{tag_html}</div>' if tags else ''}
    {build_reviews_html(rating, reviews, maps_url)}
    {f'<div class="notes">{notes}</div>' if notes else ''}
    {f'<div class="links">{"".join(links)}</div>' if links else ''}
    <div class="share">
      <button class="share-btn" onclick="shareNative()">📤 Share</button>
      <button class="share-btn" onclick="copyLink()">🔗 Copy Link</button>
      <a class="share-btn whatsapp" href="https://wa.me/?text={whatsapp_text}" target="_blank">💬 WhatsApp</a>
    </div>
    {map_html}
    <div class="qr-section">
      <h3>📱 QR Code — Scan to Share</h3>
      <div id="qrcode"></div>
      <small>Print this on your restaurant window or share with friends</small>
    </div>
    {nearby_html}
    <div class="community">
      <button class="visited-btn" id="visit-btn" onclick="toggleVisited({r['id']})">☐ I've been here</button>
      <div class="tips-box">
        <h3>💡 Quick Tips</h3>
        <div class="tip-list" id="tip-list"></div>
        <div class="tip-input">
          <input type="text" id="tip-input" placeholder="Add a tip... e.g. 'Ask for the paella!'" maxlength="120">
          <button onclick="addTip({r['id']})">Add</button>
        </div>
      </div>
    </div>
  </div>
</div>
<footer>
  <a href="../index.html">Menuverso</a> · <a href="../finder.html">Finder</a> · <a href="../analytics.html">Analytics</a> · Restaurant #{r['id']} of {total_count:,}
</footer>
<script>
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
function shareNative(){{
  if(navigator.share){{navigator.share({{title:'{name} — Menuverso',text:'{cuisine} in {hood}. {price} menú del día.',url:window.location.href}})}}
  else{{copyLink()}}
}}
function copyLink(){{
  navigator.clipboard.writeText(window.location.href).then(function(){{
    var b=event.target;b.textContent='✅ Copied!';setTimeout(function(){{b.textContent='🔗 Copy Link'}},1500);
  }})
}}
// Open Now logic
(function(){{
  var hoursStr='{hours_lunch}';
  var el=document.getElementById('open-status');
  var txt=document.getElementById('open-text');
  if(!hoursStr||!hoursStr.trim()){{el.className='open-status unknown';txt.textContent='Hours unavailable';return;}}
  function checkOpen(){{
    var now=new Date();
    var h=now.getHours(),m=now.getMinutes();
    var nowMin=h*60+m;
    var dayOfWeek=now.getDay();
    var dayMatch=hoursStr.match(/\(([^)]+)\)/);
    if(dayMatch){{
      var dayStr=dayMatch[1].toLowerCase();
      var dayAbbr=['sun','mon','tue','wed','thu','fri','sat'];
      var dayAbbr2=['dom','lun','mar','mie','jue','vie','sab'];
      var rangeM=dayStr.match(/(\w+)-(\w+)/);
      if(rangeM){{
        var s=-1,e=-1;
        [dayAbbr,dayAbbr2].forEach(function(arr){{
          arr.forEach(function(d,i){{if(rangeM[1].startsWith(d))s=i;if(rangeM[2].startsWith(d))e=i;}});
        }});
        if(s>=0&&e>=0){{
          var inR=s<=e?(dayOfWeek>=s&&dayOfWeek<=e):(dayOfWeek>=s||dayOfWeek<=e);
          if(!inR){{el.className='open-status closed';txt.textContent='Closed today';return;}}
        }}
      }}
    }}
    var timeRanges=hoursStr.replace(/\([^)]+\)/g,'').match(/\d{{1,2}}:\d{{2}}\s*-\s*\d{{1,2}}:\d{{2}}/g);
    if(!timeRanges){{el.className='open-status unknown';txt.textContent='Hours unclear';return;}}
    var isOpen=false,closesAt=null,nextOpen=null;
    timeRanges.forEach(function(range){{
      var parts=range.split('-').map(function(s){{return s.trim();}});
      var sP=parts[0].split(':'),eP=parts[1].split(':');
      var sMin=parseInt(sP[0])*60+parseInt(sP[1]);
      var eMin=parseInt(eP[0])*60+parseInt(eP[1]);
      if(nowMin>=sMin&&nowMin<eMin){{isOpen=true;closesAt=parts[1];}}
      else if(nowMin<sMin&&(!nextOpen||sMin<nextOpen)){{nextOpen=sMin;}}
    }});
    if(isOpen){{el.className='open-status open';txt.textContent='Open now · closes '+closesAt;}}
    else{{el.className='open-status closed';if(nextOpen){{var nh=Math.floor(nextOpen/60),nm=nextOpen%60;txt.textContent='Closed · opens '+(nh<10?'0':'')+nh+':'+(nm<10?'0':'')+nm;}}else{{txt.textContent='Closed now';}}}}
  }}
  checkOpen();
  setInterval(checkOpen,60000);
}})();
initTheme();
// Visited tracker
var visitKey='menuverso_visited';
function getVisited(){{return JSON.parse(localStorage.getItem(visitKey)||'{{}}');}}
function toggleVisited(id){{
  var v=getVisited();
  if(v[id]){{delete v[id];}}else{{v[id]=new Date().toISOString().slice(0,10);}}
  localStorage.setItem(visitKey,JSON.stringify(v));
  renderVisited(id);
}}
function renderVisited(id){{
  var v=getVisited();
  var btn=document.getElementById('visit-btn');
  if(v[id]){{btn.classList.add('checked');btn.textContent='✅ Visited on '+v[id];}}
  else{{btn.classList.remove('checked');btn.textContent='☐ I\'ve been here';}}
}}
// Tips
var tipKey='menuverso_tips';
function getTips(){{return JSON.parse(localStorage.getItem(tipKey)||'{{}}');}}
function addTip(id){{
  var inp=document.getElementById('tip-input');
  var text=inp.value.trim();
  if(!text)return;
  var tips=getTips();
  if(!tips[id])tips[id]=[];
  tips[id].push(text);
  localStorage.setItem(tipKey,JSON.stringify(tips));
  inp.value='';
  renderTips(id);
}}
function deleteTip(id,i){{
  var tips=getTips();
  if(tips[id]){{tips[id].splice(i,1);localStorage.setItem(tipKey,JSON.stringify(tips));}}
  renderTips(id);
}}
function renderTips(id){{
  var tips=getTips();
  var list=document.getElementById('tip-list');
  var items=tips[id]||[];
  list.innerHTML=items.map(function(t,i){{return '<div class="tip-item"><span class="tip-text">💡 '+t+'</span><button class="tip-delete" onclick="deleteTip('+id+','+i+')">✕</button></div>'}}).join('');
}}
renderVisited({r['id']});
renderTips({r['id']});
</script>
<script src="https://cdn.jsdelivr.net/npm/qrcodejs@1.0.0/qrcode.min.js"></script>
<script>try{{new QRCode(document.getElementById('qrcode'),{{text:'{page_url}',width:128,height:128,colorDark:'#1E293B',colorLight:'#ffffff',correctLevel:QRCode.CorrectLevel.M}})}}catch(e){{}}</script>
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
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/finder.html</loc><priority>0.9</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/analytics.html</loc><priority>0.8</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/lists.html</loc><priority>0.9</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/collections.html</loc><priority>0.7</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/crawl.html</loc><priority>0.7</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/landing.html</loc><priority>0.9</priority></url>\n'
    for r in restaurants:
        sitemap += f'  <url><loc>https://whiteboxamir.github.io/menuverso/r/{r["id"]}.html</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>'

    with open("sitemap.xml", "w") as f:
        f.write(sitemap)

    print(f"🏗️  Generated {total} enhanced restaurant pages in /{OUTPUT_DIR}/")
    print(f"   Features: mini-map, nearby restaurants, share + QR, dark mode, OG tags")
    print(f"📋 Generated sitemap.xml with {total + 7} URLs")
    print(f"   Example: /r/1.html (Casa Jaime)")


if __name__ == "__main__":
    main()
