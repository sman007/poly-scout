#!/usr/bin/env python3
"""
Analyze DiviLungaoBBW wallet (0xb45a797faa52b0fd8a)
SPORTS_ARB Strategy Analysis

Using correct Polymarket Data API endpoints
"""

import requests
import json
from collections import defaultdict, Counter
from datetime import datetime

# Full wallet address from seen_wallets.json
WALLET = '0xb45a797faa52b0fd8adc56d30382022b7b12192c'

def log(msg):
    print(f"[DIVI] {msg}", flush=True)

def fetch_activity(wallet: str, limit: int = 500) -> list:
    """Fetch user activity from Data API."""
    # Based on docs: GET https://data-api.polymarket.com/activity
    # Query params: user, limit, type, start, end, side, market
    url = f"https://data-api.polymarket.com/activity"
    params = {
        'user': wallet,
        'limit': limit,
        'type': 'TRADE',  # Only trades
    }

    log(f"Fetching activity from: {url}")
    log(f"Params: {params}")

    try:
        r = requests.get(url, params=params, timeout=30)
        log(f"Status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            log(f"Got {len(data)} activity records")
            return data
        else:
            log(f"Error: {r.text[:500]}")
            return []
    except Exception as e:
        log(f"Exception: {e}")
        return []

def fetch_trades(wallet: str, limit: int = 500) -> list:
    """Fetch trades from dedicated trades endpoint."""
    url = f"https://data-api.polymarket.com/trades"
    params = {
        'user': wallet,
        'limit': limit,
    }

    log(f"Fetching trades from: {url}")
    log(f"Params: {params}")

    try:
        r = requests.get(url, params=params, timeout=30)
        log(f"Status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            log(f"Got {len(data)} trade records")
            return data
        else:
            log(f"Error: {r.text[:500]}")
            return []
    except Exception as e:
        log(f"Exception: {e}")
        return []

def identify_arbitrage_pairs(trades: list):
    """Identify arbitrage trades (same market, opposite outcomes)."""
    log("\n" + "="*70)
    log("ARBITRAGE PATTERN ANALYSIS")
    log("="*70)

    # Group by conditionId (market)
    markets = defaultdict(list)
    for t in trades:
        condition_id = t.get('conditionId', 'unknown')
        markets[condition_id].append(t)

    log(f"Total unique markets: {len(markets)}")

    # Find markets with both YES and NO positions
    arb_markets = []
    for condition_id, market_trades in markets.items():
        outcomes = [t.get('outcome', '') for t in market_trades]

        # Check if both Yes and No outcomes present
        has_yes = any('Yes' in str(o) for o in outcomes)
        has_no = any('No' in str(o) for o in outcomes)

        if has_yes and has_no:
            arb_markets.append({
                'condition_id': condition_id,
                'title': market_trades[0].get('title', 'Unknown'),
                'trades': market_trades,
                'count': len(market_trades)
            })

    log(f"Markets with BOTH Yes and No positions: {len(arb_markets)}")
    log(f"Arbitrage rate: {len(arb_markets)/len(markets)*100:.1f}%")

    # Analyze arb markets in detail
    if arb_markets:
        log(f"\n" + "-"*70)
        log("ARBITRAGE MARKETS (Sample):")
        log("-"*70)

        for i, market in enumerate(arb_markets[:5], 1):
            log(f"\n{i}. {market['title']}")
            log(f"   Condition ID: {market['condition_id']}")
            log(f"   Total trades: {market['count']}")

            # Calculate combined cost
            yes_trades = [t for t in market['trades'] if 'Yes' in str(t.get('outcome', ''))]
            no_trades = [t for t in market['trades'] if 'No' in str(t.get('outcome', ''))]

            if yes_trades and no_trades:
                yes_avg_price = sum(float(t.get('price', 0)) for t in yes_trades) / len(yes_trades)
                no_avg_price = sum(float(t.get('price', 0)) for t in no_trades) / len(no_trades)
                combined_cost = yes_avg_price + no_avg_price

                log(f"   Yes trades: {len(yes_trades)} @ avg ${yes_avg_price:.4f}")
                log(f"   No trades: {len(no_trades)} @ avg ${no_avg_price:.4f}")
                log(f"   COMBINED COST: ${combined_cost:.4f}")
                log(f"   Expected profit: ${1.0 - combined_cost:.4f} per share")

    return arb_markets

def analyze_market_types(trades: list):
    """Analyze what types of markets they trade."""
    log("\n" + "="*70)
    log("MARKET TYPE ANALYSIS")
    log("="*70)

    titles = [t.get('title', '').lower() for t in trades]

    # Categorize by keywords
    categories = defaultdict(int)
    for title in titles:
        if any(kw in title for kw in ['nfl', 'football', 'nba', 'basketball', 'nhl', 'hockey', 'mlb', 'baseball', 'super bowl', 'playoffs']):
            categories['Sports'] += 1
        elif any(kw in title for kw in ['trump', 'biden', 'election', 'president', 'congress', 'senate']):
            categories['Politics'] += 1
        elif any(kw in title for kw in ['weather', 'temperature', 'snow', 'rain']):
            categories['Weather'] += 1
        elif any(kw in title for kw in ['crypto', 'bitcoin', 'eth', 'btc']):
            categories['Crypto'] += 1
        else:
            categories['Other'] += 1

    log(f"\nMarket categories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        log(f"  {cat}: {count} trades ({count/len(trades)*100:.1f}%)")

def analyze_entry_prices(trades: list):
    """Analyze entry price thresholds."""
    log("\n" + "="*70)
    log("ENTRY PRICE ANALYSIS")
    log("="*70)

    prices = [float(t.get('price', 0)) for t in trades]

    if prices:
        log(f"\nPrice statistics:")
        log(f"  Min: ${min(prices):.4f}")
        log(f"  Max: ${max(prices):.4f}")
        log(f"  Avg: ${sum(prices)/len(prices):.4f}")
        log(f"  Median: ${sorted(prices)[len(prices)//2]:.4f}")

        # Price buckets
        buckets = defaultdict(int)
        for p in prices:
            if p < 0.40:
                buckets['< 0.40'] += 1
            elif p < 0.45:
                buckets['0.40-0.45'] += 1
            elif p < 0.50:
                buckets['0.45-0.50'] += 1
            elif p < 0.55:
                buckets['0.50-0.55'] += 1
            elif p < 0.60:
                buckets['0.55-0.60'] += 1
            else:
                buckets['>= 0.60'] += 1

        log(f"\nPrice distribution:")
        for bucket in ['< 0.40', '0.40-0.45', '0.45-0.50', '0.50-0.55', '0.55-0.60', '>= 0.60']:
            count = buckets[bucket]
            if count > 0:
                log(f"  {bucket}: {count} trades ({count/len(prices)*100:.1f}%)")

def analyze_position_sizing(trades: list):
    """Analyze position sizing strategy."""
    log("\n" + "="*70)
    log("POSITION SIZING ANALYSIS")
    log("="*70)

    sizes = [float(t.get('usdcSize', 0)) for t in trades if t.get('usdcSize')]

    if sizes:
        log(f"\nPosition size (USDC):")
        log(f"  Min: ${min(sizes):.2f}")
        log(f"  Max: ${max(sizes):.2f}")
        log(f"  Avg: ${sum(sizes)/len(sizes):.2f}")
        log(f"  Median: ${sorted(sizes)[len(sizes)//2]:.2f}")
        log(f"  Total volume: ${sum(sizes):,.2f}")

def save_results(trades: list, arb_markets: list):
    """Save analysis results to files."""
    output_dir = "C:/Projects/poly-scout/output"

    # Save all trades
    with open(f"{output_dir}/divi_trades.json", 'w') as f:
        json.dump(trades, f, indent=2)
    log(f"\nSaved {len(trades)} trades to: {output_dir}/divi_trades.json")

    # Save arbitrage markets
    with open(f"{output_dir}/divi_arb_markets.json", 'w') as f:
        json.dump(arb_markets, f, indent=2)
    log(f"Saved {len(arb_markets)} arb markets to: {output_dir}/divi_arb_markets.json")

def main():
    log("="*70)
    log("DIVILUNGAOBBW SPORTS_ARB STRATEGY ANALYSIS")
    log(f"Wallet: {WALLET}")
    log(f"Time: {datetime.now().isoformat()}")
    log("="*70)

    # Try both endpoints
    trades = fetch_activity(WALLET)

    if not trades:
        log("\nTrying trades endpoint...")
        trades = fetch_trades(WALLET)

    if not trades:
        log("\nERROR: Could not fetch any trade data")
        return

    # Show sample
    log("\n" + "-"*70)
    log("SAMPLE TRADE:")
    log("-"*70)
    log(json.dumps(trades[0], indent=2)[:1000])

    # Analyze
    arb_markets = identify_arbitrage_pairs(trades)
    analyze_market_types(trades)
    analyze_entry_prices(trades)
    analyze_position_sizing(trades)

    # Save
    save_results(trades, arb_markets)

    log("\n" + "="*70)
    log("ANALYSIS COMPLETE")
    log("="*70)

if __name__ == "__main__":
    main()
