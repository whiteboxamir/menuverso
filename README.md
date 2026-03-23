# 🍽️ Menuverso — Barcelona Menú del Día Database

A structured database of Barcelona restaurants offering **Menú del Día**, powering the Menuverso subscription app.

## Structure

| File | Purpose |
|---|---|
| `restaurants.json` | Main database — array of restaurant objects |
| `schema.json` | JSON Schema defining the data model |
| `neighborhoods.md` | Reference: Barcelona lunch neighborhoods |

## Schema Fields

Each restaurant entry includes:
- **Identity**: name, address, neighborhood, coordinates
- **Classification**: cuisine type, pricing tier (budget / mid-range / premium)
- **Menú del Día**: confirmed status, price range
- **Contact**: website, Google Maps URL, phone
- **Media**: hero image URL, menu photo URL
- **Meta**: rating, notes, lunch hours

## Pricing Tiers

| Tier | Price Range | Description |
|---|---|---|
| Budget | ≤ 12€ | No-frills, generous portions |
| Mid-range | 12–18€ | Quality ingredients, nice atmosphere |
| Premium | 18€+ | Chef-driven, upscale presentation |
