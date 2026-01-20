#!/usr/bin/env python3
"""Analyze beachboy4's trading strategy from blockchain data"""

import requests
import json
from datetime import datetime

def analyze_beachboy4():
    # Get beachboy4 trades
    url = "https://data-api.polymarket.com/trades?user=0xc2e7800b5af46e6093872b177b7a5e7f0563be51&limit=300"
    data = requests.get(url).json()

    print(f"beachboy4 Recent Trades ({len(data)} total)\n")

    # Group by eventSlug (the game, not the individual outcome market)
    events = {}
    for t in data:
        event = t.get("eventSlug", "?")
        title = t.get("title", "?")
        slug = t.get("slug", "?")
        outcome = t.get("outcome", "?")
        side = t.get("side", "?")
        price = float(t.get("price", 0))
        size = float(t.get("size", 0))
        ts = t.get("timestamp", 0)

        if event not in events:
            events[event] = {"title": title, "markets": {}}

        market_key = slug  # Individual market (team-specific)
        if market_key not in events[event]["markets"]:
            events[event]["markets"][market_key] = {"title": title, "trades": []}

        events[event]["markets"][market_key]["trades"].append({
            "side": side, "outcome": outcome, "price": price, "size": size, "ts": ts
        })

    # Print results grouped by game/event
    print("=" * 80)
    print("BEACHBOY4 POSITIONS BY GAME")
    print("=" * 80)

    for event, info in list(events.items())[:12]:
        print(f"\nEVENT: {event}")

        total_combined = 0
        market_prices = []

        for market, minfo in info["markets"].items():
            trades = minfo["trades"]
            total_size = sum(t["size"] for t in trades)
            avg_price = sum(t["price"] * t["size"] for t in trades) / total_size if total_size > 0 else 0
            outcomes = set(f"{t['side']} {t['outcome']}" for t in trades)

            print(f"  {market[:55]}")
            print(f"    Positions: {outcomes}")
            print(f"    Total: ${total_size:,.0f}, Avg Price: ${avg_price:.4f}")

            market_prices.append(avg_price)

        # Check if this looks like spread capture (multiple markets, sum < 1)
        if len(market_prices) > 1:
            combined = sum(market_prices)
            edge = (1.0 - combined) * 100
            verdict = "SPREAD CAPTURE!" if combined < 0.99 else "DIRECTIONAL"
            print(f"  --> Combined: ${combined:.4f} = {edge:.1f}% edge - {verdict}")
        print()

if __name__ == "__main__":
    analyze_beachboy4()
