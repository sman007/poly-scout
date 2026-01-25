#!/usr/bin/env python3
"""Check weather market liquidity."""
import requests
import json

cities = ["seoul", "london", "wellington"]
days = [(25, "january"), (26, "january"), (27, "january")]

print("=== WEATHER MARKET LIQUIDITY ===\n")

for city in cities:
    for day, month in days:
        slug = f"highest-temperature-in-{city}-on-{month}-{day}"
        url = f"https://gamma-api.polymarket.com/events/slug/{slug}"

        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue

            event = resp.json()
            markets = event.get("markets", [])

            print(f"\n{city.upper()} {month.title()} {day}")
            print("-" * 50)

            for m in markets:
                bracket = m.get("groupItemTitle", "")
                liq = float(m.get("liquidityNum", 0) or 0)
                vol = float(m.get("volume", 0) or 0)
                prices_str = m.get("outcomePrices", "[]")
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str

                if prices:
                    yes_p = float(prices[0]) * 100 if len(prices) > 0 else 0
                    no_p = float(prices[1]) * 100 if len(prices) > 1 else 0
                else:
                    yes_p, no_p = 0, 0

                print(f"  {bracket:20} | Yes: {yes_p:5.1f}% | Liq: ${liq:>8,.0f} | Vol: ${vol:>10,.0f}")

        except Exception as e:
            print(f"Error for {slug}: {e}")
