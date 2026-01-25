#!/usr/bin/env python3
"""
Hans323 Wallet Deep Analysis.

Fetches all available data from Polymarket APIs to determine the ACTUAL strategy.
No assumptions - only facts from blockchain data.

Wallet: 0x0f37cb80dee49d55b5f6d9e595d52591d6371410
"""

import requests
import json
from datetime import datetime
from collections import defaultdict

WALLET = "0x0f37cb80dee49d55b5f6d9e595d52591d6371410"

def log(msg):
    print(f"[ANALYSIS] {msg}", flush=True)


def fetch_all_activity(wallet: str, limit: int = 500) -> list:
    """Fetch all activity from the data API."""
    url = f"https://data-api.polymarket.com/activity?user={wallet}&limit={limit}"
    log(f"Fetching activity from: {url}")

    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        log(f"Got {len(data)} activity records")
        return data
    except Exception as e:
        log(f"Error: {e}")
        return []


def fetch_positions(wallet: str) -> list:
    """Fetch current positions."""
    url = f"https://data-api.polymarket.com/positions?user={wallet}"
    log(f"Fetching positions from: {url}")

    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        log(f"Got {len(data)} positions")
        return data
    except Exception as e:
        log(f"Error: {e}")
        return []


def fetch_trades(wallet: str, limit: int = 500) -> list:
    """Fetch trades from CLOB API."""
    url = f"https://clob.polymarket.com/trades?maker={wallet}&limit={limit}"
    log(f"Fetching trades as maker from: {url}")

    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        log(f"Got {len(data) if isinstance(data, list) else 'N/A'} maker trades")
        return data if isinstance(data, list) else []
    except Exception as e:
        log(f"Error fetching maker trades: {e}")

    # Also try taker
    url = f"https://clob.polymarket.com/trades?taker={wallet}&limit={limit}"
    log(f"Fetching trades as taker from: {url}")

    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        log(f"Got {len(data) if isinstance(data, list) else 'N/A'} taker trades")
        return data if isinstance(data, list) else []
    except Exception as e:
        log(f"Error fetching taker trades: {e}")
        return []


def fetch_profit_loss(wallet: str) -> dict:
    """Fetch profit/loss data."""
    url = f"https://data-api.polymarket.com/profit-loss?user={wallet}"
    log(f"Fetching P&L from: {url}")

    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        log(f"Got P&L data: {type(data)}")
        return data
    except Exception as e:
        log(f"Error: {e}")
        return {}


def fetch_earnings(wallet: str) -> dict:
    """Fetch earnings data."""
    url = f"https://data-api.polymarket.com/earnings?user={wallet}"
    log(f"Fetching earnings from: {url}")

    try:
        r = requests.get(url, timeout=30)
        data = r.json()
        log(f"Got earnings data: {type(data)}")
        return data
    except Exception as e:
        log(f"Error: {e}")
        return {}


def analyze_activity_detail(activities: list):
    """Analyze activity records in detail."""
    log("\n" + "="*70)
    log("DETAILED ACTIVITY ANALYSIS")
    log("="*70)

    weather_trades = []

    for a in activities:
        title = a.get("title", "").lower()
        if "temperature" in title or "weather" in title:
            weather_trades.append(a)

    log(f"\nTotal weather-related activities: {len(weather_trades)}")

    # Analyze each field available
    if weather_trades:
        log("\nSample weather trade (ALL FIELDS):")
        sample = weather_trades[0]
        for key, value in sorted(sample.items()):
            log(f"  {key}: {value}")

    # Count by action type
    action_counts = defaultdict(int)
    for t in weather_trades:
        action = t.get("action", "unknown")
        action_counts[action] += 1

    log(f"\nWeather trades by action:")
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        log(f"  {action}: {count}")

    # Count by type
    type_counts = defaultdict(int)
    for t in weather_trades:
        ttype = t.get("type", "unknown")
        type_counts[ttype] += 1

    log(f"\nWeather trades by type:")
    for ttype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        log(f"  {ttype}: {count}")

    # Analyze USDCSize (actual money involved)
    sizes = [float(t.get("usdcSize", 0) or 0) for t in weather_trades]
    if sizes:
        log(f"\nUSDC Size stats:")
        log(f"  Total: ${sum(sizes):,.2f}")
        log(f"  Average: ${sum(sizes)/len(sizes):,.2f}")
        log(f"  Max: ${max(sizes):,.2f}")
        log(f"  Min: ${min(sizes):,.2f}")

    # Check for outcome info
    outcomes = defaultdict(int)
    for t in weather_trades:
        outcome = t.get("outcome", t.get("outcomeIndex", "unknown"))
        outcomes[str(outcome)] += 1

    log(f"\nWeather trades by outcome:")
    for outcome, count in sorted(outcomes.items(), key=lambda x: -x[1]):
        log(f"  {outcome}: {count}")

    # Check sides
    sides = defaultdict(int)
    for t in weather_trades:
        side = t.get("side", "unknown")
        sides[str(side)] += 1

    log(f"\nWeather trades by side:")
    for side, count in sorted(sides.items(), key=lambda x: -x[1]):
        log(f"  {side}: {count}")

    return weather_trades


def analyze_positions_detail(positions: list):
    """Analyze positions in detail."""
    log("\n" + "="*70)
    log("DETAILED POSITIONS ANALYSIS")
    log("="*70)

    weather_positions = []

    for p in positions:
        title = p.get("title", "").lower()
        if "temperature" in title or "weather" in title:
            weather_positions.append(p)

    log(f"\nTotal weather positions: {len(weather_positions)}")

    if weather_positions:
        log("\nSample weather position (ALL FIELDS):")
        sample = weather_positions[0]
        for key, value in sorted(sample.items()):
            log(f"  {key}: {value}")

    log("\n" + "-"*50)
    log("ALL WEATHER POSITIONS:")
    log("-"*50)

    total_size = 0
    total_pnl = 0

    for p in weather_positions:
        title = p.get("title", "Unknown")
        size = float(p.get("currentValue", 0) or 0)
        pnl = float(p.get("pnl", 0) or 0)
        outcome = p.get("outcome", "Unknown")
        shares = float(p.get("size", 0) or 0)
        avg_price = float(p.get("avgPrice", 0) or 0)

        total_size += size
        total_pnl += pnl

        log(f"\n{title}")
        log(f"  Outcome: {outcome}")
        log(f"  Shares: {shares:.2f}")
        log(f"  Avg Price: ${avg_price:.4f}")
        log(f"  Current Value: ${size:.2f}")
        log(f"  P&L: ${pnl:+.2f}")

    log(f"\n{'='*50}")
    log(f"TOTALS:")
    log(f"  Total Position Value: ${total_size:,.2f}")
    log(f"  Total P&L: ${total_pnl:+,.2f}")

    return weather_positions


def check_gamma_api_trades(wallet: str):
    """Check gamma API for trade history."""
    log("\n" + "="*70)
    log("GAMMA API TRADE CHECK")
    log("="*70)

    # Try different endpoints
    endpoints = [
        f"https://gamma-api.polymarket.com/trades?user={wallet}",
        f"https://gamma-api.polymarket.com/orders?user={wallet}",
        f"https://gamma-api.polymarket.com/history?user={wallet}",
    ]

    for url in endpoints:
        log(f"\nTrying: {url}")
        try:
            r = requests.get(url, timeout=15)
            log(f"  Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    log(f"  Records: {len(data)}")
                    if data:
                        log(f"  Sample keys: {list(data[0].keys()) if isinstance(data[0], dict) else 'N/A'}")
                else:
                    log(f"  Data type: {type(data)}")
                    log(f"  Keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
        except Exception as e:
            log(f"  Error: {e}")


def check_strapi_data(wallet: str):
    """Check strapi (old API) for data."""
    log("\n" + "="*70)
    log("STRAPI API CHECK")
    log("="*70)

    url = f"https://strapi-matic.poly.market/users?address={wallet}"
    log(f"Trying: {url}")
    try:
        r = requests.get(url, timeout=15)
        log(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            log(f"  Data: {json.dumps(data, indent=2)[:1000]}")
    except Exception as e:
        log(f"  Error: {e}")


def analyze_resolved_markets(activities: list):
    """Find resolved markets and calculate actual P&L."""
    log("\n" + "="*70)
    log("RESOLVED MARKET ANALYSIS")
    log("="*70)

    # Group by market
    markets = defaultdict(list)
    for a in activities:
        title = a.get("title", "").lower()
        if "temperature" in title:
            condition_id = a.get("conditionId", a.get("condition_id", "unknown"))
            markets[condition_id].append(a)

    log(f"\nFound {len(markets)} unique weather markets")

    # Check which are resolved
    resolved = []
    for condition_id, trades in markets.items():
        if not trades:
            continue

        # Check market status
        sample = trades[0]

        # Try to get resolution status
        resolved_status = sample.get("resolved", sample.get("isResolved", None))

        if resolved_status:
            resolved.append({
                "condition_id": condition_id,
                "trades": trades,
                "title": sample.get("title", "Unknown")
            })

    log(f"Resolved markets found: {len(resolved)}")

    # For each resolved market, calculate P&L
    for market in resolved[:5]:  # First 5
        log(f"\n{market['title']}")
        log(f"  Condition ID: {market['condition_id']}")
        log(f"  Trades: {len(market['trades'])}")


def main():
    log("="*70)
    log(f"HANS323 WALLET DEEP ANALYSIS")
    log(f"Wallet: {WALLET}")
    log(f"Time: {datetime.now().isoformat()}")
    log("="*70)

    # Fetch all data sources
    activities = fetch_all_activity(WALLET)
    positions = fetch_positions(WALLET)
    trades = fetch_trades(WALLET)
    pnl = fetch_profit_loss(WALLET)
    earnings = fetch_earnings(WALLET)

    # Detailed analysis
    weather_activities = analyze_activity_detail(activities)
    weather_positions = analyze_positions_detail(positions)

    # Check other APIs
    check_gamma_api_trades(WALLET)
    check_strapi_data(WALLET)

    # Analyze resolved markets
    analyze_resolved_markets(activities)

    # Summary of P&L data
    log("\n" + "="*70)
    log("P&L DATA")
    log("="*70)
    if pnl:
        log(f"P&L response: {json.dumps(pnl, indent=2)[:2000]}")
    else:
        log("No P&L data available")

    log("\n" + "="*70)
    log("EARNINGS DATA")
    log("="*70)
    if earnings:
        log(f"Earnings response: {json.dumps(earnings, indent=2)[:2000]}")
    else:
        log("No earnings data available")

    # Final summary
    log("\n" + "="*70)
    log("ANALYSIS COMPLETE")
    log("="*70)

    log("\nKEY FINDINGS TO DOCUMENT:")
    log("-" * 50)


if __name__ == "__main__":
    main()
