---
description: How to safely add new restaurant data to the Menuverso database
---

# Adding Restaurant Data — Integrity Guardrails

> **RULE #1: NEVER generate, invent, or fabricate restaurant data.**
> All restaurant records must come from verifiable external sources.

## Approved Data Sources

Only add restaurants sourced from:
- `web_search` — Manual web research with URL evidence
- `google_maps_scrape` — Automated Google Maps extraction
- `thefork` / `eltenedor` — TheFork/ElTenedor scraping
- `tripadvisor` — TripAdvisor scraping
- `manual_entry` — User-provided, manually verified
- `menu_del_dia_site` — Menú del día aggregator sites

## Required Fields for Every Record

Every new restaurant record MUST have ALL of these fields populated:

| Field | Rule |
|-------|------|
| `name` | Real name, verifiable on Google Maps |
| `city` | Must be "Barcelona" |
| `source` | Must be from approved list above |
| `address` or `address_full` | Real street address |
| `neighborhood` | Valid Barcelona neighborhood |
| `cuisine_type` | Populated |
| `google_maps_url` | Must link to a real Google Maps listing |
| `google_maps_rating` | Between 1.0 and 5.0 |
| `google_maps_review_count` | Real count from Google Maps |
| `status` | "active" or "permanently_closed" |

## Before Adding Data — Validation Steps

// turbo-all

1. Prepare new records as JSON (one file, array format)
2. Run the validator on new records:
```bash
python3 validate_data.py --check-new <new_records.json>
```
3. Fix ALL errors before proceeding
4. Merge into `restaurants.json`
5. Run full database validation:
```bash
python3 validate_data.py
```
6. Rebuild `restaurants_data.js`:
```bash
python3 -c "import json; d=json.load(open('restaurants.json')); f=open('restaurants_data.js','w'); f.write('var RESTAURANT_DATA = '+json.dumps(d,ensure_ascii=False,indent=2)+';\\n'); print(f'Rebuilt with {len(d)} records')"
```

## Red Flags — Signs of AI Fabrication

If you see ANY of these patterns, the data is likely fabricated:
- Restaurant name ends with a neighborhood name (e.g., "Trópico Sant Martí")
- No street address, only neighborhood
- No `city` or `source` field
- Suspiciously round review counts (100, 200, 300)
- Google Maps URL is just a search query with no address component
- No website, no phone, no Instagram — all empty
- Records added in a single batch with sequential IDs and no source

## Scaling the Database Legitimately

To add more real restaurants:
1. **Google Maps scraping** — Extract place data from Maps searches per neighborhood
2. **TheFork/ElTenedor** — Scrape their Barcelona restaurant listings
3. **TripAdvisor** — Cross-reference for ratings and reviews
4. **Menú del día sites** — menu-del-dia.com, bcnrestaurantes.com, etc.
5. **Always validate** — Run `validate_data.py --check-new` before merging
