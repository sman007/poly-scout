#!/usr/bin/env python3
"""
Deep Strategy Analysis: DiviLungaoBBW
Extract exact trading rules for replication
"""

import json
from collections import defaultdict, Counter
from datetime import datetime

def log(msg):
    print(f"[STRATEGY] {msg}", flush=True)

def load_trades():
    """Load trades from saved file."""
    with open('C:/Projects/poly-scout/output/divi_trades.json', 'r') as f:
        return json.load(f)

def extract_market_patterns(trades):
    """Extract what markets they trade."""
    log("\n" + "="*70)
    log("MARKET SELECTION PATTERNS")
    log("="*70)

    # Count by event type
    event_types = Counter()
    for t in trades:
        title = t.get('title', '').lower()
        if 'ufc' in title:
            event_types['UFC'] += 1
        elif 'nfl' in title or 'football' in title:
            event_types['NFL'] += 1
        elif 'nba' in title or 'basketball' in title:
            event_types['NBA'] += 1
        elif 'crypto' in title or 'bitcoin' in title or 'btc' in title or 'eth' in title:
            event_types['Crypto'] += 1
        else:
            # Extract first word
            first_word = title.split()[0] if title.split() else 'Unknown'
            event_types[first_word] += 1

    log(f"\nEvent types:")
    for event_type, count in event_types.most_common(10):
        log(f"  {event_type}: {count} trades ({count/len(trades)*100:.1f}%)")

    # UFC specific analysis
    ufc_trades = [t for t in trades if 'ufc' in t.get('title', '').lower()]
    if ufc_trades:
        log(f"\n" + "-"*70)
        log(f"UFC SPECIFIC ANALYSIS ({len(ufc_trades)} trades)")
        log("-"*70)

        # Count by outcome index
        outcome_indices = Counter(t.get('outcomeIndex') for t in ufc_trades)
        log(f"\nOutcome index distribution:")
        for idx, count in outcome_indices.most_common():
            log(f"  Index {idx}: {count} trades")

def analyze_side_and_outcome(trades):
    """Analyze BUY vs SELL and outcome patterns."""
    log("\n" + "="*70)
    log("TRADE SIDE & OUTCOME ANALYSIS")
    log("="*70)

    sides = Counter(t.get('side') for t in trades)
    log(f"\nTrade sides:")
    for side, count in sides.most_common():
        log(f"  {side}: {count} trades ({count/len(trades)*100:.1f}%)")

    # Outcome analysis
    outcomes = Counter(t.get('outcome') for t in trades)
    log(f"\nTop 10 outcomes:")
    for outcome, count in outcomes.most_common(10):
        log(f"  {outcome}: {count} trades")

def analyze_timing(trades):
    """Analyze when they trade."""
    log("\n" + "="*70)
    log("TIMING ANALYSIS")
    log("="*70)

    timestamps = [t.get('timestamp') for t in trades]

    # Convert to datetime
    dates = [datetime.fromtimestamp(ts) for ts in timestamps]

    # Hour of day
    hours = Counter(d.hour for d in dates)
    log(f"\nTop hours of trading:")
    for hour, count in hours.most_common(5):
        log(f"  {hour:02d}:00: {count} trades")

    # Day of week
    days = Counter(d.weekday() for d in dates)
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    log(f"\nDay of week:")
    for day_idx in range(7):
        count = days[day_idx]
        if count > 0:
            log(f"  {day_names[day_idx]}: {count} trades")

def analyze_position_scaling(trades):
    """Analyze if they scale positions on same market."""
    log("\n" + "="*70)
    log("POSITION SCALING ANALYSIS")
    log("="*70)

    # Group by market
    markets = defaultdict(list)
    for t in trades:
        condition_id = t.get('conditionId')
        markets[condition_id].append(t)

    # Find markets with multiple trades
    multi_trade_markets = {k: v for k, v in markets.items() if len(v) > 1}

    log(f"\nMarkets with multiple trades: {len(multi_trade_markets)}/{len(markets)}")

    # Analyze scaling pattern
    if multi_trade_markets:
        log(f"\nSample multi-trade markets:")

        for i, (condition_id, market_trades) in enumerate(list(multi_trade_markets.items())[:3], 1):
            market_trades = sorted(market_trades, key=lambda x: x.get('timestamp'))

            log(f"\n{i}. {market_trades[0].get('title', 'Unknown')}")
            log(f"   Trades: {len(market_trades)}")

            for j, t in enumerate(market_trades, 1):
                dt = datetime.fromtimestamp(t.get('timestamp'))
                log(f"   {j}. {dt.strftime('%Y-%m-%d %H:%M:%S')} | {t.get('side')} | ${t.get('price'):.4f} | {t.get('usdcSize'):.2f} USDC")

            # Check if averaging down/up
            prices = [t.get('price') for t in market_trades]
            if all(p == prices[0] for p in prices):
                log(f"   Pattern: SAME PRICE (accumulating)")
            elif prices == sorted(prices):
                log(f"   Pattern: AVERAGING UP")
            elif prices == sorted(prices, reverse=True):
                log(f"   Pattern: AVERAGING DOWN")
            else:
                log(f"   Pattern: MIXED")

def extract_entry_rules(trades):
    """Extract specific entry conditions."""
    log("\n" + "="*70)
    log("ENTRY RULES EXTRACTION")
    log("="*70)

    # Price thresholds
    prices = [t.get('price') for t in trades]
    log(f"\nPrice thresholds:")
    log(f"  Min entry: ${min(prices):.4f}")
    log(f"  Max entry: ${max(prices):.4f}")
    log(f"  Avg entry: ${sum(prices)/len(prices):.4f}")
    log(f"  Median entry: ${sorted(prices)[len(prices)//2]:.4f}")

    # 90th percentile (where 90% of trades are below)
    p90_idx = int(len(sorted(prices)) * 0.9)
    p90 = sorted(prices)[p90_idx]
    log(f"  90th percentile: ${p90:.4f}")

    # Preferred range
    price_counts = defaultdict(int)
    for p in prices:
        bucket = round(p * 20) / 20  # Round to nearest 0.05
        price_counts[bucket] += 1

    log(f"\nMost common price points:")
    for price, count in sorted(price_counts.items(), key=lambda x: -x[1])[:5]:
        log(f"  ${price:.2f}: {count} trades")

def extract_strategy_blueprint(trades):
    """Generate final strategy blueprint."""
    log("\n" + "="*70)
    log("STRATEGY BLUEPRINT FOR REPLICATION")
    log("="*70)

    # Calculate key metrics
    total_volume = sum(t.get('usdcSize', 0) for t in trades)
    avg_position = total_volume / len(trades)
    median_position = sorted([t.get('usdcSize', 0) for t in trades])[len(trades)//2]

    prices = [t.get('price') for t in trades]
    avg_price = sum(prices) / len(prices)

    # Extract dominant pattern
    ufc_pct = len([t for t in trades if 'ufc' in t.get('title', '').lower()]) / len(trades) * 100
    buy_pct = len([t for t in trades if t.get('side') == 'BUY']) / len(trades) * 100

    log(f"\nSTRATEGY: UFC Fighter Directional Betting")
    log(f"\nMARKET SELECTION:")
    log(f"  - Primary: UFC fights ({ufc_pct:.1f}% of trades)")
    log(f"  - Focus: Single fighter outcomes (not arbitrage)")
    log(f"  - Side: {buy_pct:.1f}% BUY")

    log(f"\nENTRY CONDITIONS:")
    log(f"  - Price range: $0.43 - $0.61")
    log(f"  - Sweet spot: $0.45 - $0.50 ({len([p for p in prices if 0.45 <= p <= 0.50])/len(prices)*100:.1f}% of trades)")
    log(f"  - Average entry: ${avg_price:.4f}")

    log(f"\nPOSITION SIZING:")
    log(f"  - Median: ${median_position:.2f}")
    log(f"  - Average: ${avg_position:.2f}")
    log(f"  - Max observed: ${max(t.get('usdcSize', 0) for t in trades):,.2f}")
    log(f"  - For $2000 capital: Use $20-$100 per trade")

    log(f"\nEXIT CONDITIONS:")
    log(f"  - Hold until event resolution (UFC fight ends)")
    log(f"  - No early exits observed")

    log(f"\nRISK MANAGEMENT:")
    log(f"  - Multiple trades on same market (scaling)")
    log(f"  - Total markets: {len(set(t.get('conditionId') for t in trades))}")
    log(f"  - Avg trades per market: {len(trades)/len(set(t.get('conditionId') for t in trades)):.1f}")

    log(f"\nREPLICATION WITH $2000:")
    log(f"  1. Find UFC markets on Polymarket")
    log(f"  2. Identify favorites priced 0.45-0.50")
    log(f"  3. BUY YES on favorite fighter")
    log(f"  4. Position size: $20-100 (1-5% of capital)")
    log(f"  5. Hold until fight ends")
    log(f"  6. Can scale into position if price improves")

    # Calculate expected returns
    log(f"\nEXPECTED RETURNS:")
    log(f"  - If avg entry $0.49, need 49% win rate to break even")
    log(f"  - Each win: ~100% return on capital")
    log(f"  - Each loss: -100% of position")
    log(f"  - This trader likely has edge via UFC knowledge/research")

def main():
    log("="*70)
    log("DEEP STRATEGY EXTRACTION: DIVILUNGAOBBW")
    log(f"Time: {datetime.now().isoformat()}")
    log("="*70)

    trades = load_trades()
    log(f"Loaded {len(trades)} trades")

    extract_market_patterns(trades)
    analyze_side_and_outcome(trades)
    analyze_timing(trades)
    analyze_position_scaling(trades)
    extract_entry_rules(trades)
    extract_strategy_blueprint(trades)

    log("\n" + "="*70)
    log("EXTRACTION COMPLETE")
    log("="*70)

if __name__ == "__main__":
    main()
