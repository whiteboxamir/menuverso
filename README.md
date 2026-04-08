# Menuverso — La Guía Definitiva del Menú del Día 🍽️

The largest menú del día database in Barcelona. 1,504 restaurants across 18 neighborhoods with menu tracking, pricing analytics, and trilingual support.

**Live:** [patriciaadro.github.io/menuverso-app](https://patriciaadro.github.io/menuverso-app/)

## Pages

| Page | URL | Description |
|---|---|---|
| 🗂️ Database | [index.html](index.html) | Main restaurant database with filters, map, favorites |
| 📊 Analytics | [analytics.html](analytics.html) | Price analytics by neighborhood and cuisine |
| 🔧 Admin | [admin.html](admin.html) | Data quality dashboard (noindex) |
| 🏠 Landing | [landing.html](landing.html) | Marketing landing page |
| 📋 Business Plan | [business-plan.html](business-plan.html) | Investor-facing business plan |
| 🎤 Pitch Deck | [menuverso-deck](https://patriciaadro.github.io/menuverso-deck/) | Slide deck (separate repo) |
| 🍴 Restaurant Pages | [/r/1.html](r/1.html) ... [/r/1504.html](r/1504.html) | 1,504 individual pages with JSON-LD |

## Features

- **Search & Filter** — By neighborhood, cuisine, price tier, menu status, tags, metro station
- **Interactive Map** — Leaflet map with marker clusters
- **Favorites** — LocalStorage-persisted bookmarks with ⭐ filter chip
- **CSV Export** — Download filtered results
- **Trilingual** — Spanish / Catalan / English (persisted via localStorage)
- **PWA** — Offline-capable, installable via manifest.json + sw.js
- **SEO** — JSON-LD structured data, sitemap.xml (1,507 URLs), individual restaurant pages
- **Analytics** — Price comparisons by neighborhood/cuisine, distribution charts, best-value rankings

## Data Pipeline

```
restaurants.json          ← Source of truth (1,504 entries)
    ↓
tag_restaurants.py        → Tags, pricing tiers, cuisine categories
geocode_restaurants.py    → Coordinates (safe merge, coords only)
metro_stations.py         → Nearest metro station assignment
google_maps_urls.py       → Google Maps search URLs
    ↓
restaurants_data.js       ← Auto-generated for frontend
generate_pages.py         → 1,504 individual HTML pages + sitemap.xml
```

### Post-Geocoding
After the geocoding thread finishes:
```bash
python3 post_geocode_pipeline.py
```

## Data Quality

| Field | Coverage |
|---|---|
| Name, Neighborhood, Cuisine | 100% |
| Menu Tier | 100% (595 confirmed, 619 likely, 290 none) |
| Coordinates | ~66% precise, ~33% centroid |
| Website | ~21% |
| Phone | ~22% |
| Tags | 100% (auto-generated) |

## Tech Stack

- **Frontend:** Vanilla HTML/CSS/JS, Leaflet.js, Chart.js
- **Data:** Python scripts, JSON source of truth
- **Hosting:** GitHub Pages
- **PWA:** Service Worker (network-first data, cache-first assets)
