"""
Example: Complete saturation analysis workflow.

This demonstrates how to:
1. Analyze a reference wallet's strategy
2. Find similar wallets running the same strategy
3. Track saturation over time
4. Make decisions about edge durability
"""

import asyncio
from src.scanner import WalletScanner
from src.daemon import (
    update_saturation_snapshot,
    get_saturation_trend,
    load_saturation_history,
    log
)


async def analyze_strategy_saturation(reference_wallet: str):
    """
    Complete saturation analysis for a wallet's strategy.

    Args:
        reference_wallet: Wallet address to analyze
    """
    print("\n" + "="*70)
    print("STRATEGY SATURATION ANALYSIS")
    print("="*70 + "\n")

    async with WalletScanner() as scanner:
        # Step 1: Fetch reference wallet's trading activity
        log(f"Step 1: Analyzing reference wallet {reference_wallet[:16]}...")
        trades = await scanner.fetch_wallet_activity(reference_wallet, limit=500)

        if not trades:
            log("  ERROR: Could not fetch wallet activity")
            return

        log(f"  Found {len(trades)} trades")

        # Step 2: Extract strategy parameters from trades
        log("\nStep 2: Extracting strategy parameters...")

        # Get unique markets
        markets = set()
        entry_prices = {}
        trade_sizes = []

        for trade in trades:
            market_slug = trade.market_title or trade.market_id
            if market_slug:
                markets.add(market_slug)
                if market_slug not in entry_prices:
                    entry_prices[market_slug] = []
                entry_prices[market_slug].append(trade.price)

            if trade.size > 0:
                trade_sizes.append(trade.size)

        # Calculate average entry prices
        avg_entry_prices = {
            market: sum(prices) / len(prices)
            for market, prices in entry_prices.items()
        }

        # Determine likely strategy based on markets
        likely_strategy = "UNKNOWN"
        crypto_keywords = ["up or down", "bitcoin", "ethereum", "btc", "eth", "sol"]

        if any(any(kw in market.lower() for kw in crypto_keywords) for market in markets):
            likely_strategy = "CRYPTO_ARB"

        reference_params = {
            "markets": list(markets),
            "timing_pattern": "unknown",
            "entry_price_ranges": avg_entry_prices,
            "likely_strategy": likely_strategy,
        }

        log(f"  Strategy: {likely_strategy}")
        log(f"  Markets traded: {len(markets)}")
        log(f"  Avg trade size: ${sum(trade_sizes) / len(trade_sizes):.2f}" if trade_sizes else "  Avg trade size: $0")
        log(f"  Sample markets: {', '.join(list(markets)[:3])}...")

        # Step 3: Find similar wallets
        log(f"\nStep 3: Finding wallets running similar strategy (checking 50 wallets)...")
        similar = await scanner.find_similar_wallets(reference_params, limit=50)

        log(f"\n  Results:")
        log(f"    Similar wallets: {similar['wallet_count']}")
        log(f"    Total capital: ${similar['total_capital']:,.0f}")

        if similar['wallet_count'] > 0 and 'wallet_details' in similar:
            log(f"\n  Top 3 most similar:")
            for i, wallet in enumerate(similar['wallet_details'][:3], 1):
                log(f"    {i}. {wallet['address'][:16]}... "
                    f"(overlap: {wallet['market_overlap']:.0%}, "
                    f"price sim: {wallet['price_similarity']:.0%})")

        # Step 4: Update saturation history
        log(f"\nStep 4: Recording saturation data...")

        # Create strategy key from likely_strategy and primary market
        primary_market = list(markets)[0] if markets else "UNKNOWN"
        strategy_key = f"{likely_strategy}_{primary_market[:20]}"

        trend = update_saturation_snapshot(
            strategy_key,
            similar['wallet_count'],
            similar['total_capital']
        )

        # Step 5: Assess edge durability
        log(f"\nStep 5: Edge durability assessment:")

        if similar['wallet_count'] == 0:
            log("  Status: UNEXPLOITED EDGE")
            log("  Durability: HIGH (no competition detected)")
            log("  Recommendation: BUILD IMMEDIATELY")

        elif similar['wallet_count'] <= 3 and trend != "increasing":
            log(f"  Status: LOW SATURATION ({similar['wallet_count']} wallets)")
            log(f"  Durability: HIGH (trend: {trend})")
            log(f"  Recommendation: BUILD SOON")

        elif similar['wallet_count'] <= 10 and trend == "stable":
            log(f"  Status: MODERATE SATURATION ({similar['wallet_count']} wallets)")
            log(f"  Durability: MEDIUM (trend: {trend})")
            log(f"  Recommendation: BUILD WITH CAUTION")

        else:
            log(f"  Status: HIGH SATURATION ({similar['wallet_count']} wallets)")
            log(f"  Durability: LOW (trend: {trend})")
            log(f"  Recommendation: SKIP OR INNOVATE")

        # Step 6: Show historical context
        log(f"\nStep 6: Historical context...")
        history = load_saturation_history()

        if strategy_key in history:
            dates = sorted(history[strategy_key].keys(), reverse=True)
            log(f"  Historical data points: {len(dates)}")

            if len(dates) >= 2:
                oldest = history[strategy_key][dates[-1]]
                newest = history[strategy_key][dates[0]]

                wallet_change = newest['wallets'] - oldest['wallets']
                capital_change = newest['capital'] - oldest['capital']

                log(f"  Change since {dates[-1]}:")
                log(f"    Wallets: {oldest['wallets']} -> {newest['wallets']} ({wallet_change:+d})")
                log(f"    Capital: ${oldest['capital']:,.0f} -> ${newest['capital']:,.0f} (${capital_change:+,.0f})")
        else:
            log("  No historical data yet (first scan)")

    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70 + "\n")


async def main():
    """
    Example usage with a reference wallet.

    Replace with a real wallet address to test.
    """
    # Example wallet address - replace with real address
    # For testing, this will demonstrate the workflow even if the wallet doesn't exist
    example_wallet = "0x8dxd..." # Replace with actual wallet address

    print("\nSATURATION ANALYSIS EXAMPLE")
    print("This script demonstrates the complete saturation analysis workflow.\n")
    print("To use with a real wallet:")
    print("1. Find an interesting wallet on Polymarket leaderboard")
    print("2. Copy their address")
    print("3. Replace 'example_wallet' in this script")
    print("4. Run: python example_saturation_analysis.py\n")

    # Uncomment to run with real data:
    # await analyze_strategy_saturation(example_wallet)

    print("Example workflow (not executing - add real wallet address):\n")
    print("  1. Fetch reference wallet's trades")
    print("  2. Extract strategy parameters (markets, entry prices, patterns)")
    print("  3. Scan leaderboard for similar wallets")
    print("  4. Calculate market overlap and price similarity")
    print("  5. Estimate total competing capital")
    print("  6. Record snapshot in saturation_history.json")
    print("  7. Compare to 7-day history to determine trend")
    print("  8. Assess edge durability and make BUILD/SKIP recommendation")
    print("\nKey insight: Strategy edges decay as more bots discover them.")
    print("Saturation tracking helps you catch them BEFORE saturation.\n")


if __name__ == "__main__":
    asyncio.run(main())
