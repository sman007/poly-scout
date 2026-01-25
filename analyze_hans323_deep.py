#!/usr/bin/env python3
"""
Deep analysis of Hans323's actual trading strategy.

Key question: The API shows side=BUY, not SELL. How are they making money?
"""

import requests
import json
from datetime import datetime, timezone
from collections import defaultdict

WALLET = "0x0f37cb80dee49d55b5f6d9e595d52591d6371410"


def log(msg):
    print(f"[DEEP] {msg}", flush=True)


def fetch_all_weather_activity(wallet: str) -> list:
    """Fetch all activity and filter to weather."""
    all_trades = []
    offset = 0
    limit = 500

    while True:
        url = f"https://data-api.polymarket.com/activity?user={wallet}&limit={limit}&offset={offset}"
        r = requests.get(url, timeout=30)
        batch = r.json()
        if not batch:
            break
        all_trades.extend(batch)
        offset += limit
        if len(batch) < limit:
            break
        log(f"Fetched {len(all_trades)} records...")

    weather = [t for t in all_trades if "temperature" in str(t.get("title", "")).lower()]
    return weather


def analyze_price_patterns(trades: list):
    """Analyze the price patterns to understand the strategy."""
    log("\n" + "="*70)
    log("PRICE PATTERN ANALYSIS")
    log("="*70)

    trade_only = [t for t in trades if t.get("type") == "TRADE"]

    # Separate by outcome
    yes_trades = [t for t in trade_only if t.get("outcome") == "Yes"]
    no_trades = [t for t in trade_only if t.get("outcome") == "No"]

    log(f"\nYes trades: {len(yes_trades)}")
    log(f"No trades: {len(no_trades)}")

    # Analyze prices for Yes trades
    if yes_trades:
        yes_prices = [float(t.get("price", 0) or 0) for t in yes_trades]
        yes_prices = [p for p in yes_prices if p > 0]
        if yes_prices:
            log(f"\nYES trades price distribution:")
            log(f"  Min: {min(yes_prices):.4f}")
            log(f"  Max: {max(yes_prices):.4f}")
            log(f"  Avg: {sum(yes_prices)/len(yes_prices):.4f}")

            # Bucket by price range
            buckets = defaultdict(int)
            for p in yes_prices:
                if p >= 0.99:
                    buckets["99%+"] += 1
                elif p >= 0.90:
                    buckets["90-99%"] += 1
                elif p >= 0.50:
                    buckets["50-90%"] += 1
                elif p >= 0.10:
                    buckets["10-50%"] += 1
                else:
                    buckets["<10%"] += 1

            for bucket, count in sorted(buckets.items()):
                log(f"    {bucket}: {count} trades")

    # Analyze prices for No trades
    if no_trades:
        no_prices = [float(t.get("price", 0) or 0) for t in no_trades]
        no_prices = [p for p in no_prices if p > 0]
        if no_prices:
            log(f"\nNO trades price distribution:")
            log(f"  Min: {min(no_prices):.4f}")
            log(f"  Max: {max(no_prices):.4f}")
            log(f"  Avg: {sum(no_prices)/len(no_prices):.4f}")

            buckets = defaultdict(int)
            for p in no_prices:
                if p >= 0.99:
                    buckets["99%+"] += 1
                elif p >= 0.90:
                    buckets["90-99%"] += 1
                elif p >= 0.50:
                    buckets["50-90%"] += 1
                elif p >= 0.10:
                    buckets["10-50%"] += 1
                else:
                    buckets["<10%"] += 1

            for bucket, count in sorted(buckets.items()):
                log(f"    {bucket}: {count} trades")


def analyze_timing(trades: list):
    """Analyze when trades happen relative to market end."""
    log("\n" + "="*70)
    log("TIMING ANALYSIS")
    log("="*70)

    trade_only = [t for t in trades if t.get("type") == "TRADE"]

    for trade in trade_only[:10]:  # Sample
        ts = trade.get("timestamp")
        title = trade.get("title", "")
        slug = trade.get("eventSlug", "")
        price = trade.get("price", 0)
        side = trade.get("side")
        outcome = trade.get("outcome")
        size = trade.get("usdcSize", 0)

        # Parse date from title or slug
        trade_time = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None

        log(f"\nTrade: {title[:60]}...")
        log(f"  Time: {trade_time}")
        log(f"  Side: {side} | Outcome: {outcome}")
        log(f"  Price: {price} | Size: ${size}")


def analyze_redeems(trades: list):
    """Analyze REDEEM transactions to see actual payouts."""
    log("\n" + "="*70)
    log("REDEEM ANALYSIS (ACTUAL PAYOUTS)")
    log("="*70)

    redeems = [t for t in trades if t.get("type") == "REDEEM"]

    log(f"\nTotal redeems: {len(redeems)}")

    total_redeemed = 0
    for r in redeems:
        title = r.get("title", "")[:60]
        amount = float(r.get("usdcSize", 0) or 0)
        outcome = r.get("outcome", "")
        total_redeemed += amount
        log(f"  ${amount:,.2f} on {outcome}: {title}...")

    log(f"\nTotal redeemed: ${total_redeemed:,.2f}")


def analyze_pnl_calculation(trades: list):
    """Try to calculate actual P&L from trades vs redeems."""
    log("\n" + "="*70)
    log("P&L CALCULATION")
    log("="*70)

    # Sum of buys (cost)
    buys = [t for t in trades if t.get("type") == "TRADE" and t.get("side") == "BUY"]
    total_cost = sum(float(t.get("usdcSize", 0) or 0) for t in buys)

    # Sum of redeems (payout)
    redeems = [t for t in trades if t.get("type") == "REDEEM"]
    total_redeemed = sum(float(t.get("usdcSize", 0) or 0) for t in redeems)

    log(f"\nTotal cost (buys): ${total_cost:,.2f}")
    log(f"Total redeemed: ${total_redeemed:,.2f}")
    log(f"Realized P&L: ${total_redeemed - total_cost:+,.2f}")


def check_outcome_relationship(trades: list):
    """Check if there's a pattern in which outcomes he buys based on price."""
    log("\n" + "="*70)
    log("OUTCOME vs PRICE RELATIONSHIP")
    log("="*70)

    trade_only = [t for t in trades if t.get("type") == "TRADE"]

    # For each trade, determine if he's buying the likely or unlikely outcome
    for trade in trade_only[:15]:
        price = float(trade.get("price", 0) or 0)
        outcome = trade.get("outcome")
        title = trade.get("title", "")[:50]
        size = float(trade.get("usdcSize", 0) or 0)

        # If price > 0.5, this outcome is more likely
        if price > 0.5:
            likelihood = "LIKELY"
            implied_prob = price
        else:
            likelihood = "UNLIKELY"
            implied_prob = price

        log(f"\n{title}...")
        log(f"  BUY {outcome} @ {price:.3f} ({implied_prob*100:.1f}% implied)")
        log(f"  Buying the {likelihood} outcome for ${size:,.2f}")


def analyze_bracket_type_strategy(trades: list):
    """Analyze strategy by bracket type."""
    log("\n" + "="*70)
    log("STRATEGY BY BRACKET TYPE")
    log("="*70)

    trade_only = [t for t in trades if t.get("type") == "TRADE"]

    exact_trades = []
    or_higher_trades = []
    or_lower_trades = []

    for t in trade_only:
        title = str(t.get("title", "")).lower()
        if "or higher" in title:
            or_higher_trades.append(t)
        elif "or below" in title or "or lower" in title:
            or_lower_trades.append(t)
        else:
            exact_trades.append(t)

    log(f"\nExact bracket trades: {len(exact_trades)}")
    log(f"Or higher trades: {len(or_higher_trades)}")
    log(f"Or lower trades: {len(or_lower_trades)}")

    # For each type, what's the pattern?
    for name, group in [("EXACT", exact_trades), ("OR_HIGHER", or_higher_trades), ("OR_LOWER", or_lower_trades)]:
        if not group:
            continue

        yes_count = sum(1 for t in group if t.get("outcome") == "Yes")
        no_count = sum(1 for t in group if t.get("outcome") == "No")
        yes_vol = sum(float(t.get("usdcSize", 0) or 0) for t in group if t.get("outcome") == "Yes")
        no_vol = sum(float(t.get("usdcSize", 0) or 0) for t in group if t.get("outcome") == "No")

        log(f"\n{name}:")
        log(f"  Yes: {yes_count} trades, ${yes_vol:,.2f}")
        log(f"  No: {no_count} trades, ${no_vol:,.2f}")


def main():
    log("="*70)
    log("HANS323 DEEP STRATEGY ANALYSIS")
    log("="*70)

    weather_trades = fetch_all_weather_activity(WALLET)
    log(f"\nTotal weather trades: {len(weather_trades)}")

    analyze_price_patterns(weather_trades)
    analyze_timing(weather_trades)
    analyze_redeems(weather_trades)
    analyze_pnl_calculation(weather_trades)
    check_outcome_relationship(weather_trades)
    analyze_bracket_type_strategy(weather_trades)

    log("\n" + "="*70)
    log("CONCLUSIONS")
    log("="*70)


if __name__ == "__main__":
    main()
