#!/usr/bin/env python3
"""Find events ending today/tomorrow"""

import requests
import json

def main():
    resp = requests.get("https://gamma-api.polymarket.com/events?active=true&closed=false&limit=500")
    data = resp.json()

    print("Events ending Jan 19-21 (active, not closed):")
    print("=" * 70)

    found = []
    for event in data:
        end = event.get("endDate", "")
        if "2026-01-19" in end or "2026-01-20" in end or "2026-01-21" in end:
            found.append(event)

    if found:
        for event in found:
            title = event.get("title")
            slug = event.get("slug")
            end = event.get("endDate", "")[:16]
            vol = event.get("volume", 0)
            markets = event.get("markets", [])
            active = [m for m in markets if m.get("active") and not m.get("closed")]

            print(f"\n{title}")
            print(f"  Slug: {slug}")
            print(f"  Ends: {end}, Volume: ${vol:,.0f}")
            print(f"  Active markets: {len(active)}")

            for m in active[:3]:
                name = m.get("groupItemTitle") or m.get("question", "?")[:40]
                prices = json.loads(m.get("outcomePrices", "[0,0]"))
                yes = float(prices[0]) if prices else 0
                print(f"    - {name}: {yes:.1%}")
    else:
        print("\nNone found")

    # Also check for recently closed game markets to understand the pattern
    print("\n" + "=" * 70)
    print("Checking recently CLOSED game markets...")
    print("=" * 70)

    # Search for closed game markets
    for pattern in ["lal-", "epl-", "nba-", "ser-", "bun-"]:
        slug_search = f"https://gamma-api.polymarket.com/events?slug_contains={pattern}&limit=20"
        try:
            r2 = requests.get(slug_search)
            games = r2.json()

            open_games = [g for g in games if not g.get("closed")]
            closed_games = [g for g in games if g.get("closed")]

            if open_games:
                print(f"\n{pattern.upper()} OPEN games: {len(open_games)}")
                for g in open_games[:5]:
                    print(f"  {g.get('slug')}: {g.get('title')}")
                    print(f"    Ends: {g.get('endDate', '')[:16]}")
        except:
            pass

if __name__ == "__main__":
    main()
