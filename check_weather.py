#!/usr/bin/env python3
"""Check Hans323's weather positions and find active weather markets."""
import requests
import json

def main():
    print("=" * 60)
    print("HANS323 POSITIONS (Weather Trader)")
    print("=" * 60)

    # Get Hans323's positions
    hans_addr = "0x0f37cb80dee49d55b5f6d9e595d52591d6371410"
    r = requests.get(f"https://data-api.polymarket.com/positions?user={hans_addr}", timeout=15)
    positions = r.json()

    print(f"\nTotal positions: {len(positions)}")
    for p in positions:
        title = p.get('title', 'N/A')
        pnl = float(p.get('cashPnl', 0) or 0)
        value = float(p.get('currentValue', 0) or 0)
        print(f"  {title[:70]}")
        print(f"    PnL: ${pnl:.2f} | Current Value: ${value:.2f}")

    # Get recent activity
    print("\n" + "=" * 60)
    print("RECENT ACTIVITY")
    print("=" * 60)

    r2 = requests.get(f"https://data-api.polymarket.com/activity?user={hans_addr}&limit=50", timeout=15)
    trades = r2.json()

    # Find unique market titles
    markets_traded = set()
    for t in trades:
        title = t.get('title', 'N/A')
        markets_traded.add(title)

    print(f"\nUnique markets traded (last 50 trades): {len(markets_traded)}")
    for title in list(markets_traded)[:20]:
        print(f"  - {title[:70]}")

    # Search for active weather markets on Polymarket
    print("\n" + "=" * 60)
    print("ACTIVE WEATHER MARKETS ON POLYMARKET")
    print("=" * 60)

    r3 = requests.get("https://gamma-api.polymarket.com/markets?closed=false&limit=1000", timeout=30)
    all_markets = r3.json()

    weather_terms = ['temperature', 'celsius', 'fahrenheit', 'degrees f', 'degrees c',
                     'weather', 'daily high', 'nyc high', 'chicago high', 'la high',
                     'new york temperature', 'chicago temperature']

    weather_markets = []
    for m in all_markets:
        q = str(m.get('question', '')).lower()
        for term in weather_terms:
            if term in q:
                weather_markets.append(m)
                break

    print(f"\nFound {len(weather_markets)} weather markets:")
    for m in weather_markets:
        q = m.get('question', 'N/A')
        liquidity = m.get('liquidityNum', 0)
        vol = m.get('volume', 0)
        print(f"\n  Q: {q}")
        print(f"     Liquidity: ${liquidity:,.0f} | Volume: ${vol:,.0f}")
        print(f"     Slug: {m.get('slug', 'N/A')}")

if __name__ == "__main__":
    main()
