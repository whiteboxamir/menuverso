#!/usr/bin/env python3
"""
Menuverso Curated Lists Generator
Auto-generates "Best Of" pages for SEO and discovery:
- Top 10 Budget Eats per neighborhood
- Best Rated per cuisine type  
- Best Value (high rating + low price)
- Overall Top 10s across categories
"""

import json
import os
from urllib.parse import quote_plus

INPUT = "restaurants.json"
OUTPUT_DIR = "lists"

def parse_price(s):
    if not s: return None
    import re
    nums = re.findall(r'[\d.]+', s)
    return float(nums[0]) if nums else None


def generate_list_page(title, emoji, slug, restaurants, description, total_available):
    """Generate a single curated list page."""
    cards = []
    for i, r in enumerate(restaurants[:10]):
        price = r.get("menu_price_range", "—")
        rating = r.get("google_maps_rating", "")
        tier = r.get("menu_tier", "none")
        tier_emoji = {"confirmed": "🟢", "likely": "🟡", "none": "🔴"}.get(tier, "")
        tags = "".join(f'<span class="list-tag">{t}</span>' for t in r.get("tags", [])[:3])
        rank_class = "gold" if i == 0 else "silver" if i == 1 else "bronze" if i == 2 else ""
        
        cards.append(f'''<a href="../r/{r["id"]}.html" class="list-card">
      <div class="rank {rank_class}">{i+1}</div>
      <div class="card-body">
        <div class="card-name">{r["name"]}</div>
        <div class="card-meta">{tier_emoji} {r.get("cuisine_type","")} · {r.get("neighborhood","")} · {price}</div>
        <div class="card-meta">{f'⭐ {rating}/5 ({r.get("google_maps_review_count",0)} reviews)' if rating else ''}{f' · 🚇 {r.get("metro_station","")}' if r.get("metro_station") else ''}</div>
        {f'<div class="card-notes">{r.get("notes","")[:100]}{"..." if len(r.get("notes","")) > 100 else ""}</div>' if r.get("notes") else ''}
        {f'<div class="card-tags">{tags}</div>' if tags else ''}
      </div>
      <div class="card-score">{price}<small>menú</small></div>
    </a>''')

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | Menuverso — Barcelona</title>
<meta name="description" content="{title}. {description}. Curated by Menuverso from {total_available:,} Barcelona restaurants.">
<meta property="og:title" content="{title} | Menuverso">
<meta property="og:description" content="{description}">
<meta property="og:type" content="website">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{--bg:#F8FAFC;--card:#FFF;--text:#1E293B;--sub:#64748B;--mut:#94A3B8;--border:#E2E8F0;--accent:#2563EB;--accent-sub:#DBEAFE;--green:#059669;--radius:12px;--shadow:0 2px 8px rgba(0,0,0,0.06);}}
:root.dark{{--bg:#0F172A;--card:#1E293B;--text:#F1F5F9;--sub:#94A3B8;--mut:#64748B;--border:#334155;--accent:#3B82F6;--accent-sub:#1E3A5F;--green:#34D399;--shadow:0 2px 8px rgba(0,0,0,0.3);}}
body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;transition:background 0.3s,color 0.3s;}}
.topnav{{display:flex;align-items:center;justify-content:space-between;padding:0.6rem 1.5rem;border-bottom:1px solid var(--border);background:var(--card);position:sticky;top:0;z-index:100;backdrop-filter:blur(12px);}}
.nav-brand{{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);font-weight:700;font-size:1.1rem;}}
.nav-brand img{{width:28px;height:28px;border-radius:8px;}}
.nav-links{{display:flex;align-items:center;gap:1rem;}}
.nav-links a{{color:var(--sub);text-decoration:none;font-size:0.82rem;font-weight:500;padding:0.3rem 0.5rem;border-radius:8px;transition:all 0.2s;}}
.nav-links a:hover{{color:var(--text);background:var(--accent-sub);}}
.nav-links a.active{{color:var(--accent);font-weight:600;}}
.controls-bar{{display:flex;gap:0.5rem;align-items:center;}}
.theme-btn{{background:none;border:1px solid var(--border);border-radius:20px;padding:0.3rem 0.55rem;cursor:pointer;font-size:0.85rem;color:var(--sub);transition:all 0.2s;}}
.container{{max-width:700px;margin:0 auto;padding:1.5rem;}}
.back{{display:inline-flex;align-items:center;gap:6px;color:var(--sub);text-decoration:none;font-size:0.85rem;font-weight:500;margin-bottom:1.5rem;transition:color 0.2s;}}
.back:hover{{color:var(--text);}}
.list-header{{text-align:center;margin-bottom:2rem;}}
.list-header h1{{font-size:clamp(1.4rem,3vw,2rem);margin-bottom:0.5rem;}}
.list-header p{{color:var(--sub);font-size:0.9rem;max-width:500px;margin:0 auto;}}
.list-card{{display:flex;gap:1rem;align-items:flex-start;padding:1.25rem;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:0.75rem;text-decoration:none;color:var(--text);transition:all 0.2s;box-shadow:var(--shadow);}}
.list-card:hover{{transform:translateY(-2px);box-shadow:0 6px 16px rgba(0,0,0,0.1);border-color:var(--accent);}}
.rank{{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:0.85rem;background:var(--accent-sub);color:var(--accent);flex-shrink:0;}}
.rank.gold{{background:#FEF3C7;color:#D97706;}}
.rank.silver{{background:#F1F5F9;color:#64748B;}}
.rank.bronze{{background:#FED7AA;color:#C2410C;}}
.card-body{{flex:1;min-width:0;}}
.card-name{{font-weight:600;font-size:1rem;margin-bottom:0.25rem;}}
.card-meta{{font-size:0.82rem;color:var(--sub);margin-bottom:0.15rem;}}
.card-notes{{font-size:0.8rem;color:var(--mut);margin-top:0.3rem;}}
.card-tags{{display:flex;gap:0.25rem;margin-top:0.35rem;flex-wrap:wrap;}}
.list-tag{{font-size:0.68rem;padding:2px 6px;border-radius:4px;background:var(--accent-sub);color:var(--accent);font-weight:500;}}
.card-score{{font-weight:700;font-size:1.2rem;color:var(--green);flex-shrink:0;text-align:center;}}
.card-score small{{display:block;font-size:0.6rem;color:var(--mut);font-weight:500;}}
footer{{text-align:center;padding:2rem;color:var(--mut);font-size:0.78rem;}}
footer a{{color:var(--sub);text-decoration:none;}}
img[src*="logo.png"]{{mix-blend-mode:multiply;}}
:root.dark img[src*="logo.png"]{{mix-blend-mode:normal;filter:brightness(1.2);}}
@media(max-width:640px){{.list-card{{flex-direction:column;gap:0.75rem;}}.nav-links a span{{display:none;}}}}
</style>
</head>
<body>
<nav class="topnav">
  <a href="../index.html" class="nav-brand"><img src="../assets/logo.png" alt="Menuverso"><span>Menuverso</span></a>
  <div class="nav-links">
    <a href="../index.html"><span>📋 </span>Database</a>
    <a href="../finder.html"><span>🔍 </span>Finder</a>
    <a href="../analytics.html"><span>📊 </span>Analytics</a>
    <a href="../lists.html" class="active"><span>🏆 </span>Best Of</a>
  </div>
  <div class="controls-bar"><button class="theme-btn" id="theme-toggle" onclick="toggleTheme()">🌙</button></div>
</nav>
<div class="container">
  <a href="../lists.html" class="back">← All Curated Lists</a>
  <div class="list-header">
    <h1>{emoji} {title}</h1>
    <p>{description}</p>
  </div>
  {''.join(cards)}
</div>
<footer><a href="../index.html">Menuverso</a> · <a href="../lists.html">All Lists</a> · <a href="../analytics.html">Analytics</a></footer>
<script>
function initTheme(){{var s=localStorage.getItem('menuverso_theme');if(s==='dark'||(!s&&window.matchMedia('(prefers-color-scheme:dark)').matches)){{document.documentElement.classList.add('dark');document.getElementById('theme-toggle').textContent='☀️';}}}}
function toggleTheme(){{var d=document.documentElement.classList.toggle('dark');localStorage.setItem('menuverso_theme',d?'dark':'light');document.getElementById('theme-toggle').textContent=d?'☀️':'🌙';}}
initTheme();
</script>
</body>
</html>"""


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    total = len(restaurants)
    generated = []

    # === 1. Best Value (High Rating + Low Price) ===
    best_value = [r for r in restaurants if r.get("google_maps_rating") and r["google_maps_rating"] >= 4.3 and parse_price(r.get("menu_price_range")) and parse_price(r["menu_price_range"]) <= 14]
    best_value.sort(key=lambda r: (-r["google_maps_rating"], parse_price(r["menu_price_range"])))
    html = generate_list_page("Best Value Menú del Día", "🏆", "best-value", best_value, 
        f"Restaurants rated 4.3+ stars with menú del día under €14. The best bang for your buck in Barcelona.", total)
    with open(f"{OUTPUT_DIR}/best-value.html", "w") as f: f.write(html)
    generated.append(("🏆", "Best Value Menú del Día", "best-value", len(best_value[:10]), "Rating 4.3+ & under €14"))

    # === 2. Top Rated Overall ===
    top_rated = [r for r in restaurants if r.get("google_maps_rating") and r.get("google_maps_review_count", 0) >= 50]
    top_rated.sort(key=lambda r: (-r["google_maps_rating"], -r.get("google_maps_review_count", 0)))
    html = generate_list_page("Top Rated Restaurants", "⭐", "top-rated", top_rated,
        "The highest-rated restaurants in Barcelona with 50+ Google reviews.", total)
    with open(f"{OUTPUT_DIR}/top-rated.html", "w") as f: f.write(html)
    generated.append(("⭐", "Top Rated Restaurants", "top-rated", len(top_rated[:10]), "Highest Google ratings (50+ reviews)"))

    # === 3. Most Affordable ===
    affordable = [r for r in restaurants if parse_price(r.get("menu_price_range"))]
    affordable.sort(key=lambda r: parse_price(r["menu_price_range"]))
    html = generate_list_page("Budget Friendly Menú del Día", "💚", "budget", affordable,
        "The most affordable menú del día options across Barcelona.", total)
    with open(f"{OUTPUT_DIR}/budget.html", "w") as f: f.write(html)
    generated.append(("💚", "Budget Friendly", "budget", len(affordable[:10]), "Cheapest menú del día"))

    # === 4. Premium Dining ===
    premium = [r for r in restaurants if r.get("pricing_tier") == "premium" and r.get("google_maps_rating")]
    premium.sort(key=lambda r: (-r["google_maps_rating"], -r.get("google_maps_review_count", 0)))
    html = generate_list_page("Premium Menú del Día", "💎", "premium", premium,
        "Upscale menú del día with chef-driven cuisine and premium ingredients.", total)
    with open(f"{OUTPUT_DIR}/premium.html", "w") as f: f.write(html)
    generated.append(("💎", "Premium Dining", "premium", len(premium[:10]), "Best premium-tier restaurants"))

    # === 5. Best per Neighborhood ===
    hoods = {}
    for r in restaurants:
        h = r.get("neighborhood", "Unknown")
        if h not in hoods: hoods[h] = []
        hoods[h].append(r)

    for hood, rs in sorted(hoods.items()):
        rated = [r for r in rs if r.get("google_maps_rating")]
        if len(rated) < 3: continue
        rated.sort(key=lambda r: (-r["google_maps_rating"], -r.get("google_maps_review_count", 0)))
        slug = hood.lower().replace(" ", "-").replace("'", "")
        html = generate_list_page(f"Best of {hood}", "📍", slug, rated,
            f"Top-rated restaurants in {hood}, Barcelona. Sorted by Google rating.", total)
        with open(f"{OUTPUT_DIR}/{slug}.html", "w") as f: f.write(html)
        generated.append(("📍", f"Best of {hood}", slug, len(rated[:10]), f"Top rated in {hood}"))

    # === 6. Best per Cuisine ===
    cuisines = {}
    for r in restaurants:
        c = r.get("cuisine_type", "Unknown")
        if c not in cuisines: cuisines[c] = []
        cuisines[c].append(r)

    for cuisine, rs in sorted(cuisines.items()):
        rated = [r for r in rs if r.get("google_maps_rating")]
        if len(rated) < 5: continue
        rated.sort(key=lambda r: (-r["google_maps_rating"], -r.get("google_maps_review_count", 0)))
        slug = f"cuisine-{cuisine.lower().replace(' ', '-').replace('/', '-')}"
        html = generate_list_page(f"Best {cuisine} Restaurants", "🍽️", slug, rated,
            f"Top-rated {cuisine} restaurants in Barcelona.", total)
        with open(f"{OUTPUT_DIR}/{slug}.html", "w") as f: f.write(html)
        generated.append(("🍽️", f"Best {cuisine}", slug, len(rated[:10]), f"Top {cuisine} restaurants"))

    # === 7. Confirmed Menu with Best Ratings ===
    confirmed = [r for r in restaurants if r.get("menu_tier") == "confirmed" and r.get("google_maps_rating")]
    confirmed.sort(key=lambda r: (-r["google_maps_rating"], -r.get("google_maps_review_count", 0)))
    html = generate_list_page("Best Confirmed Menú del Día", "🟢", "confirmed-best", confirmed,
        "Top-rated restaurants with confirmed menú del día. No guessing — these are verified.", total)
    with open(f"{OUTPUT_DIR}/confirmed-best.html", "w") as f: f.write(html)
    generated.append(("🟢", "Best Confirmed Menú", "confirmed-best", len(confirmed[:10]), "Verified menú del día, top rated"))

    print(f"🏆 Generated {len(generated)} curated list pages in /{OUTPUT_DIR}/")
    return generated


if __name__ == "__main__":
    lists = main()
    # Print summary
    for emoji, title, slug, count, desc in lists:
        print(f"   {emoji} {title}: {count} entries → {slug}.html")
