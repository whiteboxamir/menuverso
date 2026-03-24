#!/usr/bin/env python3
"""
Menuverso Restaurant Page Generator — Creates individual HTML pages for each restaurant.
Major SEO benefit: 1,504 indexable pages instead of 1.
Each page has JSON-LD structured data for Google's restaurant rich results.
"""

import json
import os
from urllib.parse import quote_plus

INPUT = "restaurants.json"
OUTPUT_DIR = "r"  # /r/1.html, /r/2.html, etc.


def generate_page(r):
    """Generate a standalone HTML page for a restaurant."""
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

    tier_label = {"confirmed": "🟢 Menú del Día Confirmed", "likely": "🟡 Likely Menú del Día", "none": "🔴 No Menú del Día"}.get(tier, "")
    tier_color = {"confirmed": "#059669", "likely": "#D97706", "none": "#DC2626"}.get(tier, "#94A3B8")

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

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} — Menú del Día Barcelona | Menuverso</title>
<meta name="description" content="{name} in {hood}, Barcelona. {cuisine} cuisine. {price} menú del día. {tier_label}. Rating: {rating}/5 ({reviews} reviews).">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--bg:#F8FAFC;--card:#FFF;--text:#1E293B;--sub:#64748B;--border:#E2E8F0;--radius:12px;--shadow:0 2px 8px rgba(0,0,0,0.06);}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
.container{{max-width:700px;margin:0 auto;padding:2rem 1.5rem;}}
.back{{display:inline-flex;align-items:center;gap:6px;color:var(--sub);text-decoration:none;font-size:0.85rem;font-weight:500;margin-bottom:1.5rem;transition:color 0.2s;}}
.back:hover{{color:var(--text);}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:2rem;box-shadow:var(--shadow);}}
h1{{font-size:clamp(1.3rem,3vw,1.8rem);margin-bottom:0.5rem;}}
.badge{{display:inline-flex;padding:4px 10px;border-radius:6px;font-size:0.75rem;font-weight:600;margin-bottom:1rem;color:#fff;background:{tier_color};}}
.meta{{margin-bottom:1.5rem;}}
.meta-row{{display:flex;gap:0.5rem;align-items:center;font-size:0.88rem;color:var(--sub);margin-bottom:0.4rem;}}
.tags{{display:flex;flex-wrap:wrap;gap:0.3rem;margin-bottom:1.25rem;}}
.tag{{font-size:0.72rem;padding:3px 8px;border-radius:6px;background:#F1F5F9;color:#475569;border:1px solid #E2E8F0;}}
.price{{font-size:1.5rem;font-weight:700;color:var(--text);margin-bottom:0.25rem;}}
.notes{{font-size:0.88rem;color:var(--sub);line-height:1.6;padding:1rem;background:#F8FAFC;border-radius:8px;border:1px solid var(--border);margin-bottom:1.25rem;}}
.links{{display:flex;flex-wrap:wrap;gap:0.75rem;}}
.links a{{padding:0.5rem 1rem;border:1px solid var(--border);border-radius:8px;text-decoration:none;color:#2563EB;font-size:0.85rem;font-weight:500;transition:all 0.2s;}}
.links a:hover{{background:#EFF6FF;border-color:#93C5FD;}}
footer{{text-align:center;padding:2rem;color:#94A3B8;font-size:0.78rem;}}
footer a{{color:var(--sub);text-decoration:none;}}
</style>
</head>
<body>
<div class="container">
  <a href="../index.html" class="back">← Back to all restaurants</a>
  <div class="card">
    <h1>{name}</h1>
    <div class="badge">{tier_label}</div>
    <div class="meta">
      <div class="meta-row">📍 {hood}{f' · {address}' if address else ''}{f' · {postal}' if postal else ''}</div>
      <div class="meta-row">🍽️ {cuisine}{f' · {r.get("pricing_tier","")}' if r.get("pricing_tier") else ''}</div>
      {f'<div class="meta-row">⭐ {rating}/5 ({reviews} reviews)</div>' if rating else ''}
      {f'<div class="meta-row">🚇 {metro}</div>' if metro else ''}
    </div>
    {f'<div class="price">{price}</div><p style="font-size:0.78rem;color:var(--sub);margin-bottom:1.25rem;">Menú del día price range</p>' if price else ''}
    {f'<div class="tags">{tag_html}</div>' if tags else ''}
    {f'<div class="notes">{notes}</div>' if notes else ''}
    {f'<div class="links">{"".join(links)}</div>' if links else ''}
  </div>
</div>
<footer>
  <a href="../index.html">Menuverso</a> · <a href="../analytics.html">Analytics</a> · Restaurant #{r['id']} of 1,504
</footer>
</body>
</html>"""


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for r in restaurants:
        html = generate_page(r)
        path = os.path.join(OUTPUT_DIR, f"{r['id']}.html")
        with open(path, "w") as f:
            f.write(html)

    # Generate sitemap
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/</loc><priority>1.0</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/analytics.html</loc><priority>0.8</priority></url>\n'
    sitemap += '  <url><loc>https://whiteboxamir.github.io/menuverso/landing.html</loc><priority>0.9</priority></url>\n'
    for r in restaurants:
        sitemap += f'  <url><loc>https://whiteboxamir.github.io/menuverso/r/{r["id"]}.html</loc><priority>0.6</priority></url>\n'
    sitemap += '</urlset>'

    with open("sitemap.xml", "w") as f:
        f.write(sitemap)

    print(f"🏗️  Generated {len(restaurants)} restaurant pages in /{OUTPUT_DIR}/")
    print(f"📋 Generated sitemap.xml with {len(restaurants)+3} URLs")
    print(f"   Example: /r/1.html (Casa Jaime)")


if __name__ == "__main__":
    main()
