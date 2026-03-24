#!/usr/bin/env python3
"""
Menuverso RSS Feed Generator
Creates an RSS 2.0 feed of all restaurants, useful for syndication and SEO.
"""

import json
from datetime import datetime
from xml.sax.saxutils import escape

INPUT = "restaurants.json"
OUTPUT = "feed.xml"
BASE = "https://whiteboxamir.github.io/menuverso"


def main():
    with open(INPUT) as f:
        restaurants = json.load(f)

    now = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    
    items = []
    for r in restaurants:
        name = escape(r.get("name", ""))
        hood = escape(r.get("neighborhood", ""))
        cuisine = escape(r.get("cuisine_type", ""))
        price = escape(r.get("menu_price_range", ""))
        notes = escape(r.get("notes", ""))
        rating = r.get("google_maps_rating", "")
        tier = r.get("menu_tier", "none")
        tier_label = {"confirmed": "Confirmed", "likely": "Likely", "none": "No Menú"}.get(tier, "")
        
        desc = f"{cuisine} in {hood}."
        if price:
            desc += f" {price} menú del día."
        if rating:
            desc += f" ⭐ {rating}/5."
        desc += f" Status: {tier_label}."
        if notes:
            desc += f" {notes[:120]}"

        items.append(f"""    <item>
      <title>{name}</title>
      <link>{BASE}/r/{r['id']}.html</link>
      <guid isPermaLink="true">{BASE}/r/{r['id']}.html</guid>
      <description>{escape(desc)}</description>
      <category>{cuisine}</category>
      <category>{hood}</category>
      <pubDate>{now}</pubDate>
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Menuverso — Barcelona Restaurant Database</title>
    <link>{BASE}/</link>
    <description>1,504 Barcelona restaurants with menú del día tracking. Updated daily.</description>
    <language>es</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{BASE}/feed.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>{BASE}/assets/logo.png</url>
      <title>Menuverso</title>
      <link>{BASE}/</link>
    </image>
{chr(10).join(items)}
  </channel>
</rss>"""

    with open(OUTPUT, "w") as f:
        f.write(feed)

    print(f"📡 Generated RSS feed: {OUTPUT} ({len(items)} items)")


if __name__ == "__main__":
    main()
