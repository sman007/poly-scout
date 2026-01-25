#!/usr/bin/env python3
"""Check weather market liquidity."""
import httpx
import json

url = 'https://gamma-api.polymarket.com/markets'
params = {'active': 'true', 'closed': 'false', 'limit': 500}

resp = httpx.get(url, params=params, timeout=30)
markets = resp.json()

print("=== WEATHER MARKET LIQUIDITY ===\n")

for m in markets:
    q = m.get('question', '').lower()
    # Match weather markets
    if any(city in q for city in ['seoul', 'london', 'wellington']) and \
       any(date in q for date in ['january 25', 'january 26', 'january 27']):

        question = m.get('question', '')[:65]
        liq = float(m.get('liquidity', 0))
        vol = float(m.get('volume', 0))
        prices_str = m.get('outcomePrices', '[]')
        prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str

        print(f"{question}")
        print(f"  Liquidity: ${liq:,.0f} | Volume: ${vol:,.0f}")
        if prices:
            yes_price = float(prices[0]) if len(prices) > 0 else 0
            no_price = float(prices[1]) if len(prices) > 1 else 0
            print(f"  Yes: {yes_price:.1%} | No: {no_price:.1%}")
        print()
