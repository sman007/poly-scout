#!/usr/bin/env python3
"""Weather scanner performance analysis."""
import time
import json
import requests
from collections import defaultdict
from src.weather_scanner import scan_weather_markets, find_weather_edges

print("=" * 70)
print("WEATHER SCANNER PERFORMANCE ANALYSIS")
print("=" * 70)

# 1. API LATENCY TEST
print("\n[1] API LATENCY TEST")
print("-" * 40)

latencies = []
test_slugs = [
    "highest-temperature-in-seoul-on-january-24",
    "highest-temperature-in-london-on-january-24",
    "highest-temperature-in-wellington-on-january-24"
]

for slug in test_slugs:
    start = time.time()
    r = requests.get(f"https://gamma-api.polymarket.com/events/slug/{slug}", timeout=15)
    latency_ms = (time.time() - start) * 1000
    latencies.append(latency_ms)
    print(f"  {slug[:40]}...: {latency_ms:.0f}ms")

print(f"  Average Gamma API latency: {sum(latencies)/len(latencies):.0f}ms")

start = time.time()
r = requests.get("https://api.open-meteo.com/v1/forecast?latitude=37.5665&longitude=126.9780&daily=temperature_2m_max&timezone=Asia/Seoul&start_date=2026-01-24&end_date=2026-01-24", timeout=10)
meteo_latency = (time.time() - start) * 1000
print(f"  Open-Meteo API latency: {meteo_latency:.0f}ms")

# 2. MARKET DATA ANALYSIS
print("\n[2] MARKET SATURATION & LIQUIDITY")
print("-" * 40)

markets = scan_weather_markets()

by_event = defaultdict(list)
for m in markets:
    key = m["city"] + "_" + m["date"]
    by_event[key].append(m)

total_liquidity = 0
total_volume = 0
liquid_markets = 0
illiquid_markets = 0

for event_key, event_markets in by_event.items():
    event_data = event_markets[0]["event"]
    liq = float(event_data.get("liquidity", 0) or 0)
    vol = float(event_data.get("volume", 0) or 0)
    total_liquidity += liq
    total_volume += vol

    if liq > 1000:
        liquid_markets += 1
    else:
        illiquid_markets += 1

    parts = event_key.split("_")
    city = parts[0]
    date = parts[1]
    print(f"  {city.upper()} {date}: ${liq:,.0f} liquidity, ${vol:,.0f} volume")

print(f"\n  Total liquidity: ${total_liquidity:,.0f}")
print(f"  Total volume: ${total_volume:,.0f}")
print(f"  Liquid events (>$1k): {liquid_markets}")
print(f"  Illiquid events: {illiquid_markets}")

# 3. ORDER BOOK DEPTH ANALYSIS
print("\n[3] ORDER BOOK DEPTH (Fill Likelihood)")
print("-" * 40)

sample_market = None
for m in markets[:5]:
    cid = m.get("condition_id")
    if cid:
        sample_market = m
        break

if sample_market:
    try:
        from src.polymarket_client import PolymarketClient
        client = PolymarketClient()

        market_data = sample_market["market"]
        clob_ids = market_data.get("clobTokenIds", "")

        if clob_ids:
            token_ids = json.loads(clob_ids) if isinstance(clob_ids, str) else clob_ids
            if token_ids and len(token_ids) > 0:
                book = client.get_order_book(token_ids[0])
                if book and book.bids and book.asks:
                    city = sample_market["city"].upper()
                    temp = sample_market["parsed"]["temp"]
                    print(f"  Sample: {city} {temp}C")
                    print(f"  Best bid: {book.bids[0].price:.4f} (${book.bids[0].size:.2f})")
                    print(f"  Best ask: {book.asks[0].price:.4f} (${book.asks[0].size:.2f})")
                    spread = book.asks[0].price - book.bids[0].price
                    print(f"  Spread: {spread*100:.2f}%")

                    bid_depth = sum(b.size for b in book.bids[:5])
                    ask_depth = sum(a.size for a in book.asks[:5])
                    print(f"  Bid depth (5 lvls): ${bid_depth:.2f}")
                    print(f"  Ask depth (5 lvls): ${ask_depth:.2f}")
                else:
                    print("  Order book empty or unavailable")
    except Exception as e:
        print(f"  Error getting order book: {e}")
else:
    print("  No sample market available")

# 4. EDGE DISTRIBUTION
print("\n[4] EDGE DISTRIBUTION ANALYSIS")
print("-" * 40)

edges = find_weather_edges(min_edge_pct=1.0)

if edges:
    edge_values = [e.edge_pct for e in edges]
    high_conf = [e for e in edges if e.confidence == "HIGH"]
    med_conf = [e for e in edges if e.confidence == "MEDIUM"]
    low_conf = [e for e in edges if e.confidence == "LOW"]

    buy_yes = [e for e in edges if e.direction == "BUY_YES"]
    buy_no = [e for e in edges if e.direction == "BUY_NO"]

    print(f"  Total edges found: {len(edges)}")
    print(f"  Average edge: {sum(edge_values)/len(edge_values):.1f}%")
    print(f"  Max edge: {max(edge_values):.1f}%")
    print(f"  Min edge: {min(edge_values):.1f}%")
    print(f"\n  By confidence:")
    print(f"    HIGH (>15%): {len(high_conf)}")
    print(f"    MEDIUM (10-15%): {len(med_conf)}")
    print(f"    LOW (<10%): {len(low_conf)}")
    print(f"\n  By direction:")
    print(f"    BUY_YES: {len(buy_yes)}")
    print(f"    BUY_NO: {len(buy_no)}")

# 5. FILL PROBABILITY ESTIMATE
print("\n[5] FILL PROBABILITY ESTIMATE")
print("-" * 40)

fillable_edges = []
for e in edges:
    pm_price = e.pm_probability
    if 0.05 < pm_price < 0.95:
        fillable_edges.append(e)

print(f"  Total edges: {len(edges)}")
print(f"  Fillable (5-95% price): {len(fillable_edges)}")
if edges:
    print(f"  Fill rate estimate: {len(fillable_edges)/len(edges)*100:.0f}%")

if fillable_edges:
    print(f"\n  Best fillable opportunities:")
    sorted_fillable = sorted(fillable_edges, key=lambda x: x.edge_pct, reverse=True)[:5]
    for e in sorted_fillable:
        city = e.market.city.upper()
        bracket = e.market.temp_bracket
        edge = e.edge_pct
        price = e.pm_probability * 100
        print(f"    {city} {bracket}C: {edge:.1f}% edge @ {price:.1f}% price")

# 6. TIMING ANALYSIS
print("\n[6] FULL SCAN TIMING")
print("-" * 40)

start = time.time()
_ = scan_weather_markets()
scan_time = time.time() - start

start = time.time()
_ = find_weather_edges(min_edge_pct=3.0)
edge_time = time.time() - start

print(f"  Market scan time: {scan_time:.2f}s")
print(f"  Edge detection time: {edge_time:.2f}s")
print(f"  Total cycle time: {scan_time + edge_time:.2f}s")
print(f"  Recommended poll interval: {max(60, int((scan_time + edge_time) * 2))}s")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Markets scanned: {len(markets)} brackets across {len(by_event)} events")
print(f"  Total liquidity: ${total_liquidity:,.0f}")
if edges:
    print(f"  Edges found: {len(edges)} ({len(high_conf)} high confidence)")
    print(f"  Fillable edges: {len(fillable_edges)} ({len(fillable_edges)/len(edges)*100:.0f}%)")
print(f"  Avg API latency: {sum(latencies)/len(latencies):.0f}ms")
print(f"  Full cycle time: {scan_time + edge_time:.2f}s")
