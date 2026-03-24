#!/usr/bin/env python3
"""
Menuverso Neighborhood Deep-Dive Generator
Creates standalone pages per neighborhood with:
- Stats overview (total, avg price, avg rating, confirmed %)
- Top 5 restaurants
- Cuisine breakdown
- Mini Leaflet map with all neighborhood restaurants
- Links to Best Of and database filtered views
"""

import json
import os
import re
from urllib.parse import quote_plus


INPUT = "restaurants.json"
OUTPUT_DIR = "n"


def parse_price(s):
    if not s:
        return None
    nums = re.findall(r'[\d.]+', s)
    return float(nums[0]) if nums else None


def generate_neighborhood_page(hood, restaurants, all_hoods, total_count):
    slug = hood.lower().replace(" ", "-").replace("'", "").replace("ò", "o").replace("à", "a").replace("í", "i")
    total = len(restaurants)
    confirmed = sum(1 for r in restaurants if r.get("menu_tier") == "confirmed")
    likely = sum(1 for r in restaurants if r.get("menu_tier") == "likely")
    prices = [parse_price(r.get("menu_price_range")) for r in restaurants if parse_price(r.get("menu_price_range"))]
    avg_price = sum(prices) / len(prices) if prices else 0
    ratings = [r["google_maps_rating"] for r in restaurants if r.get("google_maps_rating")]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0
    with_coords = [r for r in restaurants if r.get("coordinates", {}).get("lat")]

    # Top 5
    top5 = sorted([r for r in restaurants if r.get("google_maps_rating")],
                   key=lambda r: (-r["google_maps_rating"], -r.get("google_maps_review_count", 0)))[:5]
    top5_html = ""
    for i, r in enumerate(top5):
        tier_e = {"confirmed": "🟢", "likely": "🟡", "none": "🔴"}.get(r.get("menu_tier", "none"), "")
        rank_cl = ["gold", "silver", "bronze"][i] if i < 3 else ""
        top5_html += f'''<a href="../r/{r["id"]}.html" class="top-card">
          <div class="rank {rank_cl}">{i+1}</div>
          <div class="tc-body">
            <div class="tc-name">{r["name"]}</div>
            <div class="tc-meta">{tier_e} {r.get("cuisine_type","")} · {r.get("menu_price_range","—")} · ⭐ {r.get("google_maps_rating","")}/5</div>
          </div>
        </a>'''

    # Cuisine breakdown
    cuisines = {}
    for r in restaurants:
        c = r.get("cuisine_type", "Other")
        cuisines[c] = cuisines.get(c, 0) + 1
    cuisine_items = sorted(cuisines.items(), key=lambda x: -x[1])[:8]
    cuisine_html = "".join(f'<div class="cb-item"><span class="cb-name">{c}</span><span class="cb-count">{n}</span></div>' for c, n in cuisine_items)

    # Budget breakdown
    budget_count = sum(1 for r in restaurants if r.get("pricing_tier") == "budget")
    mid_count = sum(1 for r in restaurants if r.get("pricing_tier") == "mid-range")
    premium_count = sum(1 for r in restaurants if r.get("pricing_tier") == "premium")

    # Map markers JSON
    markers_json = json.dumps([[r["coordinates"]["lat"], r["coordinates"]["lng"], r["name"],
                                 r.get("menu_tier", "none"), r["id"]] for r in with_coords])

    # Other neighborhoods links
    def make_slug(name):
        return name.lower().replace(" ", "-").replace("'", "").replace("ò", "o").replace("à", "a").replace("í", "i")

    other_hoods_items = [(h, c, make_slug(h)) for h, c in sorted(all_hoods.items()) if h != hood]
    other_hoods_html = "".join(
        f'<a href="{s}.html" class="hood-link">{h} <span>({c})</span></a>'
        for h, c, s in other_hoods_items
    )

    sc = '</scr' + 'ipt>'

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{hood} Restaurants — Menuverso Barcelona</title>
<meta name="description" content="{hood}: {total} restaurants, avg €{avg_price:.0f} menú del día, {confirmed} confirmed. Best of {hood} in Barcelona by Menuverso.">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">{sc}
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--bg:#F8FAFC;--card:#FFF;--text:#1E293B;--sub:#64748B;--mut:#94A3B8;--border:#E2E8F0;--accent:#2563EB;--accent-sub:#DBEAFE;--green:#059669;--green-bg:#D1FAE5;--amber:#D97706;--red:#DC2626;--radius:12px;--shadow:0 2px 8px rgba(0,0,0,0.06);}}
:root.dark{{--bg:#0F172A;--card:#1E293B;--text:#F1F5F9;--sub:#94A3B8;--mut:#64748B;--border:#334155;--accent:#3B82F6;--accent-sub:#1E3A5F;--green:#34D399;--green-bg:#064E3B;--shadow:0 2px 8px rgba(0,0,0,0.3);}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background 0.3s,color 0.3s;}}
.topnav{{display:flex;align-items:center;justify-content:space-between;padding:0.6rem 1.5rem;border-bottom:1px solid var(--border);background:var(--card);position:sticky;top:0;z-index:100;backdrop-filter:blur(12px);}}
.nav-brand{{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);font-weight:700;font-size:1.1rem;}}
.nav-brand img{{width:28px;height:28px;border-radius:8px;}}
.nav-links{{display:flex;align-items:center;gap:1rem;}}
.nav-links a{{color:var(--sub);text-decoration:none;font-size:0.82rem;font-weight:500;padding:0.3rem 0.5rem;border-radius:8px;transition:all 0.2s;}}
.nav-links a:hover{{color:var(--text);}}
.controls-bar{{display:flex;gap:0.5rem;align-items:center;}}
.theme-btn{{background:none;border:1px solid var(--border);border-radius:20px;padding:0.3rem 0.55rem;cursor:pointer;font-size:0.85rem;color:var(--sub);transition:all 0.2s;}}
.container{{max-width:800px;margin:0 auto;padding:1.5rem;}}
.back{{display:inline-flex;align-items:center;gap:6px;color:var(--sub);text-decoration:none;font-size:0.85rem;font-weight:500;margin-bottom:1rem;transition:color 0.2s;}}
.back:hover{{color:var(--text);}}
.hero{{text-align:center;margin-bottom:2rem;}}
.hero h1{{font-size:clamp(1.5rem,4vw,2.2rem);margin-bottom:0.25rem;}}
.hero p{{color:var(--sub);font-size:0.9rem;}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0.75rem;margin-bottom:2rem;}}
.stat{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;text-align:center;box-shadow:var(--shadow);}}
.stat-num{{font-size:1.3rem;font-weight:700;}}
.stat-label{{font-size:0.7rem;color:var(--mut);text-transform:uppercase;letter-spacing:0.04em;margin-top:2px;}}
.green{{color:var(--green);}} .amber{{color:var(--amber);}} .red{{color:var(--red);}}
.section{{margin-bottom:2rem;}}
.section-title{{font-size:0.75rem;text-transform:uppercase;letter-spacing:0.06em;font-weight:600;color:var(--mut);margin-bottom:0.75rem;}}
.top-card{{display:flex;gap:0.75rem;align-items:center;padding:0.75rem 1rem;background:var(--card);border:1px solid var(--border);border-radius:8px;margin-bottom:0.5rem;text-decoration:none;color:var(--text);transition:all 0.2s;box-shadow:var(--shadow);}}
.top-card:hover{{transform:translateY(-1px);border-color:var(--accent);}}
.rank{{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.8rem;background:var(--accent-sub);color:var(--accent);flex-shrink:0;}}
.rank.gold{{background:#FEF3C7;color:#D97706;}} .rank.silver{{background:#F1F5F9;color:#64748B;}} .rank.bronze{{background:#FED7AA;color:#C2410C;}}
.tc-body{{flex:1;min-width:0;}}
.tc-name{{font-weight:600;font-size:0.9rem;}}
.tc-meta{{font-size:0.75rem;color:var(--sub);}}
#hood-map{{width:100%;height:300px;border-radius:var(--radius);border:1px solid var(--border);margin-bottom:1rem;z-index:1;}}
:root.dark .leaflet-tile{{filter:invert(1) hue-rotate(180deg) brightness(0.9) contrast(0.9);}}
.cb-item{{display:flex;justify-content:space-between;padding:0.4rem 0.75rem;font-size:0.85rem;border-bottom:1px solid var(--border);}}
.cb-item:last-child{{border-bottom:none;}}
.cb-name{{font-weight:500;}} .cb-count{{color:var(--sub);font-size:0.8rem;}}
.cuisine-box{{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow);}}
.actions{{display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:2rem;}}
.btn{{padding:0.5rem 1rem;border:1px solid var(--border);border-radius:8px;background:var(--card);color:var(--text);font-size:0.82rem;font-weight:600;cursor:pointer;text-decoration:none;transition:all 0.2s;font-family:Inter,sans-serif;display:inline-flex;align-items:center;gap:4px;}}
.btn:hover{{border-color:var(--accent);color:var(--accent);}}
.btn.primary{{background:var(--accent);color:#fff;border-color:var(--accent);}}
.hood-links{{display:flex;flex-wrap:wrap;gap:0.4rem;}}
.hood-link{{padding:0.3rem 0.65rem;border:1px solid var(--border);border-radius:16px;font-size:0.72rem;font-weight:500;color:var(--sub);text-decoration:none;transition:all 0.2s;}}
.hood-link:hover{{border-color:var(--accent);color:var(--accent);}}
.hood-link span{{color:var(--mut);}}
footer{{text-align:center;padding:2rem;color:var(--mut);font-size:0.78rem;border-top:1px solid var(--border);}}
footer a{{color:var(--sub);text-decoration:none;}}
img[src*="logo.png"]{{mix-blend-mode:multiply;}}
:root.dark img[src*="logo.png"]{{mix-blend-mode:normal;filter:brightness(1.2);}}
@media(max-width:640px){{.stats{{grid-template-columns:repeat(3,1fr);}}.nav-links a span{{display:none;}}.actions{{flex-direction:column;}}}}
</style>
</head>
<body>
<nav class="topnav">
  <a href="../index.html" class="nav-brand"><img src="../assets/logo.png" alt="Menuverso"><span>Menuverso</span></a>
  <div class="nav-links">
    <a href="../index.html"><span>📋 </span>Database</a>
    <a href="../finder.html"><span>🔍 </span>Finder</a>
    <a href="../analytics.html"><span>📊 </span>Analytics</a>
    <a href="../lists.html"><span>🏆 </span>Best Of</a>
    <a href="../crawl.html"><span>🚶 </span>Crawl</a>
  </div>
  <div class="controls-bar"><button class="theme-btn" id="theme-toggle" onclick="toggleTheme()">🌙</button></div>
</nav>
<div class="container">
  <a href="../index.html" class="back">← All Neighborhoods</a>
  <div class="hero">
    <h1>📍 {hood}</h1>
    <p>{total} restaurants · {confirmed} confirmed menú del día</p>
  </div>

  <div class="stats">
    <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Restaurants</div></div>
    <div class="stat"><div class="stat-num green">{confirmed}</div><div class="stat-label">Confirmed</div></div>
    <div class="stat"><div class="stat-num amber">{likely}</div><div class="stat-label">Likely</div></div>
    <div class="stat"><div class="stat-num">€{avg_price:.0f}</div><div class="stat-label">Avg Price</div></div>
    <div class="stat"><div class="stat-num">⭐ {avg_rating:.1f}</div><div class="stat-label">Avg Rating</div></div>
    <div class="stat"><div class="stat-num">{len(with_coords)}</div><div class="stat-label">On Map</div></div>
  </div>

  <div class="actions">
    <a href="../index.html?hood={quote_plus(hood)}" class="btn primary">📋 Browse All {total} in Database</a>
    <a href="../lists/{slug}.html" class="btn">🏆 Top 10 List</a>
    <a href="../crawl.html" class="btn">🚶 Plan Lunch Crawl</a>
  </div>

  <div class="section">
    <div class="section-title">🏆 Top 5 Rated</div>
    {top5_html}
  </div>

  {'<div class="section"><div class="section-title">🗺️ Neighborhood Map</div><div id="hood-map"></div></div>' if with_coords else ''}

  <div class="section">
    <div class="section-title">🍽️ Cuisine Breakdown</div>
    <div class="cuisine-box">{cuisine_html}</div>
  </div>

  <div class="section">
    <div class="section-title">💎 Price Tiers</div>
    <div class="cuisine-box">
      <div class="cb-item"><span class="cb-name">💚 Budget</span><span class="cb-count">{budget_count}</span></div>
      <div class="cb-item"><span class="cb-name">🧡 Mid-Range</span><span class="cb-count">{mid_count}</span></div>
      <div class="cb-item"><span class="cb-name">💎 Premium</span><span class="cb-count">{premium_count}</span></div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">📍 Other Neighborhoods</div>
    <div class="hood-links">{other_hoods_html}</div>
  </div>
</div>
<footer><a href="../index.html">Menuverso</a> · <a href="../lists.html">Best Of</a> · <a href="../analytics.html">Analytics</a></footer>
<script>
function initTheme(){{var s=localStorage.getItem('menuverso_theme');if(s==='dark'||(!s&&window.matchMedia('(prefers-color-scheme:dark)').matches)){{document.documentElement.classList.add('dark');document.getElementById('theme-toggle').textContent='☀️';}}}};
function toggleTheme(){{var d=document.documentElement.classList.toggle('dark');localStorage.setItem('menuverso_theme',d?'dark':'light');document.getElementById('theme-toggle').textContent=d?'☀️':'🌙';}};
initTheme();
</script>
{'<script>' + '''
var m=L.map('hood-map').setView([''' + str(with_coords[0]["coordinates"]["lat"] if with_coords else 41.3888) + ',' + str(with_coords[0]["coordinates"]["lng"] if with_coords else 2.17) + '''],15);
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{maxZoom:19}).addTo(m);
var pts=''' + markers_json + ''';
pts.forEach(function(p){
  var c=p[3]==='confirmed'?'#059669':p[3]==='likely'?'#D97706':'#DC2626';
  L.circleMarker([p[0],p[1]],{radius:6,fillColor:c,color:'#fff',weight:2,fillOpacity:0.9}).addTo(m).bindPopup('<b>'+p[2]+'</b><br><a href="../r/'+p[4]+'.html">View details</a>');
});
if(pts.length>1){m.fitBounds(pts.map(function(p){return[p[0],p[1]]}));}
</script>''' if with_coords else ''}
</body>
</html>"""


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = len(restaurants)

    # Group by neighborhood
    hoods = {}
    for r in restaurants:
        h = r.get("neighborhood", "Unknown")
        if h not in hoods:
            hoods[h] = []
        hoods[h].append(r)

    hood_counts = {h: len(rs) for h, rs in hoods.items()}

    for hood, rs in hoods.items():
        html = generate_neighborhood_page(hood, rs, hood_counts, total)
        slug = hood.lower().replace(" ", "-").replace("'", "").replace("ò", "o").replace("à", "a").replace("í", "i")
        path = os.path.join(OUTPUT_DIR, f"{slug}.html")
        with open(path, "w") as f:
            f.write(html)

    print(f"📍 Generated {len(hoods)} neighborhood deep-dive pages in /{OUTPUT_DIR}/")
    for h in sorted(hoods.keys()):
        slug = h.lower().replace(" ", "-").replace("'", "").replace("ò", "o").replace("à", "a").replace("í", "i")
        print(f"   📍 {h}: {len(hoods[h])} restaurants → {slug}.html")


if __name__ == "__main__":
    main()
